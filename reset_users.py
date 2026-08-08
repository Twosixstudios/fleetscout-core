from src.core.database import SessionLocal, sync_engine, Base
from src.core.models import User, Vehicle, Load, LoadStatusLog
from src.core.security import get_password_hash, verify_password

# 1. Ensure tables exist on the active database
Base.metadata.create_all(bind=sync_engine)

db = SessionLocal()

# 2. Clear existing assignments, loads, and users to start fresh
db.query(LoadStatusLog).delete()
db.query(Load).delete()
db.query(User).delete()
db.commit()

# 3. Hash the test password
pwd_hash = get_password_hash("password123")

# 4. Create test accounts
owner = User(
    email="owner@twosix.com",
    username="owner@twosix.com",
    hashed_password=pwd_hash,
    role="Owner",
    carrier_id=1,
)
dispatcher = User(
    email="dispatcher@twosix.com",
    username="dispatcher@twosix.com",
    hashed_password=pwd_hash,
    role="Dispatcher",
    carrier_id=1,
)
driver = User(
    email="driver@twosix.com",
    username="driver@twosix.com",
    hashed_password=pwd_hash,
    role="Driver",
    carrier_id=1,
)

db.add_all([owner, dispatcher, driver])
db.commit()

# Resolve the primary driver so the seeded load below can be assigned
driver = db.query(User).filter_by(email="driver@twosix.com").first()

# 4b. Ensure an Active vehicle exists so the driver load can be assigned
truck = db.query(Vehicle).filter_by(status="Active").first()
if truck is None:
    truck = Vehicle(unit_number="TRK001", status="Active", carrier_id=1)
    db.add(truck)
    db.commit()

# 4c. Seed an active dispatched load for the primary driver so the
# One-Tap Status Toggles render for the test login.
dispatch = db.query(Load).filter_by(assigned_driver_id=driver.id).first()
if dispatch is None:
    dispatch = Load(
        load_number="LD-TEST-1",
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
    db.commit()
    db.add(LoadStatusLog(load_id=dispatch.id, status="dispatched"))
    db.commit()

print("✅ Database refreshed successfully!\n")

# 5. Direct verification check
print("--- USER VERIFICATION AUDIT ---")
for email in ["owner@twosix.com", "dispatcher@twosix.com", "driver@twosix.com"]:
    u = db.query(User).filter_by(email=email).first()
    if u:
        is_valid = verify_password("password123", u.hashed_password)
        print(f"User: {u.email:<22} | Role: {u.role:<10} | Password Match: {is_valid}")
    else:
        print(f"❌ Missing user: {email}")

active_loads = db.query(Load).filter_by(assigned_driver_id=driver.id).all()
print("\n--- ACTIVE DRIVER LOAD AUDIT ---")
if active_loads:
    for l in active_loads:
        print(f"Load: {l.load_number:<12} | Status: {l.status:<10} | Assigned to: {driver.email}")
else:
    print("❌ No active load assigned to " + driver.email)

db.close()
