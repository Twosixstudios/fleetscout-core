from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.exceptions import SafetyViolationError
from src.core.models import (
    Vehicle,
    OdometerLog,
    Load,
    LoadStatusLog,
    RepairReport,
    DutyLog,
)


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


async def unground_vehicle(
    session: AsyncSession, vehicle_id: int
) -> Vehicle:
    """Sets a grounded vehicle's status back to 'Active' after repairs."""
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
        .options(selectinload(Load.vehicle))
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