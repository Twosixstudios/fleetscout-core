import pytest

from src.core.database import Base, sync_engine, AsyncSessionLocal
from src.core.models import Load, LoadStatusLog
from src.core.services import update_load_status


@pytest.fixture(scope="module", autouse=True)
def reset_schema():
    Base.metadata.drop_all(bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)


@pytest.mark.asyncio
async def test_update_load_status_logs_gps_and_timestamp():
    async with AsyncSessionLocal() as session:
        load = Load(
            load_number="TST-GPS-100",
            load_weight=18000,
            commodity="Test Cargo",
            pickup_ref="PU-TST",
            delivery_ref="DEL-TST",
            status="dispatched",
            carrier_id=1,
        )
        session.add(load)
        await session.commit()
        await session.refresh(load)
        load_id = load.id

    async with AsyncSessionLocal() as session:
        log_entry = await update_load_status(
            session,
            load_id,
            status="at_shipper",
            gps_lat=36.7378,
            gps_lng=-119.7871,
        )

    assert log_entry is not None
    assert log_entry.status == "at_shipper"
    assert log_entry.gps_lat == 36.7378
    assert log_entry.gps_lng == -119.7871
    assert log_entry.timestamp is not None

    async with AsyncSessionLocal() as session:
        fresh_log = await session.get(LoadStatusLog, log_entry.id)
        assert fresh_log is not None
        assert fresh_log.gps_lat == 36.7378

    async with AsyncSessionLocal() as session:
        fresh_load = await session.get(Load, load_id)
        assert fresh_load.status == "at_shipper"
