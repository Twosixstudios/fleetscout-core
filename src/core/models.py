from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from src.core.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    unit_number = Column(String, unique=True, index=True, nullable=False)
    vin = Column(String, unique=True, index=True, nullable=True)
    make = Column(String, nullable=True)
    model = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    current_odometer = Column(Integer, default=0, nullable=False)
    status = Column(String, default="Active", nullable=False)
    carrier_id = Column(Integer, default=1, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # ORM Relationship (Audit logs preserved - no delete-orphan cascade)
    odometer_logs = relationship("OdometerLog", back_populates="vehicle")

    # New relationship for assigned loads
    assigned_loads = relationship("Load", back_populates="vehicle")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String, default="Driver", nullable=False)
    carrier_id = Column(Integer, default=1, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # New relationship for assigned loads
    assigned_loads = relationship("Load", back_populates="driver")


class Load(Base):
    __tablename__ = "loads"

    id = Column(Integer, primary_key=True, index=True)
    load_number = Column(String, unique=True, index=True, nullable=False)
    load_weight = Column(Integer, nullable=False)
    commodity = Column(String, index=True, nullable=False)
    pickup_ref = Column(String, nullable=False)
    delivery_ref = Column(String, nullable=False)
    pickup_address = Column(String, nullable=True)
    delivery_address = Column(String, nullable=True)
    target_pickup_at = Column(DateTime, nullable=True)
    target_delivery_at = Column(DateTime, nullable=True)
    dispatcher_notes = Column(String, nullable=True)
    status = Column(String, default="unassigned", nullable=False)
    carrier_id = Column(Integer, default=1, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # New columns for assignments
    assigned_driver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)

    # ORM Relationships
    driver = relationship("User", back_populates="assigned_loads")
    vehicle = relationship("Vehicle", back_populates="assigned_loads")
    status_logs = relationship("LoadStatusLog", back_populates="load")


class LoadStatusLog(Base):
    __tablename__ = "load_status_logs"

    id = Column(Integer, primary_key=True, index=True)
    load_id = Column(Integer, ForeignKey("loads.id"), nullable=False)
    status = Column(String, nullable=False)
    gps_lat = Column(Float, nullable=True)
    gps_lng = Column(Float, nullable=True)
    timestamp = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # ORM Relationship
    load = relationship("Load", back_populates="status_logs")


class Carrier(Base):
    """Baseline carrier branding record (Task TASK-6.1).

    Stores the white-label values rendered in the app header and pre-populated
    into the Owner Portal carrier settings form. Falls back to the demo
    defaults if no row exists yet.
    """

    __tablename__ = "carriers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, default="Two-Six Logistics LLC")
    dot_number = Column(String, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


class OdometerLog(Base):
    __tablename__ = "odometer_logs"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    reading = Column(Integer, nullable=False)
    notes = Column(String, nullable=True)
    logged_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # ORM Relationship
    vehicle = relationship("Vehicle", back_populates="odometer_logs")


class RepairReport(Base):
    """Structured mobile issue report submitted by a driver (Task DS-4.3)."""

    __tablename__ = "repair_reports"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False)
    description = Column(String, nullable=True)
    photo_path = Column(String, nullable=True)
    status = Column(String, default="reported", nullable=False)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    load_id = Column(Integer, ForeignKey("loads.id"), nullable=True)
    gps_lat = Column(Float, nullable=True)
    gps_lng = Column(Float, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # ORM Relationships
    driver = relationship("User")
    vehicle = relationship("Vehicle")
    load = relationship("Load")

    # Task DS-4.3 approved categories
    REPAIR_CATEGORIES = ("Brakes", "Tires", "Lights", "Engine Light", "Trailer")


class UserInvite(Base):
    """Onboarding invitation issued by an Owner to a recruit (Task TASK-6.3).

    A pending invite stores the target email, intended role, and a one-time
    redemption token. A recruit redeems the token on the public registration
    screen to create an active Team Member account bound to the owner's
    carrier network. Once redeemed the record is marked 'Accepted' so the
    same token cannot create a second account.
    """

    __tablename__ = "user_invites"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False)
    carrier_id = Column(Integer, nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default="Pending", nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Task TASK-6.3 invite lifecycle states
    INVITE_STATUSES = ("Pending", "Accepted")


class DutyLog(Base):
    """Driver hours-of-service duty entry for the reset planner (Task DS-4.4).

    Logs a duty-state start. When a driver goes 'Off Duty' or 'Sleeper Berth',
    the 10-hour availability return countdown begins (target_available_at).
    """

    __tablename__ = "duty_logs"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    duty_state = Column(String, nullable=False)
    gps_lat = Column(Float, nullable=True)
    gps_lng = Column(Float, nullable=True)
    off_duty_started_at = Column(DateTime, nullable=True)
    target_available_at = Column(DateTime, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # ORM relationship
    driver = relationship("User")

    # Task DS-4.4 approved duty states
    DUTY_STATES = ("Driving", "On Duty (not driving)", "Off Duty", "Sleeper Berth")

    # Hours of Service 10-hour rest rule
    REST_HOURS = 10
