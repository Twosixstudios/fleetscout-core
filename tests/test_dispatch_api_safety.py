import asyncio

import pytest

from src.core.database import AsyncSessionLocal, Base, sync_engine
from src.core.models import Load, User, Vehicle
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


def _seed_vehicle(unit_number, status="Active"):
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


def _create_load(client, headers, load_number, vehicle_id):
    payload = {
        "load_number": load_number,
        "load_weight": 20000,
        "commodity": "Test Cargo",
        "pickup_ref": "PU-API",
        "delivery_ref": "DEL-API",
        "status": "dispatched",
        "carrier_id": 1,
        "assigned_driver_id": None,
        "assigned_vehicle_id": vehicle_id,
    }
    return client.post("/api/loads", json=payload, headers=headers)


def test_api_assign_to_active_vehicle_succeeds(client):
    """Dispatcher can dispatch a load onto an Active vehicle via the API."""
    _register_user("api-disp-act@fleetscout.com", "Dispatcher")
    vehicle_id = _seed_vehicle("API-ACT-01", status="Active")

    tokens_are_headers = {
        "Authorization": f"Bearer {_token(client, 'api-disp-act@fleetscout.com')}"
    }
    response = _create_load(
        client, tokens_are_headers, "API-LD-ACT-01", vehicle_id
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "dispatched"
    assert body["assigned_vehicle_id"] == vehicle_id


def test_api_assign_to_grounded_vehicle_returns_409(client):
    """HD-5.3: assigning a load to a Grounded vehicle is rejected (409)."""
    _register_user("api-disp-409@fleetscout.com", "Dispatcher")
    vehicle_id = _seed_vehicle("API-GRD-01", status="Grounded")

    headers = {"Authorization": f"Bearer {_token(client, 'api-disp-409@fleetscout.com')}"}
    response = _create_load(client, headers, "API-LD-BLOCKED-01", vehicle_id)
    assert response.status_code == 409
    assert "Grounded" in response.json()["detail"]

    # No load was persisted
    async def _count():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                Load.__table__.select().where(
                    Load.load_number == "API-LD-BLOCKED-01"
                )
            )
            return len(result.all())

    assert asyncio.run(_count()) == 0


def test_api_e2e_ground_block_unground_assign(client):
    """Full HD-5.3 lifecycle through the REST API:
    Driver grounds -> Dispatcher blocked -> Dispatcher/Driver cannot unground ->
    Mechanic ungrounds -> Dispatcher assigns successfully.
    """
    _register_user("driver-api@fleetscout.com", "Driver")
    _register_user("mechanic-api@fleetscout.com", "Mechanic")
    _register_user("dispatcher-api@fleetscout.com", "Dispatcher")
    vehicle_id = _seed_vehicle("API-E2E-LOOP-01", status="Active")

    driver_headers = {"Authorization": f"Bearer {_token(client, 'driver-api@fleetscout.com')}"}
    disp_headers = {"Authorization": f"Bearer {_token(client, 'dispatcher-api@fleetscout.com')}"}
    mech_headers = {"Authorization": f"Bearer {_token(client, 'mechanic-api@fleetscout.com')}"}

    # 1. Driver (via the report/ground endpoint) grounds the truck
    response = client.post(f"/api/vehicles/{vehicle_id}/ground", headers=driver_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "Grounded"

    # 2. Dispatcher attempt is physically blocked (409 hard lockout)
    response = _create_load(client, disp_headers, "API-LD-E2E-01", vehicle_id)
    assert response.status_code == 409
    assert "Grounded" in response.json()["detail"]

    # 3a. Dispatcher cannot un-ground (403 role guard); asset stays Grounded
    response = client.post(f"/api/vehicles/{vehicle_id}/unground", headers=disp_headers)
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()

    # 3b. Mechanic performs the repair and releases the asset
    response = client.post(f"/api/vehicles/{vehicle_id}/unground", headers=mech_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "Active"

    # 4. Dispatcher assignment now succeeds
    response = _create_load(client, disp_headers, "LOAD-E-E-UNBLOCKED", vehicle_id)
    assert response.status_code == 200
    assert response.json()["status"] == "dispatched"
    assert response.json()["assigned_vehicle_id"] == vehicle_id