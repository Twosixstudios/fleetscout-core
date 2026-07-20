import pytest
from datetime import timedelta
from jose import jwt, JWTError
from src.core.security import get_password_hash, verify_password, create_access_token

def test_password_hashing():
    password = "fleet_secure_password_123"
    hashed = get_password_hash(password)
    
    # Assert hash is not plaintext
    assert hashed != password
    # Assert verification succeeds with correct password
    assert verify_password(password, hashed) is True
    # Assert verification fails with incorrect password
    assert verify_password("wrong_password", hashed) is False

def test_create_access_token():
    payload_data = {"sub": "dispatcher@fleetscout.com", "role": "Dispatcher", "carrier_id": 1}
    token = create_access_token(data=payload_data, expires_delta=timedelta(minutes=15))
    
    assert isinstance(token, str)
    assert len(token) > 0

    # Test decoding the generated token to ensure payload integrity
    # We will use temporary dummy credentials for verification structure
    try:
        # Note: 'SECRET_KEY' and 'ALGORITHM' will be managed via src.core.config
        from src.core.config import settings
        secret = settings.SECRET_KEY
        algo = settings.ALGORITHM
    except (ImportError, AttributeError):
        secret = "TEST_SECRET_KEY_FALLBACK_FOR_SECURITY_ISOLATION_XYZ123"
        algo = "HS256"

    decoded_data = jwt.decode(token, secret, algorithms=[algo])
    assert decoded_data.get("sub") == "dispatcher@fleetscout.com"
    assert decoded_data.get("role") == "Dispatcher"
    assert decoded_data.get("carrier_id") == 1