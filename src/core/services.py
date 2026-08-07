from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.models import Vehicle, OdometerLog, Load, LoadStatusLog, RepairReport


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