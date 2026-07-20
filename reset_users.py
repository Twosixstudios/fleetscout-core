from src.core.database import SessionLocal, sync_engine, Base
from src.core.models import User
from src.core.security import get_password_hash, verify_password

# 1. Ensure tables exist on the active database
Base.metadata.create_all(bind=sync_engine)

db = SessionLocal()

# 2. Clear existing users to start fresh
db.query(User).delete()
db.commit()

# 3. Hash the test password
pwd_hash = get_password_hash("password123")

# 4. Create test accounts
test_users = [
    User(
        email="owner@twosix.com",
        username="owner@twosix.com",
        hashed_password=pwd_hash,
        role="Owner",
        carrier_id=1,
    ),
    User(
        email="dispatcher@twosix.com",
        username="dispatcher@twosix.com",
        hashed_password=pwd_hash,
        role="Dispatcher",
        carrier_id=1,
    ),
    User(
        email="driver@twosix.com",
        username="driver@twosix.com",
        hashed_password=pwd_hash,
        role="Driver",
        carrier_id=1,
    ),
]

db.add_all(test_users)
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

db.close()