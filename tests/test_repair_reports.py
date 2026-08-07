import pytest

from src.core.database import Base, sync_engine, AsyncSessionLocal
from src.core.models import Load, RepairReport, Vehicle, User
from src.core.security import get_password_hash
from src.core.services import create_repair_report, get_recent_repair_reports


@pytest.fixture(scope="module", autouse=True)
def reset_schema():
    Base.metadata.drop_all(bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)


@pytest.mark.asyncio
async def test_create_repair_report_persists_all_fields():
    async with AsyncSessionLocal() as session:
        driver = User(
            email="repair-driver@fleetscout.com",
            hashed_password=get_password_hash("password123"),
            role="Driver",
            carrier_id=1,
        )
        vehicle = Vehicle(unit_number="RPR001", status="Active", carrier_id=1)
        load = Load(
            load_number="RPR-LD-1",
            load_weight=20000,
            commodity="Test Cargo",
            pickup_ref="PU-RPR",
            delivery_ref="DEL-RPR",
            status="dispatched",
            carrier_id=1,
        )
        session.add_all([driver, vehicle, load])
        await session.commit()
        await session.refresh(driver)
        await session.refresh(vehicle)
        await session.refresh(load)

    async with AsyncSessionLocal() as session:
        report = await create_repair_report(
            session,
            driver_id=driver.id,
            category="Brakes",
            description="Squealing noise when braking at speed.",
            photo_path="/tmp/uploads/repair_test.jpg",
            vehicle_id=vehicle.id,
            load_id=load.id,
            gps_lat=36.7378,
            gps_lng=-119.7871,
        )

    assert report is not None
    assert report.category == "Brakes"
    assert report.description == "Squealing noise when braking at speed."
    assert report.photo_path == "/tmp/uploads/repair_test.jpg"
    assert report.status == "reported"
    assert report.driver_id == driver.id
    assert report.vehicle_id == vehicle.id
    assert report.load_id == load.id
    assert report.gps_lat == 36.7378
    assert report.gps_lng == -119.7871
    assert report.created_at is not None

    async with AsyncSessionLocal() as session:
        fresh_report = await session.get(RepairReport, report.id)
        assert fresh_report is not None
        assert fresh_report.category == "Brakes"
        assert fresh_report.description == "Squealing noise when braking at speed."


@pytest.mark.asyncio
async def test_get_recent_repair_reports_filters_by_driver():
    async with AsyncSessionLocal() as session:
        await create_repair_report(session, driver_id=1, category="Tires", description="Low pressure.")
        await create_repair_report(session, driver_id=99, category="Lights", description="Headlight out.")

    async with AsyncSessionLocal() as session:
        reports = await get_recent_repair_reports(session, driver_id=99)
        assert len(reports) == 1
        assert reports[0].category == "Lights"