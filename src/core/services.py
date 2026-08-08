import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.plugins import plugin_registry
from src.core.exceptions import SafetyViolationError
from src.core.models import (
    User,
    Vehicle,
    OdometerLog,
    Load,
    LoadStatusLog,
    RepairReport,
    DutyLog,
)
from src.core.security import get_password_hash

logger = logging.getLogger("fleetscout.plugins")

TEAM_MEMBER_ROLES = ("Dispatcher", "Driver")


async def create_team_member(
    db: AsyncSession,
    carrier_id: int,
    email: str,
    username: str,
    password: str,
    role: str,
) -> User:
    """Provisions a new Dispatcher/Driver account bound to the Owner's carrier.

    Validates the requested role, hashes the temporary password via
    ``get_password_hash()``, and guards against duplicate email/username
    collisions with a user-friendly error. The new ``User`` is committed so
    the Team Roster renders it on the very next rerun.
    """
    if role not in TEAM_MEMBER_ROLES:
        raise ValueError(
            f"Invalid role '{role}'. Choose either 'Dispatcher' or 'Driver'."
        )

    clean_email = (email or "").strip().lower()
    clean_username = (username or "").strip()
    if not clean_email:
        raise ValueError("Email address is required.")
    if not password:
        raise ValueError("Temporary password is required.")

    from sqlalchemy import select

    existing_email = (
        await db.execute(select(User).where(User.email == clean_email))
    ).scalar_one_or_none()
    if existing_email is not None:
        raise ValueError(
            f"An account with email '{clean_email}' already exists. "
            "Choose a different email address."
        )

    if clean_username:
        existing_username = (
            await db.execute(select(User).where(User.username == clean_username))
        ).scalar_one_or_none()
        if existing_username is not None:
            raise ValueError(
                f"Username '{clean_username}' is already taken. "
                "Choose a different username."
            )

    member = User(
        email=clean_email,
        username=clean_username or None,
        hashed_password=get_password_hash(password),
        role=role,
        carrier_id=carrier_id,
        is_active=True,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


async def run_plugin_hook(
    plugin_name: str, data: dict, **kwargs
) -> dict:
    """Execute a registered plugin in complete isolation (Task HD-5.1).

    Guarantees plugin failure can never crash core dispatch: every exception
    is caught, logged, and surfaced as a structured ``{"ok": False, ...}``
    dict. No database transaction is started, altered, or rolled back by a
    plugin hook, so dispatch logic remains deterministic regardless of
    third-party adapter behaviour.
    """
    plugin = plugin_registry.get(plugin_name)
    if plugin is None:
        return {
            "ok": False,
            "plugin": plugin_name,
            "error": f"Plugin '{plugin_name}' is not registered.",
        }
    try:
        if not await plugin.validate():
            return {
                "ok": False,
                "plugin": plugin_name,
                "error": f"Plugin '{plugin_name}' failed validation.",
            }
        result = await plugin.execute(data, **kwargs)
        return {"ok": True, "plugin": plugin_name, "result": result}
    except Exception as exc:  # isolation boundary - never propagates
        logger.exception("Plugin '%s' execution failed", plugin_name)
        return {"ok": False, "plugin": plugin_name, "error": str(exc)}


async def validate_vehicle_readiness(
    session: AsyncSession, vehicle_id: int
) -> Vehicle:
    """Safety interceptor (Task HD-5.2): blocks load assignment to Grounded vehicles.

    Raises SafetyViolationError if the vehicle does not exist or its status is
    'Grounded'. Returns the vehicle when dispatch-ready.
    """
    vehicle = await session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise SafetyViolationError(
            f"Vehicle with ID {vehicle_id} not found. Cannot assign a load."
        )
    if vehicle.status == "Grounded":
        raise SafetyViolationError(
            f"Vehicle {vehicle.unit_number} (ID {vehicle.id}) is Grounded and "
            "cannot be assigned a load. Resolve maintenance before dispatching "
            "this asset."
        )
    return vehicle


def update_vehicle_odometer(
    db: Session, vehicle_id: int, new_reading: int, notes: str = None
) -> OdometerLog:
    """
    Atomically creates an OdometerLog entry and updates Vehicle.current_odometer.
    Enforces that new readings cannot be lower than the current reading.
    """
    # Fetch a fresh, active instance inside the current db session
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise ValueError(f"Vehicle with ID {vehicle_id} not found.")

    if new_reading < vehicle.current_odometer:
        raise ValueError(
            f"Invalid reading ({new_reading:,} miles): Cannot be lower than "
            f"current odometer reading ({vehicle.current_odometer:,} miles)."
        )

    # 1. Create audit log
    log_entry = OdometerLog(
        vehicle_id=vehicle.id, reading=new_reading, notes=notes
    )

    # 2. Update parent vehicle reading
    vehicle.current_odometer = new_reading

    # 3. Commit atomically
    db.add(log_entry)
    db.commit()
    db.refresh(vehicle)
    db.refresh(log_entry)

    return log_entry


async def create_dispatched_load(
    session: AsyncSession,
    load_number: str,
    load_weight: int,
    commodity: str,
    pickup_ref: str,
    delivery_ref: str,
    dispatcher_notes: str = None,
    assigned_driver_id: int = None,
    assigned_vehicle_id: int = None,
    pickup_address: str = None,
    delivery_address: str = None,
    target_pickup_at=None,
    target_delivery_at=None,
) -> Load:
    """Atomically inserts a new Load record with 'dispatched' status."""
    if assigned_vehicle_id is not None:
        try:
            await validate_vehicle_readiness(session, assigned_vehicle_id)
        except SafetyViolationError:
            await session.rollback()
            raise

    db_load = Load(
        load_number=load_number,
        load_weight=load_weight,
        commodity=commodity,
        pickup_ref=pickup_ref,
        delivery_ref=delivery_ref,
        pickup_address=pickup_address,
        delivery_address=delivery_address,
        target_pickup_at=target_pickup_at,
        target_delivery_at=target_delivery_at,
        dispatcher_notes=dispatcher_notes,
        status="dispatched",
        carrier_id=1,
        assigned_driver_id=assigned_driver_id,
        assigned_vehicle_id=assigned_vehicle_id,
    )
    session.add(db_load)
    await session.commit()
    await session.refresh(db_load)
    return db_load


async def dispatch_load_with_plugins(
    session: AsyncSession,
    *,
    load_number: str = None,
    load_weight: int = None,
    commodity: str = None,
    pickup_ref: str = None,
    delivery_ref: str = None,
    dispatcher_notes: str = None,
    assigned_driver_id: int = None,
    assigned_vehicle_id: int = None,
    pickup_address: str = None,
    delivery_address: str = None,
    ratecon_bytes: bytes = None,
    origin: str = None,
    destination: str = None,
    hos_driving_hours: float = None,
    hos_start_time: str = None,
) -> tuple[Load, dict]:
    """Dispatch a load while consulting modular plugin hooks (Task HD-5.1).

    1. ``freightslip`` parses an optional RateCon payload to auto-fill load
       fields (commodity, weight, refs) when the caller left them unset.
    2. ``lanesight`` computes route distance / transit time and, optionally,
       the DOT HOS plan - appended to dispatcher notes as a summary.

    Every plugin call is isolated via ``run_plugin_hook``: a failing or
    misconfigured plugin returns a structured error dict and dispatch simply
    continues with the provided (or defaulted) payload. Plugin hooks never
    raise ``SafetyViolationError`` and never roll back the session. The SD-5.2
    safety interceptor still runs once, inside ``create_dispatched_load``.
    """
    enrichment: dict = {}

    if ratecon_bytes is not None:
        hook = await run_plugin_hook(
            "freightslip", {"action": "parse", "file_bytes": ratecon_bytes}
        )
        enrichment["freightslip"] = hook
        if hook.get("ok"):
            parsed = hook["result"]
            load_number = load_number or parsed.get("load_number")
            load_weight = load_weight or parsed.get("weight")
            commodity = commodity or parsed.get("commodity")
            pickup_ref = pickup_ref or parsed.get("pickup_ref")
            delivery_ref = delivery_ref or parsed.get("delivery_ref")

    notes_bits = []
    if dispatcher_notes:
        notes_bits.append(dispatcher_notes)

    if origin and destination:
        hook = await run_plugin_hook(
            "lanesight", {"action": "route", "origin": origin, "destination": destination}
        )
        enrichment["lanesight"] = hook
        if hook.get("ok"):
            route = hook["result"]
            notes_bits.append(
                "est. {0:,.1f} mi / {1:.2f} hr".format(
                    float(route["distance_miles"]), float(route["duration_hours"])
                )
            )

    if hos_driving_hours is not None and hos_start_time:
        hook = await run_plugin_hook(
            "lanesight",
            {"action": "hos", "driving_hours": hos_driving_hours, "start_time": hos_start_time},
        )
        enrichment["lanesight_hos"] = hook
        if hook.get("ok"):
            hos = hook["result"]
            notes_bits.append(
                "HOS: {} stops / avail {}".format(
                    hos["rest_break_count"],
                    hos["sleeper_berth_reset"]["available_at"],
                )
            )

    load_number = load_number or f"PLG-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    load_weight = load_weight if load_weight is not None else 0
    commodity = commodity or "TBD"
    pickup_ref = pickup_ref or "N/A"
    delivery_ref = delivery_ref or "N/A"

    load = await create_dispatched_load(
        session,
        load_number=load_number,
        load_weight=load_weight,
        commodity=commodity,
        pickup_ref=pickup_ref,
        delivery_ref=delivery_ref,
        dispatcher_notes=" | ".join(notes_bits) if notes_bits else None,
        assigned_driver_id=assigned_driver_id,
        assigned_vehicle_id=assigned_vehicle_id,
        pickup_address=pickup_address,
        delivery_address=delivery_address,
    )
    return load, enrichment


async def update_load_status(
    session: AsyncSession, load_id: int, status: str, gps_lat: float = None, gps_lng: float = None
) -> LoadStatusLog:
    """Sets a Load's active status and logs a timestamped entry (with optional GPS) for the board timeline."""
    load = await session.get(Load, load_id)
    if not load:
        raise ValueError(f"Load with ID {load_id} not found.")

    load.status = status
    log_entry = LoadStatusLog(
        load_id=load.id,
        status=status,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
    )
    session.add(log_entry)
    await session.commit()
    await session.refresh(load)
    await session.refresh(log_entry)
    return log_entry


async def create_repair_report(
    session: AsyncSession,
    driver_id: int,
    category: str,
    description: str = None,
    photo_path: str = None,
    vehicle_id: int = None,
    load_id: int = None,
    gps_lat: float = None,
    gps_lng: float = None,
) -> RepairReport:
    """Atomically persists a structured driver issue report (Task DS-4.3)."""
    report = RepairReport(
        category=category,
        description=description,
        photo_path=photo_path,
        status="reported",
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        load_id=load_id,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def get_recent_repair_reports(
    session: AsyncSession, driver_id: int = None, limit: int = 20
):
    """Returns recent repair reports, optionally filtered to one driver."""
    from sqlalchemy import select

    stmt = select(RepairReport).order_by(RepairReport.created_at.desc()).limit(limit)
    if driver_id is not None:
        stmt = stmt.where(RepairReport.driver_id == driver_id)
    return (await session.execute(stmt)).scalars().all()


# Only Owner/Mechanic roles may release a grounded asset back to the road
# (Task HD-5.3). Dispatchers and drivers cannot override the safety lockout.
UNGROUND_AUTHORIZED_ROLES = ("Owner", "Mechanic")


async def ground_vehicle(session: AsyncSession, vehicle_id: int) -> Vehicle:
    """Flags a vehicle as 'Grounded' (Task HD-5.3 lifecycle).

    Called when a driver reports a safety issue affecting an asset. Once
    grounded, the HD-5.2 interceptor blocks any load assignment until a
    Mechanic/Owner performs the repair and un-grounds the vehicle.
    """
    vehicle = await session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise ValueError(f"Vehicle with ID {vehicle_id} not found.")

    if vehicle.status == "Grounded":
        raise ValueError(f"Vehicle {vehicle.unit_number} is already Grounded.")

    vehicle.status = "Grounded"
    await session.commit()
    await session.refresh(vehicle)
    return vehicle


async def unground_vehicle(
    session: AsyncSession, vehicle_id: int, actor_role: str = None
) -> Vehicle:
    """Sets a grounded vehicle's status back to 'Active' after repairs.

    Strictly restricted to authorized roles (Mechanic/Owner). Callers must
    supply the actor's role — Dispatchers and Drivers cannot release an asset.
    """
    if actor_role not in UNGROUND_AUTHORIZED_ROLES:
        raise PermissionError(
            f"Role '{actor_role}' is not authorized to un-ground vehicles. "
            f"Only {', '.join(UNGROUND_AUTHORIZED_ROLES)} may release an asset."
        )

    vehicle = await session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise ValueError(f"Vehicle with ID {vehicle_id} not found.")

    vehicle.status = "Active"
    await session.commit()
    await session.refresh(vehicle)
    return vehicle


async def get_active_loads(session: AsyncSession):
    """Returns active dispatched loads with driver/vehicle and status-history timeline."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    stmt = (
        select(Load)
        .options(selectinload(Load.driver), selectinload(Load.vehicle), selectinload(Load.status_logs))
        .order_by(Load.created_at.desc())
    )
    return (await session.execute(stmt)).scalars().all()


async def get_driver_briefing(session: AsyncSession, driver_id: int):
    """Returns active loads assigned to a driver, newest first, with vehicle details."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    stmt = (
        select(Load)
        .options(selectinload(Load.vehicle), selectinload(Load.status_logs))
        .where(Load.assigned_driver_id == driver_id)
        .order_by(Load.created_at.desc())
    )
    return (await session.execute(stmt)).scalars().all()


async def log_duty_start(
    session: AsyncSession,
    driver_id: int,
    duty_state: str,
    gps_lat: float = None,
    gps_lng: float = None,
) -> DutyLog:
    """Atomically logs a driver duty-state start (Task DS-4.4).

    When the state is 'Off Duty' or 'Sleeper Berth', the 10-hour availability
    return countdown begins and target_available_at is set accordingly.
    """
    if duty_state not in DutyLog.DUTY_STATES:
        raise ValueError(
            f"Invalid duty state '{duty_state}'. Choose one of {DutyLog.DUTY_STATES}."
        )

    now = datetime.now(timezone.utc)
    rests = {"Off Duty", "Sleeper Berth"}
    off_duty_started_at = now if duty_state in rests else None
    target_available_at = (
        now + timedelta(hours=DutyLog.REST_HOURS) if duty_state in rests else None
    )

    log_entry = DutyLog(
        driver_id=driver_id,
        duty_state=duty_state,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        off_duty_started_at=off_duty_started_at,
        target_available_at=target_available_at,
    )
    session.add(log_entry)
    await session.commit()
    await session.refresh(log_entry)
    return log_entry


async def get_latest_duty_log(session: AsyncSession, driver_id: int) -> DutyLog:
    """Returns the most recent duty log for a driver, or None."""
    from sqlalchemy import select

    stmt = (
        select(DutyLog)
        .where(DutyLog.driver_id == driver_id)
        .order_by(DutyLog.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def get_duty_summary(session: AsyncSession, driver_id: int):
    """Returns a dict summarizing the driver's 10-hour availability countdown.

    Includes the latest duty log, the off-duty start time, the availability
    return time, and the seconds remaining until available (0 if already available).
    """
    latest = await get_latest_duty_log(session, driver_id)
    summary = {
        "latest_log": latest,
        "off_duty_started_at": None,
        "target_available_at": None,
        "seconds_remaining": None,
        "is_resting": False,
    }
    if latest is None:
        return summary

    if latest.target_available_at is None:
        return summary

    now = datetime.now(timezone.utc)
    target = latest.target_available_at
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    seconds_remaining = max(int((target - now).total_seconds()), 0)

    summary.update(
        {
            "off_duty_started_at": latest.off_duty_started_at,
            "target_available_at": target,
            "seconds_remaining": seconds_remaining,
            "is_resting": seconds_remaining > 0,
        }
    )
    return summary


async def get_recent_duty_logs(
    session: AsyncSession, driver_id: int = None, limit: int = 20
):
    """Returns recent duty logs, optionally filtered to one driver."""
    from sqlalchemy import select

    stmt = select(DutyLog).order_by(DutyLog.created_at.desc()).limit(limit)
    if driver_id is not None:
        stmt = stmt.where(DutyLog.driver_id == driver_id)
    return (await session.execute(stmt)).scalars().all()