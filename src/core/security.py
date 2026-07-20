from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt
import bcrypt

try:
    from src.core.config import settings
    SECRET_KEY = settings.SECRET_KEY
    ALGORITHM = settings.ALGORITHM
except (ImportError, AttributeError):
    SECRET_KEY = "TEST_SECRET_KEY_FALLBACK_FOR_SECURITY_ISOLATION_XYZ123"
    ALGORITHM = "HS256"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)