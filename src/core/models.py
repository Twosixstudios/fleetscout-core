from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
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


class Load(Base):
    __tablename__ = "loads"

    id = Column(Integer, primary_key=True, index=True)
    load_number = Column(String, unique=True, index=True, nullable=False)
    load_weight = Column(Integer, nullable=False)
    commodity = Column(String, index=True, nullable=False)
    pickup_ref = Column(String, nullable=False)
    delivery_ref = Column(String, nullable=False)
    dispatcher_notes = Column(String, nullable=True)
    status = Column(String, default="unassigned", nullable=False)
    carrier_id = Column(Integer, default=1, nullable=False)
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