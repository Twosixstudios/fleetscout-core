"""Manual end-to-end walkthrough for Task HD-5.3.

Walks the complete operational loop:
  1. Driver reports an issue -> truck is Grounded.
  2. Dispatcher attempts assignment -> BLOCKED (HD-5.2 hard lockout).
  3. Mechanic performs repair -> un-grounds (role-restricted).
  4. Dispatcher attempts assignment again -> SUCCEEDS.

Usage (from repo root):
    python -m scripts.verify_hd_5_3

Runs against the configured database using only module imports and legacy-safe
runs. Idempotent: creates uniquely-suffixed rows, then cleans them up. Exits
non-zero if any step fails.
"""

import asyncio
import sys
from datetime import datetime

from src.core.database import AsyncSessionLocal
from src.core.exceptions import SafetyViolationError
from src.core.models import Load, RepairReport, User, Vehicle
from src.core.services import (
    UNGROUND_AUTHORIZED_ROLES,
    create_dispatched_load,
    create_repair_report,
    ground_vehicle,
    unground_vehicle,
)

SUFFIX = datetime.utcnow().strftime("%H%M%S")

results = []


def report(label, ok, detail=""):
    status = "[PASS]" if ok else "[FAIL]"
    print(f"{status} {label}" + (f" — {detail}" if detail else ""))
    results.append(ok)


async def main():
    print("=" * 72)
    print("HD-5.3 End-to-End Walkthrough — Ground/Block/Unground/Assign")
    print("=" * 72)

    unit = f"HD53-{SUFFIX}"
    suffix = SUFFIX

    # ---------- Setup actors ----------
    async with AsyncSessionLocal() as session:
        driver = User(
            email=f"hd53-driver-{suffix}@fleetscout.com",
            hashed_password="x",
            role="Driver",
            carrier_id=1,
        )
        mechanic = User(
            email=f"hd53-mechanic-{suffix}@fleetscout.com",
            hashed_password="x",
            role="Mechanic",
            carrier_id=1,
        )
        dispatcher = User(
            email=f"hd53-dispatcher-{suffix}@fleetscout.com",
            hashed_password="x",
            role="Dispatcher",
            carrier_id=1,
        )
        vehicle = Vehicle(unit_number=unit, status="Active", carrier_id=1)
        session.add_all([driver, mechanic, dispatcher, vehicle])
        await session.commit()
        await session.refresh(driver)
        await session.refresh(mechanic)
        await session.refresh(dispatcher)
        await session.refresh(vehicle)
        vehicle_id = vehicle.id

    report("Setup: driver, mechanic, dispatcher, Active truck created", True)

    # ---------- 1. Driver reports issue -> Grounded ----------
    async with AsyncSessionLocal() as session:
        report_entry = await create_repair_report(
            session,
            driver_id=driver.id,
            category="Brakes",
            description="E2E walkthrough: soft pedal, brake light flickers.",
            vehicle_id=vehicle_id,
        )
        grounded = await ground_vehicle(session, vehicle_id)

    ok1 = grounded.status == "Grounded"
    report("Driver reported issue (RepairReport persisted)", bool(report_entry.id))
    report("Vehicle status is now 'Grounded'", ok1, grounded.status)

    # ---------- 2. Dispatcher attempt -> BLOCKED ----------
    blocked_msg = None
    try:
        async with AsyncSessionLocal() as session:
            await create_dispatched_load(
                session,
                load_number=f"HD53-BLOCKED-{suffix}",
                load_weight=20000,
                commodity="Walkthrough cargo",
                pickup_ref="PU-HD53",
                delivery_ref="DEL-HD53",
                assigned_vehicle_id=vehicle_id,
            )
    except SafetyViolationError as sve:
        blocked_msg = str(sve)

    report(
        "Dispatcher assignment REJECTED by safety interceptor",
        blocked_msg is not None,
        blocked_msg or "assignment unexpectedly succeeded",
    )

    # ---------- 3. Mechanic repair -> Ungrounded (role-guarded) ----------
    denied = False
    try:
        async with AsyncSessionLocal() as session:
            await unground_vehicle(session, vehicle_id, actor_role="Dispatcher")
    except PermissionError:
        denied = True
    report("Dispatcher (unauthorized) blocked from un-grounding", denied)

    async with AsyncSessionLocal() as session:
        repaired = await unground_vehicle(session, vehicle_id, actor_role="Mechanic")
    report(
        "Mechanic performed repair -> vehicle un-grounded",
        repaired.status == "Active",
        repaired.status,
    )

    async with AsyncSessionLocal() as session:
        fresh = await session.get(Vehicle, vehicle_id)
    report("Post-repair DB state is 'Active'", fresh.status == "Active", fresh.status)
    report(
        "Unground authorized roles = Owner/Mechanic",
        UNGROUND_AUTHORIZED_ROLES == ("Owner", "Mechanic"),
    )

    # ---------- 4. Dispatcher attempt -> SUCCEEDS ----------
    async with AsyncSessionLocal() as session:
        load = await create_dispatched_load(
            session,
            load_number=f"HD53-ASSIGN-{suffix}",
            load_weight=20000,
            commodity="Walkthrough",
            pickup_ref="PU-HD53",
            delivery_ref="DEL-HD53",
            assigned_vehicle_id=vehicle_id,
            assigned_driver_id=driver.id,
        )
    report(
        "Dispatcher assignment succeeded after repair",
        load.status == "dispatched"
        and load.assigned_vehicle_id == vehicle_id
        and load.assigned_driver_id == driver.id,
        f"{load.load_number} -> #{unit}",
    )

    # ---------- Cleanup ----------
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                Load.__table__.delete().where(
                    Load.assigned_vehicle_id == vehicle_id
                )
            )
            await session.execute(
                RepairReport.__table__.delete().where(
                    RepairReport.vehicle_id == vehicle_id
                )
            )
            await session.execute(
                Vehicle.__table__.delete().where(Vehicle.id == vehicle_id)
            )
            await session.execute(
                User.__table__.delete().where(
                    User.id.in_([driver.id, mechanic.id, dispatcher.id])
                )
            )
            await session.commit()
            print("[INFO] Cleaned up walkthrough rows.")
    except Exception as cleanup_err:
        print(f"[WARN] Cleanup incomplete: {cleanup_err}")

    # ---------- Summary ----------
    passed = all(results)
    print("-" * 72)
    print(f"HD-5.3 walkthrough: {sum(results)}/{len(results)} steps passed")
    print("=" * 72)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))