import pytest

@pytest.mark.asyncio
async def test_user_registration(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "password123"}
    )
    assert response.status_code in (200, 201)