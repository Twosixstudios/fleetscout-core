import asyncio
from src.core.database import AsyncSessionLocal, sync_engine
from src.core.database import AsyncSessionLocal, sync_engine, Base
from src.core.models import User, Vehicle, Load

def reset_database():
    """Drop and recreate all database tables using the synchronous engine."""
    Base.metadata.drop_all(bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)

async def seed_database():
    # 1. Fresh schema reset
    reset_database()
    
    async with AsyncSessionLocal() as db:
        try:
            # 2. Seed Users FIRST so their IDs exist
            dispatcher = User(
                id=1,
                email="dispatcher@fleetscout.com",
                username="dispatcher1",
                hashed_password="default_mock_password_hash",
                role="Dispatcher",
                carrier_id=1
            )
            driver1 = User(
                id=2,
                email="driver1@fleetscout.com",
                username="driver1",
                hashed_password="default_mock_password_hash",
                role="Driver",
                carrier_id=1
            )
            db.add_all([dispatcher, driver1])
            await db.commit()

            # 3. Seed Vehicles
            truck1 = Vehicle(unit_number="TRK001", status="Active", carrier_id=1)
            truck2 = Vehicle(unit_number="TRK002", status="Grounded", carrier_id=1)
            db.add_all([truck1, truck2])
            await db.commit()

            # 4. Seed Active Load (linking Driver #2 and Truck #1 AFTER both exist)
            load1 = Load(
                load_number="LD-8801",
                load_weight=42000.0,
                commodity="Refrigerated Goods",
                status="In Transit",
                carrier_id=1,
                assigned_driver_id=driver1.id,
                assigned_vehicle_id=truck1.id,
                pickup_ref="PU-1001",
                delivery_ref="DEL-2002"
            )
            db.add(load1)
            await db.commit()

            print("Database successfully seeded with baseline assets!")
        except Exception as e:
            await db.rollback()
            print(f"Seeding failed: {e}")

if __name__ == "__main__":
    asyncio.run(seed_database())
