import asyncio
from sqlalchemy import delete
from src.core.database import AsyncSessionLocal
from src.core.models import User, Vehicle

async def seed_database():
    async with AsyncSessionLocal() as db:
        try:
            # 1. Clear existing data to ensure a clean seed environment
            await db.execute(delete(User))
            await db.execute(delete(Vehicle))
            await db.commit()

            # 2. Seed Default Vehicles
            truck1 = Vehicle(unit_number="TRK001", status="Active", carrier_id=1)
            truck2 = Vehicle(unit_number="TRK002", status="Active", carrier_id=1)
            db.add_all([truck1, truck2])

            # 3. Seed Sample Users (Dispatcher and Driver)
            dispatcher = User(
                email="dispatcher@fleetscout.com",
                username="dispatcher1",
                hashed_password="default_mock_password_hash",
                role="Dispatcher",
                carrier_id=1
            )
            driver = User(
                email="driver@fleetscout.com",
                username="driver1",
                hashed_password="default_mock_password_hash",
                role="Driver",
                carrier_id=1
            )
            db.add_all([dispatcher, driver])
            
            await db.commit()
            print("✅ Database successfully seeded with baseline assets!")
        except Exception as e:
            await db.rollback()
            print(f"❌ Seeding failed: {e}")

if __name__ == "__main__":
    asyncio.run(seed_database())