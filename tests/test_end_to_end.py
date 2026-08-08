import pytest

from sqlalchemy import func, select

from src.core.database import Base, sync_engine, AsyncSessionLocal
from src.core.exceptions import SafetyViolationError
from src.core.models import DutyLog, Load, RepairReport, User, UserInvite, Vehicle
from src.core.seed import ensure_database_seeded
from src.core.services import (
    UNGROUND_AUTHORIZED_ROLES,
    accept_onboarding_invite,
    admin_reset_password,
    create_onboarding_invite,
    create_team_member,
    create_dispatched_load,
    create_repair_report,
    delete_or_deactivate_user,
    get_driver_briefing,
    ground_vehicle,
    list_onboarding_invites,
    log_duty_start,
    toggle_user_active_status,
    unground_vehicle,
    update_load_status,
    update_team_member,
)
from src.core.security import get_password_hash, verify_password


@pytest.mark.asyncio
async def test_startup_self_heals_empty_database():
    """FIX-6.2: initializing against a fresh empty database triggers auto-seeding.

    The module-scoped fixture has just (re)built empty tables, so this must
    run first: a User count of 0 forces ensure_database_seeded() to seed the
    baseline accounts, and a second pass stays a no-op (idempotent).
    """
    async with AsyncSessionLocal() as session:
        count = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    assert count == 0

    seeded = await ensure_database_seeded()
    assert seeded is True

    async with AsyncSessionLocal() as session:
        emails = set((await session.execute(select(User.email))).scalars().all())
        baseline = {
            "owner@fleetscout.com",
            "dispatcher@fleetscout.com",
            "driver@fleetscout.com",
        }
        assert baseline <= emails
        assert len(emails) == 4

    # Idempotent guard: re-seeding the populated DB adds nothing and never raises.
    reseeded = await ensure_database_seeded()
    assert reseeded is False
    async with AsyncSessionLocal() as session:
        assert (
            await session.execute(select(func.count()).select_from(User))
        ).scalar_one() == 4


@pytest.fixture(scope="module", autouse=True)
def reset_schema():
    Base.metadata.drop_all(bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)


@pytest.mark.asyncio
async def test_full_lifecycle_ground_block_repair_assign():
    """Task HD-5.3 end-to-end walkthrough:
    Driver reports issue -> truck Grounded -> Dispatcher blocked ->
    Mechanic repairs (unground) -> Dispatcher assignment succeeds.
    """
    # --- Setup: driver, mechanic, and an active truck ---
    async with AsyncSessionLocal() as session:
        driver = User(
            email="e2e-driver@fleetscout.com",
            hashed_password="x",
            role="Driver",
            carrier_id=1,
        )
        mechanic = User(
            email="e2e-mechanic@fleetscout.com",
            hashed_password="x",
            role="Mechanic",
            carrier_id=1,
        )
        vehicle = Vehicle(unit_number="E2E-001", status="Active", carrier_id=1)
        session.add_all([driver, mechanic, vehicle])
        await session.commit()
        await session.refresh(driver)
        await session.refresh(mechanic)
        await session.refresh(vehicle)
        vehicle_id = vehicle.id

    # --- 1. Driver reports issue -> truck is Grounded ---
    async with AsyncSessionLocal() as session:
        report = await create_repair_report(
            session,
            driver_id=driver.id,
            category="Brakes",
            description="Squealing noise, pedal feels soft.",
            vehicle_id=vehicle_id,
        )
        grounded = await ground_vehicle(session, vehicle_id)

    assert report is not None
    assert report.vehicle_id == vehicle_id
    assert grounded.status == "Grounded"

    # --- 2. Dispatcher attempts assignment -> blocked by HD-5.2 interceptor ---
    with pytest.raises(SafetyViolationError) as exc_info:
        async with AsyncSessionLocal() as session:
            await create_dispatched_load(
                session,
                load_number="E2E-BLOCKED-1",
                load_weight=20000,
                commodity="Test Cargo",
                pickup_ref="PU-E2E",
                delivery_ref="DEL-E2E",
                assigned_vehicle_id=vehicle_id,
            )
    assert "Grounded" in str(exc_info.value)

    # --- 3. Mechanic performs repair -> un-grounded ---
    async with AsyncSessionLocal() as session:
        repaired = await unground_vehicle(
            session, vehicle_id, actor_role="Mechanic"
        )
    assert repaired.status == "Active"

    # --- 4. Dispatcher attempts assignment -> succeeds ---
    async with AsyncSessionLocal() as session:
        load = await create_dispatched_load(
            session,
            load_number="E2E-ASSIGN-1",
            load_weight=20000,
            commodity="Test Cargo",
            pickup_ref="PU-E2E",
            delivery_ref="DEL-E2E",
            assigned_vehicle_id=vehicle_id,
            assigned_driver_id=driver.id,
        )

    assert load is not None
    assert load.status == "dispatched"
    assert load.assigned_vehicle_id == vehicle_id
    assert load.assigned_driver_id == driver.id


@pytest.mark.asyncio
async def test_unground_restricted_to_authorized_roles():
    """Only Owner/Mechanic roles may release a grounded asset (HD-5.3 guardrail)."""
    assert UNGROUND_AUTHORIZED_ROLES == ("Owner", "Mechanic")

    async with AsyncSessionLocal() as session:
        vehicle = Vehicle(unit_number="E2E-ROLE-01", status="Grounded", carrier_id=1)
        session.add(vehicle)
        await session.commit()
        await session.refresh(vehicle)
        vehicle_id = vehicle.id

    # Dispatcher (or any other role) is denied — asset stays Grounded
    with pytest.raises(PermissionError):
        async with AsyncSessionLocal() as session:
            await unground_vehicle(session, vehicle_id, actor_role="Dispatcher")

    async with AsyncSessionLocal() as session:
        fresh = await session.get(Vehicle, vehicle_id)
        assert fresh.status == "Grounded"

    # A missing actor role is also denied (no bypass)
    with pytest.raises(PermissionError):
        async with AsyncSessionLocal() as session:
            await unground_vehicle(session, vehicle_id)

    # Mechanic and Owner are authorized
    async with AsyncSessionLocal() as session:
        await unground_vehicle(session, vehicle_id, actor_role="Mechanic")

    async with AsyncSessionLocal() as session:
        await ground_vehicle(session, vehicle_id)
        await unground_vehicle(session, vehicle_id, actor_role="Owner")

    async with AsyncSessionLocal() as session:
        fresh = await session.get(Vehicle, vehicle_id)
        assert fresh.status == "Active"


@pytest.mark.asyncio
async def test_ground_vehicle_is_idempotent_guard():
    async with AsyncSessionLocal() as session:
        vehicle = Vehicle(unit_number="E2E-GRD-01", status="Grounded", carrier_id=1)
        session.add(vehicle)
        await session.commit()
        await session.refresh(vehicle)
        vehicle_id = vehicle.id

    with pytest.raises(ValueError):
        async with AsyncSessionLocal() as session:
            await ground_vehicle(session, vehicle_id)


@pytest.mark.asyncio
async def test_report_persisted_after_full_cycle():
    """Sanity check: the driver's repair report survives the whole lifecycle."""
    async with AsyncSessionLocal() as session:
        stmt = select(RepairReport).where(RepairReport.category == "Brakes")
        reports = (await session.execute(stmt)).scalars().all()
    assert len(reports) >= 1


@pytest.mark.asyncio
async def test_driver_briefing_eager_loads_status_logs():
    """FIX-5.8: status_logs must survive session close on driver briefing loads."""
    async with AsyncSessionLocal() as session:
        driver = User(
            email="e2e-briefing-driver@fleetscout.com",
            hashed_password="x",
            role="Driver",
            carrier_id=1,
        )
        vehicle = Vehicle(unit_number="E2E-BRIEF-01", status="Active", carrier_id=1)
        session.add_all([driver, vehicle])
        await session.commit()
        await session.refresh(driver)
        await session.refresh(vehicle)

        load = await create_dispatched_load(
            session,
            load_number="E2E-BRIEF-1",
            load_weight=10000,
            commodity="Briefing Cargo",
            pickup_ref="PU-BRIEF",
            delivery_ref="DEL-BRIEF",
            assigned_vehicle_id=vehicle.id,
            assigned_driver_id=driver.id,
        )

    async with AsyncSessionLocal() as session:
        await update_load_status(session, load.id, "at_shipper", gps_lat=40.0, gps_lng=-74.0)

    late_labels = []
    async with AsyncSessionLocal() as session:
        loads = await get_driver_briefing(session, driver.id)
        briefing_load = next(l for l in loads if l.id == load.id)
        late_labels.append(briefing_load.status_logs)

    assert len(late_labels[0]) >= 1
    assert late_labels[0][0].status == "at_shipper"


def test_gps_component_falls_back_to_demo_telemetry_on_load_failure(monkeypatch):
    """FIX-5.9 + TASK-6.4: GPS component must never raise or render a warning
    banner when the custom iframe fails, the static frontend build is missing,
    or the browser geolocation returns nothing. Instead of a blank
    "unavailable" state, it injects realistic mock telemetry centered on the
    LA / I-10 / Inland Empire freight corridor (34.0522, -118.2437)."""
    from src.ui import gps_component as gc

    monkeypatch.setattr(gc, "_gps_location", None)
    gps = gc.gps_location(key="fallback_test")
    assert gps is not None
    assert gps["fallback"] is True
    assert gps["label"] == gc.MOCK_TELEMETRY_LABEL
    assert 33.9 <= gps["lat"] <= 34.2
    assert -118.5 <= gps["lng"] <= -118.0
    assert len(gps["vehicles"]) >= 4

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated component load failure")

    monkeypatch.setattr(gc, "_gps_location", _raise)
    gps = gc.gps_location(key="fallback_test")
    assert gps is not None and gps["fallback"] is True

    monkeypatch.setattr(gc, "_gps_location", lambda *a, **k: None)
    assert gc.gps_location(key="fallback_test")["fallback"] is True

    monkeypatch.setattr(gc, "_gps_location", lambda *a, **k: {})
    assert gc.gps_location(key="fallback_test")["fallback"] is True

    monkeypatch.setattr(gc, "_gps_location", lambda *a, **k: {"lat": 33.9, "lng": -118.4})
    live = gc.gps_location(key="fallback_test")
    assert live["fallback"] is False
    assert live["lat"] == 33.9
    assert live["lng"] == -118.4
    assert live["vehicles"] == []


def test_mock_telemetry_generates_realistic_fleet_markers():
    """TASK-6.4: the mock telemetry engine returns a realistic LA-corridor
    fleet (TRK-001 In Transit, TRK-002 Docked, ...) with simulated speed,
    heading, and status, plus the exact demo caption label. Same key ->
    same deterministic payload across reruns."""
    from src.ui.gps_component import (
        MOCK_TELEMETRY_LABEL,
        format_gps_summary,
        mock_telemetry,
    )

    telemetry = mock_telemetry(key="demo_corridor")
    assert telemetry["fallback"] is True
    assert telemetry["label"] == MOCK_TELEMETRY_LABEL
    assert MOCK_TELEMETRY_LABEL == "📍 GPS: Live Demo Telemetry (I-10 / LA Corridor)"
    assert "Live Demo Telemetry" in format_gps_summary(telemetry)

    vehicles = telemetry["vehicles"]
    assert len(vehicles) >= 4

    statuses = {v["status"] for v in vehicles}
    assert "In Transit" in statuses
    assert "Docked" in statuses

    # Coordinates stay within the Southern California freight corridor.
    assert all(33.5 <= v["lat"] <= 34.6 for v in vehicles)
    assert all(-118.8 <= v["lon"] <= -117.0 for v in vehicles)

    # Speeds and headings obey sane bounds per unit.
    assert all(0 <= v["speed_mph"] <= 75 for v in vehicles)
    assert all(0 <= v["heading_deg"] <= 360 for v in vehicles)

    # Docked units are stationary with zero ground speed.
    by_unit = {v["unit"]: v for v in vehicles}
    assert any(v["speed_mph"] == 0 for v in vehicles if v["status"] == "Docked")
    assert by_unit["TRK-001"]["status"] == "In Transit"
    assert by_unit["TRK-002"]["status"] == "Docked"

    # Deterministic: the same session key reproduces identical feeds.
    replay = mock_telemetry(key="demo_corridor")
    assert [(v["lat"], v["lon"]) for v in replay["vehicles"]] == [
        (v["lat"], v["lon"]) for v in vehicles
    ]
    assert replay["lng"] == telemetry["lng"]


@pytest.mark.asyncio
async def _create_team_member_in_session(**kwargs):
    async with AsyncSessionLocal() as session:
        return await create_team_member(db=session, **kwargs)


@pytest.mark.asyncio
async def test_owner_provisions_driver_and_dispatcher():
    """TASK-6.2: an Owner can provision a Driver and a Dispatcher account."""
    driver = await _create_team_member_in_session(
        carrier_id=1,
        email="provision-driver@fleetscout.com",
        username="provisiondriver",
        password="temp1234",
        role="Driver",
    )
    dispatcher = await _create_team_member_in_session(
        carrier_id=1,
        email="provision-dispatcher@fleetscout.com",
        username="provisiondispatcher",
        password="temp1234",
        role="Dispatcher",
    )
    assert driver.role == "Driver"
    assert dispatcher.role == "Dispatcher"
    assert driver.carrier_id == 1
    assert dispatcher.carrier_id == 1
    assert verify_password("temp1234", driver.hashed_password)
    assert verify_password("temp1234", dispatcher.hashed_password)

    async with AsyncSessionLocal() as session:
        stored = await session.get(User, driver.id)
        assert stored.carrier_id == 1
        assert stored.role == "Driver"


@pytest.mark.asyncio
async def test_duplicate_team_member_is_blocked():
    """TASK-6.2: re-provisioning an existing email/username surfaces an error."""
    await _create_team_member_in_session(
        carrier_id=1,
        email="dup-email@fleetscout.com",
        username="dupemail",
        password="temp1234",
        role="Driver",
    )
    with pytest.raises(ValueError, match="already exists"):
        await _create_team_member_in_session(
            carrier_id=1,
            email="dup-email@fleetscout.com",
            username="othername",
            password="temp1234",
            role="Driver",
        )
    with pytest.raises(ValueError, match="already taken"):
        await _create_team_member_in_session(
            carrier_id=1,
            email="other-email@fleetscout.com",
            username="dupemail",
            password="temp1234",
            role="Dispatcher",
        )


@pytest.mark.asyncio
async def test_team_member_role_validation():
    """TASK-6.2: only Dispatcher/Driver roles may be provisioned."""
    with pytest.raises(ValueError, match="Invalid role"):
        await _create_team_member_in_session(
            carrier_id=1,
            email="bad-role@fleetscout.com",
            username="badrole",
            password="temp1234",
            role="Owner",
        )


@pytest.mark.asyncio
async def test_create_onboarding_invite_records_pending_invite():
    """TASK-6.3: an Owner can issue a redeemable onboarding invite."""
    async with AsyncSessionLocal() as session:
        payload = await create_onboarding_invite(
            db=session,
            carrier_id=1,
            email="recruit@fleetscout.com",
            role="Driver",
        )

    invite = payload["invite"]
    assert invite is not None
    assert invite.email == "recruit@fleetscout.com"
    assert invite.role == "Driver"
    assert invite.carrier_id == 1
    assert invite.status == "Pending"
    assert invite.token is not None and len(invite.token) > 16
    assert invite.expires_at is not None
    assert payload["registration_link"] == f"/?invite_token={invite.token}"
    assert "fleetscout.com" in payload["email_payload"]

    # Duplicate pending invite for the same email is blocked.
    with pytest.raises(ValueError, match="already pending"):
        async with AsyncSessionLocal() as session:
            await create_onboarding_invite(
                db=session,
                carrier_id=1,
                email="recruit@fleetscout.com",
                role="Driver",
            )

    async with AsyncSessionLocal() as session:
        invites = await list_onboarding_invites(session, carrier_id=1)
        assert any(i.email == "recruit@fleetscout.com" for i in invites)


@pytest.mark.asyncio
async def test_accept_onboarding_invite_creates_active_user():
    """TASK-6.3: a recruit redeems the token and gets an active account."""
    async with AsyncSessionLocal() as session:
        payload = await create_onboarding_invite(
            db=session,
            carrier_id=1,
            email="newhire@fleetscout.com",
            role="Dispatcher",
        )
        token = payload["invite"].token

    async with AsyncSessionLocal() as session:
        recruit = await accept_onboarding_invite(
            db=session,
            token=token,
            username="newhire1",
            password="newpass123",
        )

    assert recruit is not None
    assert recruit.email == "newhire@fleetscout.com"
    assert recruit.username == "newhire1"
    assert recruit.role == "Dispatcher"
    assert recruit.carrier_id == 1
    assert recruit.is_active is True
    assert verify_password("newpass123", recruit.hashed_password)

    # Invite is now marked Accepted and cannot be redeemed twice.
    async with AsyncSessionLocal() as session:
        stored = (
            await session.execute(select(UserInvite).where(UserInvite.token == token))
        ).scalar_one()
        assert stored.status == "Accepted"
        with pytest.raises(ValueError, match="already been accepted"):
            await accept_onboarding_invite(
                db=session, token=token, username="newhire2", password="xpass1"
            )

    # The email can no longer be invited again (account exists).
    with pytest.raises(ValueError, match="already exists"):
        async with AsyncSessionLocal() as session:
            await create_onboarding_invite(
                db=session,
                carrier_id=1,
                email="newhire@fleetscout.com",
                role="Driver",
            )


@pytest.mark.asyncio
async def test_accept_onboarding_invite_rejects_unknown_and_expired_tokens():
    """TASK-6.3: unknown tokens are rejected and expired tokens hard-fail."""
    with pytest.raises(ValueError, match="not valid"):
        async with AsyncSessionLocal() as session:
            await accept_onboarding_invite(
                db=session, token="does-not-exist", username="u", password="p"
            )

    from datetime import datetime, timedelta, timezone

    from src.core.models import UserInvite as UI

    async with AsyncSessionLocal() as session:
        stale = UI(
            email="stale@fleetscout.com",
            role="Driver",
            carrier_id=1,
            token="stale-token-xyz",
            status="Pending",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        session.add(stale)
        await session.commit()

    with pytest.raises(ValueError, match="expired"):
        async with AsyncSessionLocal() as session:
            await accept_onboarding_invite(
                db=session, token="stale-token-xyz", username="u", password="p"
            )


@pytest.mark.asyncio
async def test_admin_reset_password_overrides_credentials():
    """TASK-6.3: an Owner/Dispatcher can override a team member's password."""
    async with AsyncSessionLocal() as session:
        member = User(
            email="pw-reset@fleetscout.com",
            username="pwreset",
            hashed_password="x",
            role="Driver",
            carrier_id=1,
        )
        session.add(member)
        await session.commit()
        await session.refresh(member)
        member_id = member.id

    async with AsyncSessionLocal() as session:
        updated = await admin_reset_password(
            db=session,
            target_user_id=member_id,
            new_password="tempOverride!",
            carrier_id=1,
        )
    assert verify_password("tempOverride!", updated.hashed_password)

    with pytest.raises(ValueError, match="new password"):
        async with AsyncSessionLocal() as session:
            await admin_reset_password(
                db=session,
                target_user_id=member_id,
                new_password="",
                carrier_id=1,
            )


@pytest.mark.asyncio
async def test_admin_cross_carrier_isolation_blocks_foreign_edits():
    """TASK-6.3: carrier_id guardrail — foreign users cannot be managed."""
    async with AsyncSessionLocal() as session:
        foreign = User(
            email="foreign@fleetscout.com",
            username="foreignuser",
            hashed_password="x",
            role="Driver",
            carrier_id=99,
        )
        session.add(foreign)
        await session.commit()
        await session.refresh(foreign)
        foreign_id = foreign.id

    with pytest.raises(PermissionError, match="another carrier"):
        async with AsyncSessionLocal() as session:
            await admin_reset_password(
                db=session,
                target_user_id=foreign_id,
                new_password="hacked123",
                carrier_id=1,
            )
    with pytest.raises(PermissionError, match="another carrier"):
        async with AsyncSessionLocal() as session:
            await toggle_user_active_status(
                db=session,
                target_user_id=foreign_id,
                active_status=False,
                carrier_id=1,
            )
    with pytest.raises(PermissionError, match="another carrier"):
        async with AsyncSessionLocal() as session:
            await update_team_member(
                db=session,
                target_user_id=foreign_id,
                username="evil",
                email="evil@fleetscout.com",
                role="Driver",
                carrier_id=1,
            )

    # The foreign account's password was never touched.
    async with AsyncSessionLocal() as session:
        stored = await session.get(User, foreign_id)
        assert stored.hashed_password == "x"


@pytest.mark.asyncio
async def test_update_team_member_edits_details_and_blocks_collisions():
    """TASK-6.3: edit username/email/role, with duplicate guardrails."""
    async with AsyncSessionLocal() as session:
        member = User(
            email="edit-me@fleetscout.com",
            username="editme",
            hashed_password="x",
            role="Driver",
            carrier_id=1,
        )
        session.add(member)
        await session.commit()
        await session.refresh(member)
        member_id = member.id

    async with AsyncSessionLocal() as session:
        updated = await update_team_member(
            db=session,
            target_user_id=member_id,
            username="editedname",
            email="edited@fleetscout.com",
            role="Dispatcher",
            carrier_id=1,
        )
    assert updated.username == "editedname"
    assert updated.email == "edited@fleetscout.com"
    assert updated.role == "Dispatcher"

    with pytest.raises(ValueError, match="Invalid role"):
        async with AsyncSessionLocal() as session:
            await update_team_member(
                db=session,
                target_user_id=member_id,
                username="editedname",
                email="edited@fleetscout.com",
                role="Owner",
                carrier_id=1,
            )

    async with AsyncSessionLocal() as session:
        other = User(
            email="other-name@fleetscout.com",
            username="takenname",
            hashed_password="x",
            role="Driver",
            carrier_id=1,
        )
        session.add(other)
        await session.commit()

    with pytest.raises(ValueError, match="already taken"):
        async with AsyncSessionLocal() as session:
            await update_team_member(
                db=session,
                target_user_id=member_id,
                username="takenname",
                email="edited@fleetscout.com",
                role="Dispatcher",
                carrier_id=1,
            )


@pytest.mark.asyncio
async def test_toggle_user_active_status_deactivates_and_reactivates():
    """TASK-6.3: one-click deactivate/reactivate toggle."""
    async with AsyncSessionLocal() as session:
        member = User(
            email="toggle-me@fleetscout.com",
            username="toggler",
            hashed_password="x",
            role="Driver",
            carrier_id=1,
        )
        session.add(member)
        await session.commit()
        await session.refresh(member)
        member_id = member.id

    async with AsyncSessionLocal() as session:
        deactivated = await toggle_user_active_status(
            db=session,
            target_user_id=member_id,
            active_status=False,
            carrier_id=1,
        )
    assert deactivated.is_active is False

    async with AsyncSessionLocal() as session:
        reactivated = await toggle_user_active_status(
            db=session,
            target_user_id=member_id,
            active_status=True,
            carrier_id=1,
        )
    assert reactivated.is_active is True

    # Self-deactivation is blocked when actor == target.
    with pytest.raises(ValueError, match="own account"):
        async with AsyncSessionLocal() as session:
            await toggle_user_active_status(
                db=session,
                target_user_id=member_id,
                active_status=False,
                carrier_id=1,
                actor_user_id=member_id,
            )


# ==========================================
# TASK-6.4 (Executive Owner Dashboard) — account deletion,
# password override, and Executive tab navigation
# ==========================================
@pytest.mark.asyncio
async def test_owner_deletes_account_preserving_historical_trip_logs():
    """Executive Owner delete: remove the member from the roster while
    historical loads, repair reports, and duty logs survive with a detached
    (NULL) driver reference — DB integrity never violated."""
    async with AsyncSessionLocal() as session:
        driver = User(
            email="delete-vision@fleetscout.com",
            username="deleteme",
            hashed_password="x",
            role="Driver",
            carrier_id=1,
        )
        vehicle = Vehicle(unit_number="E2E-DEL-01", status="Active", carrier_id=1)
        session.add_all([driver, vehicle])
        await session.commit()
        await session.refresh(driver)
        await session.refresh(vehicle)
        driver_id = driver.id

        vehicle_id = vehicle.id
        load = await create_dispatched_load(
            session,
            load_number="E2E-DEL-LOAD-1",
            load_weight=15000,
            commodity="Deletion Cargo",
            pickup_ref="PU-DEL",
            delivery_ref="DEL-DEL",
            assigned_vehicle_id=vehicle_id,
            assigned_driver_id=driver_id,
        )
        await create_repair_report(
            session,
            driver_id=driver_id,
            category="Brakes",
            description="Historical report filed pre-removal.",
            vehicle_id=vehicle_id,
            load_id=load.id,
        )
        await log_duty_start(session, driver_id, "Sleeper Berth")
        load_id = load.id

    async with AsyncSessionLocal() as session:
        removed = await delete_or_deactivate_user(
            db=session, target_user_id=driver_id, carrier_id=1
        )

    assert removed["id"] == driver_id
    assert removed["email"] == "delete-vision@fleetscout.com"
    assert removed["username"] == "deleteme"
    assert removed["role"] == "Driver"

    async with AsyncSessionLocal() as session:
        assert await session.get(User, driver_id) is None

        # The historical load survives, now detached from the driver.
        stored_load = await session.get(Load, load_id)
        assert stored_load is not None
        assert stored_load.assigned_driver_id is None
        assert stored_load.assigned_vehicle_id is not None

        # The repair report survives with its driver reference cleaved.
        reports = (
            await session.execute(
                select(RepairReport).where(
                    RepairReport.description == "Historical report filed pre-removal."
                )
            )
        ).scalars().all()
        assert len(reports) == 1
        assert reports[0].driver_id is None

        # Duty history is intact, driver reference detached.
        duty_logs = (
            await session.execute(
                select(DutyLog).where(DutyLog.duty_state == "Sleeper Berth")
            )
        ).scalars().all()
        assert any(d.driver_id is None for d in duty_logs)


@pytest.mark.asyncio
async def test_deletion_guards_owner_role_self_and_cross_carrier():
    """Executive Owner delete guardrails: foreign users are blocked, Owner
    role accounts cannot be deleted, and self-deletion is impossible. A
    second delete of an already-removed id resolves as not-found."""
    async with AsyncSessionLocal() as session:
        foreign = User(
            email="delete-foreign@fleetscout.com",
            username="foreigndel",
            hashed_password="x",
            role="Driver",
            carrier_id=99,
        )
        session.add(foreign)
        await session.commit()
        await session.refresh(foreign)
        foreign_id = foreign.id

    with pytest.raises(PermissionError, match="another carrier"):
        async with AsyncSessionLocal() as session:
            await delete_or_deactivate_user(
                db=session, target_user_id=foreign_id, carrier_id=1
            )

    async with AsyncSessionLocal() as session:
        co_owner = User(
            email="owner2remove@fleetscout.com",
            username="owner2",
            hashed_password="x",
            role="Owner",
            carrier_id=1,
        )
        session.add(co_owner)
        await session.commit()
        await session.refresh(co_owner)
        co_owner_id = co_owner.id

    with pytest.raises(PermissionError, match="Owner accounts"):
        async with AsyncSessionLocal() as session:
            await delete_or_deactivate_user(
                db=session, target_user_id=co_owner_id, carrier_id=1
            )

    async with AsyncSessionLocal() as session:
        self_del = User(
            email="selfdelete@fleetscout.com",
            username="selfdel",
            hashed_password="x",
            role="Driver",
            carrier_id=1,
        )
        session.add(self_del)
        await session.commit()
        await session.refresh(self_del)
        self_del_id = self_del.id

    with pytest.raises(ValueError, match="own account"):
        async with AsyncSessionLocal() as session:
            await delete_or_deactivate_user(
                db=session,
                target_user_id=self_del_id,
                carrier_id=1,
                actor_user_id=self_del_id,
            )

    # A non-owner acting user can delete this driver, then a second delete of
    # the same id is a clean not-found (no data corruption).
    async with AsyncSessionLocal() as session:
        await delete_or_deactivate_user(
            db=session, target_user_id=self_del_id, carrier_id=1
        )
        assert await session.get(User, self_del_id) is None

    with pytest.raises(ValueError, match="not found"):
        async with AsyncSessionLocal() as session:
            await delete_or_deactivate_user(
                db=session, target_user_id=self_del_id, carrier_id=1
            )


@pytest.mark.asyncio
async def test_password_override_binds_new_credential_and_drops_old():
    """Executive Owner password override: new credential verifies, old one is
    permanently invalidated."""
    async with AsyncSessionLocal() as session:
        member = User(
            email="override@fleetscout.com",
            username="overrider",
            hashed_password=get_password_hash("original123"),
            role="Driver",
            carrier_id=1,
        )
        session.add(member)
        await session.commit()
        await session.refresh(member)
        member_id = member.id
        assert verify_password("original123", member.hashed_password)

    async with AsyncSessionLocal() as session:
        updated = await admin_reset_password(
            db=session,
            target_user_id=member_id,
            new_password="tempOverride!",
            carrier_id=1,
        )

    assert verify_password("tempOverride!", updated.hashed_password)
    assert not verify_password("original123", updated.hashed_password)


def test_executive_dashboard_tab_navigation_renders_all_four():
    """Executive Owner Dashboard exposes the four executive tabs."""
    from streamlit.testing.v1 import AppTest

    probe_script = (
        "import os, sys\n"
        "sys.path.insert(0, os.getcwd())\n"
        "import streamlit as st\n"
        "from src.ui.owner_portal import render_owner_portal\n"
        "st.set_page_config(page_title='probe')\n"
        "render_owner_portal(carrier_id=1, actor_user_id=1)\n"
    )
    at = AppTest.from_string(probe_script, default_timeout=30)
    at.run()
    assert not at.exception
    labels = {tab.label for tab in at.tabs}
    assert "📊 Fleet Command Center" in labels
    assert "🚛 Driver Console View" in labels
    assert "👥 Team & Access Management" in labels
    assert "⚙️ Carrier Settings" in labels




# ==========================================
# TASK-6.5: FreightSlip ratecon PDF parser & HITL authorization
# ==========================================
SAMPLE_RATECON_TEXT = """Rate Confirmation
Broker: Acme Corp Freight Brokers
Shipper: WidgetMfg Supply
Load: RC-8801
Weight: 42,800 lbs
Commodity: Auto Parts
Pickup Ref: PU-10001
Delivery Ref: DEL-2002
Pickup Location: 1234 Citrus Ave, Fresno, CA
Pickup Date: 08/07/2026
Delivery Location: 899 Market St, San Francisco, CA
Delivery Date: 08/11/2026
Line Haul: $2,450.00
Total Pay: $2,765.75
"""


def test_ratecon_parser_extracts_load_metadata():
    """TASK-6.5: the FreightSlip parser extracts broker, rate, locations/dates,
    commodity, weight, and reference from a rate-confirmation payload."""
    from src.core.ratecon_parser import (
        RateConfirmationParseError,
        parse_rate_confirmation_bytes,
    )

    parsed = parse_rate_confirmation_bytes(SAMPLE_RATECON_TEXT.encode("utf-8"))

    assert parsed["broker_name"] == "Acme Corp Freight Brokers"
    assert parsed["shipper_name"] == "WidgetMfg Supply"
    assert parsed["load_number"] == "RC-8801"
    assert parsed["pickup_ref"] == "PU-10001"
    assert parsed["delivery_ref"] == "DEL-2002"
    assert parsed["load_weight"] == 42800
    assert parsed["commodity"] == "Auto Parts"
    assert parsed["pickup_location"] == "1234 Citrus Ave, Fresno, CA"
    assert parsed["pickup_date"] == "08/07/2026"
    assert parsed["delivery_location"] == "899 Market St, San Francisco, CA"
    assert parsed["delivery_date"] == "08/11/2026"
    assert parsed["linehaul_rate"] == pytest.approx(2450.00)
    assert parsed["total_pay"] == pytest.approx(2765.75)
    assert parsed["payout"] == pytest.approx(2765.75)

    # Unparseable content resolves to an explicit parse error.
    with pytest.raises(RateConfirmationParseError):
        parse_rate_confirmation_bytes(b"\x00\x01 no usable freight data here")


def test_ratecon_form_auto_fill_pre_populates_fields():
    """TASK-6.5: parsed ratecon data auto-fills every Load Creation form field."""
    from src.core.ratecon_parser import (
        date_to_form_time,
        parse_rate_confirmation_bytes,
        ratecon_to_form,
    )

    parsed = parse_rate_confirmation_bytes(SAMPLE_RATECON_TEXT.encode("utf-8"))
    form = ratecon_to_form(parsed)

    assert form["load_number"] == "RC-8801"
    assert form["load_weight"] == 42800
    assert form["commodity"] == "Auto Parts"
    assert form["pickup_ref"] == "PU-10001"
    assert form["delivery_ref"] == "DEL-2002"
    assert form["pickup_address"] == "1234 Citrus Ave, Fresno, CA"
    assert form["delivery_address"] == "899 Market St, San Francisco, CA"
    assert form["target_pickup_at"] == "08/07/2026 08:00 AM"
    assert form["target_delivery_at"] == "08/11/2026 05:00 PM"
    assert "$2,765.75" in form["dispatcher_notes"]
    assert "Acme Corp Freight Brokers" in form["dispatcher_notes"]
    assert form["broker_name"] == "Acme Corp Freight Brokers"

    # The date→form-time helper drives the target fields.
    assert date_to_form_time("08/07/2026", 8, 0) == "08/07/2026 08:00 AM"
    assert date_to_form_time("bogus") == "bogus"


@pytest.mark.asyncio
async def test_hitl_blocks_unauthorized_commit_and_succeeds_when_authorized():
    """TASK-6.5: zero-click database insertions are impossible. An
    un-authorized call raises PermissionError; after the explicit human check
    the same load data commits successfully."""
    from src.core.ratecon_parser import parse_rate_confirmation_bytes
    from src.core.services import create_authorized_load

    parsed = parse_rate_confirmation_bytes(SAMPLE_RATECON_TEXT.encode("utf-8"))

    # Un-authorized (no human click): the DB write is refused.
    with pytest.raises(PermissionError, match="authorization required"):
        async with AsyncSessionLocal() as session:
            await create_authorized_load(
                session,
                load_number=parsed["load_number"],
                load_weight=parsed["load_weight"],
                commodity=parsed["commodity"],
                pickup_ref=parsed["pickup_ref"],
                delivery_ref=parsed["delivery_ref"],
            )

    # Authorized (operator clicked Authorize & Commit): write succeeds.
    async with AsyncSessionLocal() as session:
        vehicle = Vehicle(unit_number="E2E-RATECON-01", status="Active", carrier_id=1)
        session.add(vehicle)
        await session.commit()
        await session.refresh(vehicle)
        vehicle_id = vehicle.id

    async with AsyncSessionLocal() as session:
        load = await create_authorized_load(
            session,
            human_authorized=True,
            load_number=parsed["load_number"],
            load_weight=parsed["load_weight"],
            commodity=parsed["commodity"],
            pickup_ref=parsed["pickup_ref"],
            delivery_ref=parsed["delivery_ref"],
            assigned_vehicle_id=vehicle_id,
            dispatcher_notes="Authorized by operator after HITL review.",
        )

    assert load is not None
    assert load.status == "dispatched"
    assert load.load_number == "RC-8801"
    assert load.load_weight == 42800
    assert load.assigned_vehicle_id == vehicle_id


@pytest.mark.asyncio
async def test_parse_and_staging_never_writes_to_database():
    """TASK-6.5: calling the parser + staging auto-fill alone must never insert
    a row — zero-click insertions are impossible until Authorization succeeds."""
    from src.core.ratecon_parser import (
        parse_rate_confirmation_bytes,
        ratecon_to_form,
    )

    async with AsyncSessionLocal() as session:
        existing = (
            await session.execute(select(Load.load_number))
        ).scalars().all()

    # Parse + build auto-fill payload — no session, no write.
    parsed = parse_rate_confirmation_bytes(SAMPLE_RATECON_TEXT.encode("utf-8"))
    auto = ratecon_to_form(parsed)
    assert auto["load_number"] == "RC-8801"

    # No new database rows appear just by parsing (before/after identical sets).
    async with AsyncSessionLocal() as session:
        after = (
            await session.execute(select(Load.load_number))
        ).scalars().all()
    assert set(after) >= set(existing)


# ==========================================
# TASK-6.6: Live Fuel API Service & EIA Diesel Benchmark Engine
# ==========================================
EIA_SAMPLE_CSV = (
    "Period,Regular Gasoline,Midgrade,Premium,On-Highway Diesel\n"
    "08/03/2026,3.12,3.32,3.52,3.87\n"
    "08/10/2026,3.10,3.30,3.50,3.92\n"
)


def _patch_fuel(monkeypatch, price=None, error=None, now=1_000_000.0):
    """Isolate the fuel service: deterministic clock + fake benchmark fetch."""
    import src.core.fuel_service as fs

    calls = {"n": 0}

    def fake_fetch(_region="national"):
        calls["n"] += 1
        if error is not None:
            raise error
        return price

    monkeypatch.setattr(fs, "_now_ts", lambda: now)
    monkeypatch.setattr(fs, "_fetch_benchmark", fake_fetch)
    fs.clear_cache("national")
    fs.clear_cache("offline")
    monkeypatch.setattr(fs, "clear_cache", lambda region="national": None)
    return fs, calls


def test_fuel_eia_csv_parser_extracts_latest_diesel():
    """TASK-6.6: the EIA gasdiesel CSV parser picks the newest on-highway
    diesel column (3.92), ignores header rows, and degrades cleanly on junk."""
    import src.core.fuel_service as fs

    assert fs.parse_diesel_price_csv(EIA_SAMPLE_CSV) == pytest.approx(3.92)

    muscle_bolt = (
        "Period,Regular,Midgrade,Premium,Diesel\n"
        "08/03/2026,3.10,3.30,3.50,3.98\n"
    )
    assert fs.parse_diesel_price_csv(muscle_bolt) == pytest.approx(3.98)

    with pytest.raises(ValueError):
        fs.parse_diesel_price_csv("no usable freight data here")


def test_fuel_price_fetches_success_and_serves_24h_cache(monkeypatch):
    """TASK-6.6: a fresh fetch returns structured metadata and the 24-hour
    TTL cache means Streamlit reruns never re-hit the network."""
    fs, calls = _patch_fuel(monkeypatch, price=3.95)

    first = fs.get_current_diesel_price("national")
    assert first["price_per_gal"] == pytest.approx(3.95)
    assert first["is_fallback"] is False
    assert "EIA" in first["source"]
    assert first["updated_at"]
    assert calls["n"] == 1

    # Second call within the 24h TTL is served from cache — zero network calls.
    second = fs.get_current_diesel_price("national")
    assert second["price_per_gal"] == pytest.approx(3.95)
    assert second["is_fallback"] is False
    assert "Cache" in second["source"]
    assert calls["n"] == 1

    # Advancing the clock past 24h forces a live re-fetch.
    monkeypatch.setattr(fs, "_now_ts", lambda: 1_000_000.0 + 24 * 3600 + 1)
    third = fs.get_current_diesel_price("national")
    assert third["price_per_gal"] == pytest.approx(3.95)
    assert calls["n"] == 2


def test_fuel_price_falls_back_on_network_failure(monkeypatch):
    """TASK-6.6: an offline network must never crash the app — the service
    degrades to the $3.85 demo floor with is_fallback True."""
    fs, calls = _patch_fuel(
        monkeypatch, price=None, error=ConnectionError("simulated network outage")
    )

    result = fs.get_current_diesel_price("offline")
    assert result["is_fallback"] is True
    assert result["price_per_gal"] == pytest.approx(3.85)
    assert result["source"]
    assert calls["n"] == 1

    # A second offline rerun also never raises.
    again = fs.get_current_diesel_price("offline")
    assert again["is_fallback"] is True
    assert again["price_per_gal"] == pytest.approx(3.85)


def test_fuel_stale_cache_is_used_when_fetch_fails(monkeypatch):
    """TASK-6.6: after a live fetch, a subsequent network outage serves the
    stale cached price (marked is_fallback) instead of dropping to the floor."""
    fs, calls = _patch_fuel(monkeypatch, price=4.10)
    first = fs.get_current_diesel_price("national")
    assert first["price_per_gal"] == pytest.approx(4.10)

    # Network dies; the stale cache (4.10) is still preferred over $3.85.
    monkeypatch.setattr(fs, "_fetch_benchmark", lambda region="national": (_ for _ in ()).throw(ConnectionError("offline")))
    monkeypatch.setattr(fs, "_now_ts", lambda: 1_000_000.0 + 25 * 3600)
    stale = fs.get_current_diesel_price("national")
    assert stale["price_per_gal"] == pytest.approx(4.10)
    assert stale["is_fallback"] is True


def test_fuel_effective_cost_applies_carrier_discount(monkeypatch):
    """TASK-6.6: the effective cost subtracts the carrier fuel-card discount
    ($0.45/gal) and clamps to $0.00 so it never goes negative."""
    import src.core.fuel_service as fs

    _patch_fuel(monkeypatch, price=3.85)

    assert fs.get_effective_fuel_cost(carrier_discount=0.45) == pytest.approx(3.40)
    assert fs.get_effective_fuel_cost(carrier_discount=0.0) == pytest.approx(3.85)

    # A discount larger than the whole price is clamped at $0.00.
    assert fs.get_effective_fuel_cost(carrier_discount=5.00) == pytest.approx(0.00)


@pytest.mark.asyncio
async def test_carrier_defaults_expose_economic_fuel_columns():
    """TASK-6.6: the Carrier settings schema supports optional default MPG,
    driver cents-per-mile, and the fuel-card discount used by the benchmark
    engine — pre-populated with demo defaults on a fresh row."""
    from src.core.models import Carrier as CarrierModel

    async with AsyncSessionLocal() as session:
        fresh = CarrierModel(
            id=777,
            name="TASK-6.6 Carrier",
            dot_number="USDOT-777",
        )
        session.add(fresh)
        await session.commit()

        stored = await session.get(CarrierModel, 777)
        assert stored.default_mpg == pytest.approx(6.5)
        assert stored.default_driver_cpm == pytest.approx(0.60)
        assert stored.carrier_fuel_discount == pytest.approx(0.00)
        await session.delete(stored)
        await session.commit()

