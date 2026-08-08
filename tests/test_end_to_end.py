import pytest

from sqlalchemy import select

from src.core.database import Base, sync_engine, AsyncSessionLocal
from src.core.exceptions import SafetyViolationError
from src.core.models import RepairReport, User, Vehicle
from src.core.services import (
    UNGROUND_AUTHORIZED_ROLES,
    create_dispatched_load,
    create_repair_report,
    ground_vehicle,
    unground_vehicle,
)


@pytest.fixture(scope="module", autouse=True)
def reset_schema():
    Base.metadata.drop_all(bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)


@pytest.mark.asyncio
async def test_full_lifecycle_ground_block_repair_assign():
    """Task HD-5.3 end-to-end walkthrough:
    Driver reports issue -> truck Grounded -> Dispatcher blocked ->
    Mechanic repairs (unground) -> Dispatcher assignment succeeds.
    """
    # --- Setup: driver, mechanic, and an active truck ---
    async with AsyncSessionLocal() as session:
        driver = User(
            email="e2e-driver@fleetscout.com",
            hashed_password="x",
            role="Driver",
            carrier_id=1,
        )
        mechanic = User(
            email="e2e-mechanic@fleetscout.com",
            hashed_password="x",
            role="Mechanic",
            carrier_id=1,
        )
        vehicle = Vehicle(unit_number="E2E-001", status="Active", carrier_id=1)
        session.add_all([driver, mechanic, vehicle])
        await session.commit()
        await session.refresh(driver)
        await session.refresh(mechanic)
        await session.refresh(vehicle)
        vehicle_id = vehicle.id

    # --- 1. Driver reports issue -> truck is Grounded ---
    async with AsyncSessionLocal() as session:
        report = await create_repair_report(
            session,
            driver_id=driver.id,
            category="Brakes",
            description="Squealing noise, pedal feels soft.",
            vehicle_id=vehicle_id,
        )
        grounded = await ground_vehicle(session, vehicle_id)

    assert report is not None
    assert report.vehicle_id == vehicle_id
    assert grounded.status == "Grounded"

    # --- 2. Dispatcher attempts assignment -> blocked by HD-5.2 interceptor ---
    with pytest.raises(SafetyViolationError) as exc_info:
        async with AsyncSessionLocal() as session:
            await create_dispatched_load(
                session,
                load_number="E2E-BLOCKED-1",
                load_weight=20000,
                commodity="Test Cargo",
                pickup_ref="PU-E2E",
                delivery_ref="DEL-E2E",
                assigned_vehicle_id=vehicle_id,
            )
    assert "Grounded" in str(exc_info.value)

    # --- 3. Mechanic performs repair -> un-grounded ---
    async with AsyncSessionLocal() as session:
        repaired = await unground_vehicle(
            session, vehicle_id, actor_role="Mechanic"
        )
    assert repaired.status == "Active"

    # --- 4. Dispatcher attempts assignment -> succeeds ---
    async with AsyncSessionLocal() as session:
        load = await create_dispatched_load(
            session,
            load_number="E2E-ASSIGN-1",
            load_weight=20000,
            commodity="Test Cargo",
            pickup_ref="PU-E2E",
            delivery_ref="DEL-E2E",
            assigned_vehicle_id=vehicle_id,
            assigned_driver_id=driver.id,
        )

    assert load is not None
    assert load.status == "dispatched"
    assert load.assigned_vehicle_id == vehicle_id
    assert load.assigned_driver_id == driver.id


@pytest.mark.asyncio
async def test_unground_restricted_to_authorized_roles():
    """Only Owner/Mechanic roles may release a grounded asset (HD-5.3 guardrail)."""
    assert UNGROUND_AUTHORIZED_ROLES == ("Owner", "Mechanic")

    async with AsyncSessionLocal() as session:
        vehicle = Vehicle(unit_number="E2E-ROLE-01", status="Grounded", carrier_id=1)
        session.add(vehicle)
        await session.commit()
        await session.refresh(vehicle)
        vehicle_id = vehicle.id

    # Dispatcher (or any other role) is denied — asset stays Grounded
    with pytest.raises(PermissionError):
        async with AsyncSessionLocal() as session:
            await unground_vehicle(session, vehicle_id, actor_role="Dispatcher")

    async with AsyncSessionLocal() as session:
        fresh = await session.get(Vehicle, vehicle_id)
        assert fresh.status == "Grounded"

    # A missing actor role is also denied (no bypass)
    with pytest.raises(PermissionError):
        async with AsyncSessionLocal() as session:
            await unground_vehicle(session, vehicle_id)

    # Mechanic and Owner are authorized
    async with AsyncSessionLocal() as session:
        await unground_vehicle(session, vehicle_id, actor_role="Mechanic")

    async with AsyncSessionLocal() as session:
        await ground_vehicle(session, vehicle_id)
        await unground_vehicle(session, vehicle_id, actor_role="Owner")

    async with AsyncSessionLocal() as session:
        fresh = await session.get(Vehicle, vehicle_id)
        assert fresh.status == "Active"


@pytest.mark.asyncio
async def test_ground_vehicle_is_idempotent_guard():
    async with AsyncSessionLocal() as session:
        vehicle = Vehicle(unit_number="E2E-GRD-01", status="Grounded", carrier_id=1)
        session.add(vehicle)
        await session.commit()
        await session.refresh(vehicle)
        vehicle_id = vehicle.id

    with pytest.raises(ValueError):
        async with AsyncSessionLocal() as session:
            await ground_vehicle(session, vehicle_id)


@pytest.mark.asyncio
async def test_report_persisted_after_full_cycle():
    """Sanity check: the driver's repair report survives the whole lifecycle."""
    async with AsyncSessionLocal() as session:
        stmt = select(RepairReport).where(RepairReport.category == "Brakes")
        reports = (await session.execute(stmt)).scalars().all()
    assert len(reports) >= 1
