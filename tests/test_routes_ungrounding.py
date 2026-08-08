import asyncio

import pytest

from src.core.database import AsyncSessionLocal, Base, sync_engine
from src.core.models import User, Vehicle
from src.core.security import get_password_hash


def _register_user(email, role, password="password123"):
    async def _mutate():
        async with AsyncSessionLocal() as session:
            user = User(
                email=email,
                username=email.split("@")[0],
                hashed_password=get_password_hash(password),
                role=role,
                carrier_id=1,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user.id

    return asyncio.run(_mutate())


def _seed_vehicle(unit_number, status="Grounded"):
    async def _mutate():
        async with AsyncSessionLocal() as session:
            vehicle = Vehicle(unit_number=unit_number, status=status, carrier_id=1)
            session.add(vehicle)
            await session.commit()
            await session.refresh(vehicle)
            return vehicle.id

    return asyncio.run(_mutate())


def _token(client, email, password="password123"):
    response = client.post(
        "/api/auth/token",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(scope="module", autouse=True)
def reset_schema():
    Base.metadata.drop_all(bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)


def test_ground_endpoint_grounds_active_vehicle(client):
    """An authenticated report can ground an active asset via the API."""
    _register_user("api-mech@fleetscout.com", "Mechanic")
    vehicle_id = _seed_vehicle("API-GRP-01", status="Active")

    headers = {"Authorization": f"Bearer {_token(client, 'api-mech@fleetscout.com')}"}
    response = client.post(f"/api/vehicles/{vehicle_id}/ground", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "Grounded"


def test_unground_endpoint_forbids_dispatcher(client):
    """Dispatcher role is denied the un-ground action (403)."""
    _register_user("api-disp@fleetscout.com", "Dispatcher")
    vehicle_id = _seed_vehicle("API-UNG-01")

    headers = {"Authorization": f"Bearer {_token(client, 'api-disp@fleetscout.com')}"}
    response = client.post(f"/api/vehicles/{vehicle_id}/unground", headers=headers)
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()

    # Asset remains grounded after the rejected attempt
    response = client.get("/api/vehicles", headers=headers)
    vehicles = response.json()
    grounded = next(v for v in vehicles if v["id"] == vehicle_id)
    assert grounded["status"] == "Grounded"


def test_unground_endpoint_allows_mechanic(client):
    """A mechanic role can release the grounded asset."""
    _register_user("api-mech2@fleetscout.com", "Mechanic")
    vehicle_id = _seed_vehicle("API-UNG-02")

    headers = {"Authorization": f"Bearer {_token(client, 'api-mech2@fleetscout.com')}"}
    response = client.post(f"/api/vehicles/{vehicle_id}/unground", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "Active"


def test_unground_endpoint_allows_owner(client):
    """Owner is an authorized un-ground role."""
    _register_user("api-owner@fleetscout.com", "Owner")
    vehicle_id = _seed_vehicle("API-UNG-03")

    headers = {"Authorization": f"Bearer {_token(client, 'api-owner@fleetscout.com')}"}
    response = client.post(f"/api/vehicles/{vehicle_id}/unground", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "Active"