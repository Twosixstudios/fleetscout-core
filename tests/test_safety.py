import pytest

from sqlalchemy import select

from src.core.database import Base, sync_engine, AsyncSessionLocal
from src.core.exceptions import SafetyViolationError
from src.core.models import Load, Vehicle
from src.core.services import create_dispatched_load


@pytest.fixture(scope="module", autouse=True)
def reset_schema():
    Base.metadata.drop_all(bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)


@pytest.mark.asyncio
async def test_assign_load_to_active_vehicle_succeeds():
    async with AsyncSessionLocal() as session:
        vehicle = Vehicle(unit_number="SAFE-ACTIVE", status="Active", carrier_id=1)
        session.add(vehicle)
        await session.commit()
        await session.refresh(vehicle)
        vehicle_id = vehicle.id

    async with AsyncSessionLocal() as session:
        load = await create_dispatched_load(
            session,
            load_number="SAFE-LD-ACTIVE-1",
            load_weight=20000,
            commodity="Test Cargo",
            pickup_ref="PU-SAFE",
            delivery_ref="DEL-SAFE",
            assigned_vehicle_id=vehicle_id,
        )

    assert load is not None
    assert load.status == "dispatched"
    assert load.assigned_vehicle_id == vehicle_id

    async with AsyncSessionLocal() as session:
        fresh_load = await session.get(Load, load.id)
        assert fresh_load is not None
        assert fresh_load.assigned_vehicle_id == vehicle_id


@pytest.mark.asyncio
async def test_assign_load_to_grounded_vehicle_raises_safety_violation():
    async with AsyncSessionLocal() as session:
        vehicle = Vehicle(unit_number="SAFE-GROUNDED", status="Grounded", carrier_id=1)
        session.add(vehicle)
        await session.commit()
        await session.refresh(vehicle)
        vehicle_id = vehicle.id

    with pytest.raises(SafetyViolationError) as exc_info:
        async with AsyncSessionLocal() as session:
            await create_dispatched_load(
                session,
                load_number="SAFE-LD-BLOCKED-1",
                load_weight=20000,
                commodity="Test Cargo",
                pickup_ref="PU-SAFE",
                delivery_ref="DEL-SAFE",
                assigned_vehicle_id=vehicle_id,
            )

    message = str(exc_info.value)
    assert "Grounded" in message
    assert f"ID {vehicle_id}" in message


@pytest.mark.asyncio
async def test_transaction_rolls_back_on_blocked_assignment():
    async with AsyncSessionLocal() as session:
        vehicle = Vehicle(
            unit_number="SAFE-ROLLBACK", status="Grounded", carrier_id=1
        )
        session.add(vehicle)
        await session.commit()
        await session.refresh(vehicle)
        vehicle_id = vehicle.id

    with pytest.raises(SafetyViolationError):
        async with AsyncSessionLocal() as session:
            await create_dispatched_load(
                session,
                load_number="SAFE-LD-ROLLBACK-1",
                load_weight=20000,
                commodity="Test Cargo",
                pickup_ref="PU-SAFE",
                delivery_ref="DEL-SAFE",
                assigned_vehicle_id=vehicle_id,
            )

    async with AsyncSessionLocal() as session:
        stmt = select(Load).where(Load.load_number == "SAFE-LD-ROLLBACK-1")
        result = await session.execute(stmt)
        assert result.scalars().first() is None