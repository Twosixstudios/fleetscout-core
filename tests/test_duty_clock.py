from datetime import timedelta

import pytest

from src.core.database import Base, sync_engine, AsyncSessionLocal
from src.core.models import DutyLog
from src.core.security import get_password_hash
from src.core.services import (
    get_duty_summary,
    get_latest_duty_log,
    get_recent_duty_logs,
    log_duty_start,
)


@pytest.fixture(scope="module", autouse=True)
def reset_schema():
    Base.metadata.drop_all(bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)


@pytest.mark.asyncio
async def test_log_duty_start_sets_ten_hour_availability():
    async with AsyncSessionLocal() as session:
        log = await log_duty_start(
            session,
            driver_id=2,
            duty_state="Off Duty",
            gps_lat=36.7378,
            gps_lng=-119.7871,
        )

    assert log is not None
    assert log.driver_id == 2
    assert log.duty_state == "Off Duty"
    assert log.gps_lat == 36.7378
    assert log.gps_lng == -119.7871
    assert log.off_duty_started_at is not None
    assert log.target_available_at is not None
    assert log.created_at is not None

    # 10-hour availability return countdown
    expected = log.off_duty_started_at + timedelta(hours=DutyLog.REST_HOURS)
    assert log.target_available_at.replace(tzinfo=None) - expected.replace(tzinfo=None) < timedelta(seconds=5)


@pytest.mark.asyncio
async def test_log_duty_start_non_rest_state_has_no_target():
    async with AsyncSessionLocal() as session:
        log = await log_duty_start(session, driver_id=2, duty_state="Driving")

    assert log.duty_state == "Driving"
    assert log.off_duty_started_at is None
    assert log.target_available_at is None


@pytest.mark.asyncio
async def test_log_duty_start_rejects_unknown_state():
    with pytest.raises(ValueError):
        async with AsyncSessionLocal() as session:
            await log_duty_start(session, driver_id=2, duty_state="Flying")


@pytest.mark.asyncio
async def test_get_duty_summary_reports_countdown():
    async with AsyncSessionLocal() as session:
        await log_duty_start(session, driver_id=7, duty_state="Sleeper Berth")

    async with AsyncSessionLocal() as session:
        summary = await get_duty_summary(session, driver_id=7)

    assert summary["is_resting"] is True
    assert summary["latest_log"].duty_state == "Sleeper Berth"
    assert summary["seconds_remaining"] is not None
    assert summary["seconds_remaining"] > 0
    assert summary["seconds_remaining"] <= int(timedelta(hours=DutyLog.REST_HOURS).total_seconds())


@pytest.mark.asyncio
async def test_get_duty_summary_no_logs_returns_empty():
    async with AsyncSessionLocal() as session:
        summary = await get_duty_summary(session, driver_id=9999)
    assert summary["latest_log"] is None
    assert summary["is_resting"] is False
    assert summary["seconds_remaining"] is None


@pytest.mark.asyncio
async def test_get_latest_and_recent_maps_driver():
    async with AsyncSessionLocal() as session:
        await log_duty_start(session, driver_id=1, duty_state="Driving")
        await log_duty_start(session, driver_id=1, duty_state="Off Duty")

    async with AsyncSessionLocal() as session:
        latest = await get_latest_duty_log(session, driver_id=1)
        assert latest.duty_state == "Off Duty"

    async with AsyncSessionLocal() as session:
        recent = await get_recent_duty_logs(session, driver_id=1, limit=10)
        assert len(recent) == 2