from sqlalchemy.orm import Session
from src.core.models import Vehicle, OdometerLog


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