import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from src.core.database import AsyncSessionLocal, sync_engine, Base
from src.core.models import User, Vehicle, Load, LoadStatusLog, Carrier
from src.core.security import get_password_hash

def reset_database():
    """Drop and recreate all database tables using the synchronous engine."""
    Base.metadata.drop_all(bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)

async def _get_or_none(db, model, field, value):
    result = await db.execute(select(model).where(getattr(model, field) == value))
    return result.scalar_one_or_none()

async def seed_database():
    """Idempotently seed the baseline demo assets (FIX-6.2).

    Creates tables if missing, then inserts the baseline Carrier,
    Owner/Dispatcher/Driver accounts, Vehicles, and Active Loads using a
    get-or-create guard so reruns against an already-seeded database never
    raise primary key or unique constraint exceptions.
    """
    Base.metadata.create_all(bind=sync_engine)

    async with AsyncSessionLocal() as db:
        try:
            # 1. Seed the baseline Carrier FIRST so users/loads can link to it.
            if await _get_or_none(db, Carrier, "id", 1) is None:
                db.add(
                    Carrier(
                        id=1,
                        name="Two-Six Logistics LLC",
                        dot_number="USDOT-3829104",
                    )
                )

            # 2. Seed demo Users NEXT (get-or-create by unique email).
            demo_users = [
                ("owner@fleetscout.com", "owner", "Owner"),
                ("dispatcher@fleetscout.com", "dispatcher1", "Dispatcher"),
                ("driver@fleetscout.com", "driver", "Driver"),
                ("driver@twosix.com", "driver2", "Driver"),
            ]
            created_users = {}
            for email, username, role in demo_users:
                user = await _get_or_none(db, User, "email", email)
                if user is None:
                    user = User(
                        email=email,
                        username=username,
                        hashed_password=get_password_hash("password123"),
                        role=role,
                        carrier_id=1,
                    )
                    db.add(user)
                    await db.flush()
                created_users[email] = user

            # 3. Seed Vehicles (get-or-create by unit number).
            truck_specs = [
                ("TRK001", "Active"),
                ("TRK002", "Grounded"),
                ("TRK003", "Active"),
            ]
            trucks = {}
            for unit_number, status in truck_specs:
                truck = await _get_or_none(db, Vehicle, "unit_number", unit_number)
                if truck is None:
                    truck = Vehicle(unit_number=unit_number, status=status, carrier_id=1)
                    db.add(truck)
                    await db.flush()
                trucks[unit_number] = truck

            # 4. Seed Active Loads (get-or-create by load number).
            load_specs = [
                Load(
                    load_number="LD-8801",
                    load_weight=42000.0,
                    commodity="Refrigerated Goods",
                    status="dispatched",
                    carrier_id=1,
                    assigned_driver_id=created_users["driver@fleetscout.com"].id,
                    assigned_vehicle_id=trucks["TRK001"].id,
                    pickup_ref="PU-1001",
                    delivery_ref="DEL-2002",
                    pickup_address="1234 Citrus Ave, Fresno, CA",
                    delivery_address="899 Market St, San Francisco, CA",
                    target_pickup_at=datetime.now(timezone.utc) + timedelta(hours=2),
                    target_delivery_at=datetime.now(timezone.utc) + timedelta(hours=12),
                    dispatcher_notes="Reefer must stay at 34F the whole run. Call dispatch on arrival.",
                ),
                Load(
                    load_number="LD-8802",
                    load_weight=38000.0,
                    commodity="Auto Parts",
                    status="dispatched",
                    carrier_id=1,
                    assigned_driver_id=created_users["driver@twosix.com"].id,
                    assigned_vehicle_id=trucks["TRK003"].id,
                    pickup_ref="PU-2001",
                    delivery_ref="DEL-3003",
                    pickup_address="777 Commerce Blvd, Los Angeles, CA",
                    delivery_address="1200 Harbor Dr, San Diego, CA",
                    target_pickup_at=datetime.now(timezone.utc) + timedelta(hours=3),
                    target_delivery_at=datetime.now(timezone.utc) + timedelta(hours=14),
                    dispatcher_notes="Two-Six load must arrive before warehouse close.",
                ),
            ]
            for load in load_specs:
                if await _get_or_none(db, Load, "load_number", load.load_number) is None:
                    db.add(load)
                    await db.flush()
                    db.add(
                        LoadStatusLog(
                            load_id=load.id,
                            status="dispatched",
                            timestamp=datetime.now(timezone.utc),
                        )
                    )
            await db.commit()

            print("Database successfully seeded with baseline assets!")
        except Exception as e:
            await db.rollback()
            print(f"Seeding failed: {e}")
            raise


async def ensure_database_seeded() -> bool:
    """FIX-6.2 self-healing startup check.

    Counts rows in the User table and, when it finds an empty database
    (e.g. first boot on Streamlit Cloud), seeds the baseline Owner
    (owner@fleetscout.com), Dispatcher, Driver, Carrier, Vehicle, and
    Active Load records. Returns True when seeding was triggered.
    """
    Base.metadata.create_all(bind=sync_engine)
    async with AsyncSessionLocal() as db:
        count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
        if count == 0:
            await seed_database()
            return True
    return False

if __name__ == "__main__":
    reset_database()
    asyncio.run(seed_database())