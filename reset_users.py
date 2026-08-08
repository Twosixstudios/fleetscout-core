import asyncio
from sqlalchemy import select
from src.core.database import AsyncSessionLocal, sync_engine, Base
from src.core.models import User, Vehicle, Load, LoadStatusLog
from src.core.security import get_password_hash, verify_password

# 1. Ensure tables exist on the active database
Base.metadata.create_all(bind=sync_engine)


async def reset_users():
    async with AsyncSessionLocal() as db:
        # 2. Clear existing assignments, loads, and users to start fresh
        await db.execute(LoadStatusLog.__table__.delete())
        await db.execute(Load.__table__.delete())
        await db.execute(User.__table__.delete())
        await db.commit()

        # 3. Hash the test password
        pwd_hash = get_password_hash("password123")

        # 4. Create the canonical test accounts
        dispatcher = User(
            email="dispatcher@fleetscout.com",
            username="dispatcher1",
            hashed_password=pwd_hash,
            role="Dispatcher",
            carrier_id=1,
        )
        driver1 = User(
            email="driver@fleetscout.com",
            username="driver",
            hashed_password=pwd_hash,
            role="Driver",
            carrier_id=1,
        )
        driver2 = User(
            email="driver@twosix.com",
            username="driver2",
            hashed_password=pwd_hash,
            role="Driver",
            carrier_id=1,
        )

        db.add_all([dispatcher, driver1, driver2])
        await db.commit()

        # Resolve drivers so the seeded loads below can be assigned
        driver1 = (
            await db.execute(select(User).where(User.email == "driver@fleetscout.com"))
        ).scalar_one()
        driver2 = (
            await db.execute(select(User).where(User.email == "driver@twosix.com"))
        ).scalar_one()

        # 4b. Ensure two Active vehicles exist so each driver load can be assigned
        truck1 = (
            await db.execute(select(Vehicle).where(Vehicle.unit_number == "TRK001"))
        ).scalar_one_or_none()
        if truck1 is None:
            truck1 = Vehicle(unit_number="TRK001", status="Active", carrier_id=1)
            db.add(truck1)
        truck3 = (
            await db.execute(select(Vehicle).where(Vehicle.unit_number == "TRK003"))
        ).scalar_one_or_none()
        if truck3 is None:
            truck3 = Vehicle(unit_number="TRK003", status="Active", carrier_id=1)
            db.add(truck3)
        await db.commit()

        # 4c. Seed an active dispatched load for each driver so the
        # One-Tap Status Toggles render for the test logins.
        for load_number, driver, truck in [
            ("LD-TEST-1", driver1, truck1),
            ("LD-TEST-2", driver2, truck3),
        ]:
            dispatch = (
                await db.execute(
                    select(Load).where(Load.assigned_driver_id == driver.id)
                )
            ).scalar_one_or_none()
            if dispatch is None:
                dispatch = Load(
                    load_number=load_number,
                    load_weight=35000,
                    commodity="Test Cargo",
                    pickup_ref="PU-1001",
                    delivery_ref="DEL-2002",
                    pickup_address="1234 Citrus Ave, Fresno, CA",
                    delivery_address="899 Market St, San Francisco, CA",
                    dispatcher_notes="Assigned by reset_users.py so driver status toggles render.",
                    status="dispatched",
                    carrier_id=1,
                    assigned_driver_id=driver.id,
                    assigned_vehicle_id=truck.id,
                )
                db.add(dispatch)
                await db.commit()
                db.add(LoadStatusLog(load_id=dispatch.id, status="dispatched"))
                await db.commit()

        print("✅ Database refreshed successfully!\n")

        # 5. Direct verification check
        print("--- USER VERIFICATION AUDIT ---")
        for email in ["dispatcher@fleetscout.com", "driver@fleetscout.com", "driver@twosix.com"]:
            u = (
                await db.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if u:
                is_valid = verify_password("password123", u.hashed_password)
                print(f"User: {u.email:<22} | Role: {u.role:<10} | Password Match: {is_valid}")
            else:
                print(f"❌ Missing user: {email}")

        for driver in [driver1, driver2]:
            active_loads = (
                await db.execute(
                    select(Load).where(Load.assigned_driver_id == driver.id)
                )
            ).scalars().all()
            print(f"\n--- ACTIVE DRIVER LOAD AUDIT ({driver.email}) ---")
            if active_loads:
                for load in active_loads:
                    print(
                        f"  Load: {load.load_number:<12} | Status: {load.status:<10} "
                        f"| Assigned to: {driver.email}"
                    )
            else:
                print("  ❌ No active load assigned to " + driver.email)


if __name__ == "__main__":
    asyncio.run(reset_users())