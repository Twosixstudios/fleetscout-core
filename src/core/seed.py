import asyncio
from datetime import datetime, timedelta, timezone
from src.core.database import AsyncSessionLocal, sync_engine, Base
from src.core.models import User, Vehicle, Load, LoadStatusLog, Carrier
from src.core.security import get_password_hash

def reset_database():
    """Drop and recreate all database tables using the synchronous engine."""
    Base.metadata.drop_all(bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)

async def seed_database():
    # 1. Fresh schema reset
    reset_database()
    
    async with AsyncSessionLocal() as db:
        try:
            # 2. Seed the baseline Carrier FIRST so users/loads can link to it.
            carrier = Carrier(
                id=1,
                name="Two-Six Logistics LLC",
                dot_number="USDOT-3829104",
            )
            db.add(carrier)

            # 3. Seed Users NEXT so their IDs exist
            owner = User(
                id=1,
                email="owner@fleetscout.com",
                username="owner",
                hashed_password=get_password_hash("password123"),
                role="Owner",
                carrier_id=1,
            )
            dispatcher = User(
                id=2,
                email="dispatcher@fleetscout.com",
                username="dispatcher1",
                hashed_password=get_password_hash("password123"),
                role="Dispatcher",
                carrier_id=1
            )
            driver1 = User(
                id=3,
                email="driver@fleetscout.com",
                username="driver",
                hashed_password=get_password_hash("password123"),
                role="Driver",
                carrier_id=1
            )
            driver2 = User(
                id=4,
                email="driver@twosix.com",
                username="driver2",
                hashed_password=get_password_hash("password123"),
                role="Driver",
                carrier_id=1
            )
            db.add_all([owner, dispatcher, driver1, driver2])
            await db.commit()

            # 3. Seed Vehicles (two Active for the two drivers, one Grounded)
            truck1 = Vehicle(unit_number="TRK001", status="Active", carrier_id=1)
            truck2 = Vehicle(unit_number="TRK002", status="Grounded", carrier_id=1)
            truck3 = Vehicle(unit_number="TRK003", status="Active", carrier_id=1)
            db.add_all([truck1, truck2, truck3])
            await db.commit()

            # 4. Seed Active Load (linking Driver #2 and Truck #1 AFTER both exist)
            load1 = Load(
                load_number="LD-8801",
                load_weight=42000.0,
                commodity="Refrigerated Goods",
                status="dispatched",
                carrier_id=1,
                assigned_driver_id=driver1.id,
                assigned_vehicle_id=truck1.id,
                pickup_ref="PU-1001",
                delivery_ref="DEL-2002",
                pickup_address="1234 Citrus Ave, Fresno, CA",
                delivery_address="899 Market St, San Francisco, CA",
                target_pickup_at=datetime.now(timezone.utc) + timedelta(hours=2),
                target_delivery_at=datetime.now(timezone.utc) + timedelta(hours=12),
                dispatcher_notes="Reefer must stay at 34F the whole run. Call dispatch on arrival."
            )
            db.add(load1)
            await db.commit()

            # Seed an initial status log so the watch board and status
            # toggles render a timestamped timeline for the fresh dispatch.
            db.add(
                LoadStatusLog(
                    load_id=load1.id,
                    status="dispatched",
                    timestamp=datetime.now(timezone.utc),
                )
            )
            await db.commit()

            # 5. Seed a second Active Load for Driver #2 (driver@twosix.com)
            load2 = Load(
                load_number="LD-8802",
                load_weight=38000.0,
                commodity="Auto Parts",
                status="dispatched",
                carrier_id=1,
                assigned_driver_id=driver2.id,
                assigned_vehicle_id=truck3.id,
                pickup_ref="PU-2001",
                delivery_ref="DEL-3003",
                pickup_address="777 Commerce Blvd, Los Angeles, CA",
                delivery_address="1200 Harbor Dr, San Diego, CA",
                target_pickup_at=datetime.now(timezone.utc) + timedelta(hours=3),
                target_delivery_at=datetime.now(timezone.utc) + timedelta(hours=14),
                dispatcher_notes="Two-Six load must arrive before warehouse close."
            )
            db.add(load2)
            await db.commit()

            db.add(
                LoadStatusLog(
                    load_id=load2.id,
                    status="dispatched",
                    timestamp=datetime.now(timezone.utc),
                )
            )
            await db.commit()

            print("Database successfully seeded with baseline assets!")
        except Exception as e:
            await db.rollback()
            print(f"Seeding failed: {e}")

if __name__ == "__main__":
    asyncio.run(seed_database())
