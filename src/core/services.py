import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.plugins import plugin_registry
from src.core.exceptions import SafetyViolationError
from src.core.models import (
    User,
    UserInvite,
    Vehicle,
    OdometerLog,
    Load,
    LoadStatusLog,
    RepairReport,
    DutyLog,
)
from src.core.security import get_password_hash

logger = logging.getLogger("fleetscout.plugins")

TEAM_MEMBER_ROLES = ("Dispatcher", "Driver")

# Invites are redeemable for 7 days before they hard-expire (Task TASK-6.3).
INVITE_TTL_DAYS = 7


async def create_team_member(
    db: AsyncSession,
    carrier_id: int,
    email: str,
    username: str,
    password: str,
    role: str,
) -> User:
    """Provisions a new Dispatcher/Driver account bound to the Owner's carrier.

    Validates the requested role, hashes the temporary password via
    ``get_password_hash()``, and guards against duplicate email/username
    collisions with a user-friendly error. The new ``User`` is committed so
    the Team Roster renders it on the very next rerun.
    """
    if role not in TEAM_MEMBER_ROLES:
        raise ValueError(
            f"Invalid role '{role}'. Choose either 'Dispatcher' or 'Driver'."
        )

    clean_email = (email or "").strip().lower()
    clean_username = (username or "").strip()
    if not clean_email:
        raise ValueError("Email address is required.")
    if not password:
        raise ValueError("Temporary password is required.")

    from sqlalchemy import select

    existing_email = (
        await db.execute(select(User).where(User.email == clean_email))
    ).scalar_one_or_none()
    if existing_email is not None:
        raise ValueError(
            f"An account with email '{clean_email}' already exists. "
            "Choose a different email address."
        )

    if clean_username:
        existing_username = (
            await db.execute(select(User).where(User.username == clean_username))
        ).scalar_one_or_none()
        if existing_username is not None:
            raise ValueError(
                f"Username '{clean_username}' is already taken. "
                "Choose a different username."
            )

    member = User(
        email=clean_email,
        username=clean_username or None,
        hashed_password=get_password_hash(password),
        role=role,
        carrier_id=carrier_id,
        is_active=True,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


# ==========================================
# TASK-6.3: Onboarding Invites & Account Admin
# ==========================================
async def create_onboarding_invite(
    db: AsyncSession, carrier_id: int, email: str, role: str
) -> dict:
    """Issues a redeemable onboarding invitation to a recruit (Task TASK-6.3).

    Generates a cryptographically unique token, guards against duplicate
    pending invites and existing accounts, stores the Pending invite bound to
    the Owner's carrier network, and returns the simulated email payload
    (registration link) for the UI to surface as the onboarding dispatch.
    """
    from sqlalchemy import select

    if role not in TEAM_MEMBER_ROLES:
        raise ValueError(
            f"Invalid role '{role}'. Choose either 'Dispatcher' or 'Driver'."
        )

    clean_email = (email or "").strip().lower()
    if not clean_email:
        raise ValueError("Email address is required.")

    existing_user = (
        await db.execute(select(User).where(User.email == clean_email))
    ).scalar_one_or_none()
    if existing_user is not None:
        raise ValueError(
            f"An account with email '{clean_email}' already exists. "
            "Invite a different email address."
        )

    pending = (
        await db.execute(
            select(UserInvite).where(
                UserInvite.email == clean_email,
                UserInvite.status == "Pending",
            )
        )
    ).scalar_one_or_none()
    if pending is not None:
        raise ValueError(
            f"An invite for '{clean_email}' is already pending. "
            "Resend or wait for the recruit to accept it."
        )

    token = secrets.token_urlsafe(32)
    invite = UserInvite(
        email=clean_email,
        role=role,
        carrier_id=carrier_id,
        token=token,
        status="Pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)

    registration_link = f"/?invite_token={token}"
    return {
        "invite": invite,
        "registration_link": registration_link,
        "email_payload": (
            f"Subject: You're invited to join the {carrier_id} fleet on FleetScout\n"
            f"To: {clean_email}\n"
            f"Body: Complete your profile by {registration_link}. "
            f"This link expires in {INVITE_TTL_DAYS} days."
        ),
    }


async def accept_onboarding_invite(
    db: AsyncSession, token: str, username: str, password: str
) -> User:
    """Redeems an onboarding invitation into an active Team Member account.

    Validates the token, guards against expired or already-accepted invites,
    hashes the recruit's password with native bcrypt, creates an active
    ``User`` bound to the invite's carrier, and marks the invite 'Accepted'
    so the token can never be redeemed twice.
    """
    from sqlalchemy import select

    if not token:
        raise ValueError("An invite token is required.")

    invite = (
        await db.execute(select(UserInvite).where(UserInvite.token == token))
    ).scalar_one_or_none()
    if invite is None:
        raise ValueError(
            "That invite token is not valid. Check the link and try again."
        )
    if invite.status == "Accepted":
        raise ValueError("This invite has already been accepted.")
    expires_at = invite.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at is None or expires_at < datetime.now(timezone.utc):
        raise ValueError("This invite has expired. Ask your owner to re-invite you.")

    clean_username = (username or "").strip()
    if not clean_username:
        raise ValueError("A username is required to set up your account.")
    if not password:
        raise ValueError("A password is required to set up your account.")

    existing_username = (
        await db.execute(select(User).where(User.username == clean_username))
    ).scalar_one_or_none()
    if existing_username is not None:
        raise ValueError(
            f"Username '{clean_username}' is already taken. Choose another."
        )

    recruit = User(
        email=invite.email,
        username=clean_username,
        hashed_password=get_password_hash(password),
        role=invite.role,
        carrier_id=invite.carrier_id,
        is_active=True,
    )
    db.add(recruit)
    invite.status = "Accepted"
    await db.commit()
    await db.refresh(recruit)
    return recruit


async def list_onboarding_invites(db: AsyncSession, carrier_id: int):
    """Returns all onboarding invites for a carrier, newest first."""
    from sqlalchemy import select

    stmt = (
        select(UserInvite)
        .where(UserInvite.carrier_id == carrier_id)
        .order_by(UserInvite.created_at.desc())
    )
    return (await db.execute(stmt)).scalars().all()


async def _require_same_carrier(db: AsyncSession, target_user_id: int, carrier_id: int) -> User:
    """Fetch a user strictly scoped to the acting carrier network.

    Prevents Owners/Dispatchers from editing, resetting, or deactivating users
    belonging to another carrier (Task TASK-6.3 guardrail). Raises PermissionError
    when the target user does not exist or lives in a different carrier.
    """
    target = await db.get(User, target_user_id)
    if target is None:
        raise ValueError(f"Team member with ID {target_user_id} not found.")
    if target.carrier_id != carrier_id:
        raise PermissionError(
            f"Team member with ID {target_user_id} belongs to another carrier "
            "and cannot be managed from this account."
        )
    return target


async def admin_reset_password(
    db: AsyncSession, target_user_id: int, new_password: str, carrier_id: int
) -> User:
    """Owner/Dispatcher instant password override (Task TASK-6.3).

    Strictly scoped to the acting carrier's own team. The new password is
    hashed with native bcrypt and committed atomically.
    """
    if not new_password:
        raise ValueError("A new password is required.")
    target = await _require_same_carrier(db, target_user_id, carrier_id)
    target.hashed_password = get_password_hash(new_password)
    await db.commit()
    await db.refresh(target)
    return target


async def update_team_member(
    db: AsyncSession,
    target_user_id: int,
    username: str,
    email: str,
    role: str,
    carrier_id: int,
) -> User:
    """Owner edits a team member's username, email, or role (Task TASK-6.3).

    Guards duplicate email/username collisions and only accepts
    Dispatcher/Driver roles. Strictly carrier-scoped.
    """
    from sqlalchemy import select

    target = await _require_same_carrier(db, target_user_id, carrier_id)

    if role not in TEAM_MEMBER_ROLES:
        raise ValueError(
            f"Invalid role '{role}'. Choose either 'Dispatcher' or 'Driver'."
        )

    clean_email = (email or "").strip().lower()
    clean_username = (username or "").strip()
    if not clean_email:
        raise ValueError("Email address is required.")

    conflict_email = (
        await db.execute(
            select(User).where(
                User.email == clean_email, User.id != target_user_id
            )
        )
    ).scalar_one_or_none()
    if conflict_email is not None:
        raise ValueError(
            f"An account with email '{clean_email}' already exists. "
            "Choose a different email address."
        )

    if clean_username:
        conflict_username = (
            await db.execute(
                select(User).where(
                    User.username == clean_username, User.id != target_user_id
                )
            )
        ).scalar_one_or_none()
        if conflict_username is not None:
            raise ValueError(
                f"Username '{clean_username}' is already taken. "
                "Choose a different username."
            )

    target.username = clean_username or None
    target.email = clean_email
    target.role = role
    await db.commit()
    await db.refresh(target)
    return target


async def toggle_user_active_status(
    db: AsyncSession,
    target_user_id: int,
    active_status: bool,
    carrier_id: int,
    actor_user_id: int = None,
) -> User:
    """One-click Deactivate / Reactivate switch (Task TASK-6.3).

    Carrier-scoped. An Owner cannot deactivate their own account, so the
    acting user id is dropped when supplied; attempting a self-deactivation
    raises a user-friendly ValueError.
    """
    target = await _require_same_carrier(db, target_user_id, carrier_id)

    if actor_user_id is not None and actor_user_id == target_user_id and not active_status:
        raise ValueError(
            "You cannot deactivate your own account. Ask another owner to manage it."
        )

    target.is_active = bool(active_status)
    await db.commit()
    await db.refresh(target)
    return target


async def delete_or_deactivate_user(
    db: AsyncSession,
    target_user_id: int,
    carrier_id: int,
    actor_user_id: int = None,
) -> dict:
    """Permanently removes a team member while preserving historical trip logs.

    The target must belong to the acting carrier's network (strict carrier_id
    boundary). Two protective guardrails are enforced:

    * Owner accounts are non-deletable — an avenue remains to own the carrier.
    * An actor may never delete their own account.

    Before the row is removed, every historical reference that still points at
    the user — past loads they were dispatched on, repair reports they filed,
    and duty logs they recorded — is quietly detached (FK column set to NULL)
    so no orphan rows exist and the delete never violates FK constraints. The
    active ''trip'' history is preserved: loads stay on the books, just marked
    'Unassigned'.
    """
    from sqlalchemy import select

    target = await _require_same_carrier(db, target_user_id, carrier_id)

    if target.role == "Owner":
        raise PermissionError(
            "Owner accounts cannot be deleted from within FleetScout. "
            "Keep at least one owner to administer the carrier."
        )
    if actor_user_id is not None and actor_user_id == target_user_id:
        raise ValueError(
            "You cannot delete your own account. Ask another owner to remove it."
        )

    removed = {
        "id": target.id,
        "email": target.email,
        "username": target.username,
        "role": target.role,
    }

    # Detach historical references FIRST so the delete never violates FK
    # constraints and old loads/reports/duty logs survive with NULL driver.
    for load in (
        await db.execute(select(Load).where(Load.assigned_driver_id == target.id))
    ).scalars():
        load.assigned_driver_id = None
    for report in (
        await db.execute(
            select(RepairReport).where(RepairReport.driver_id == target.id)
        )
    ).scalars():
        report.driver_id = None
    for duty in (
        await db.execute(select(DutyLog).where(DutyLog.driver_id == target.id))
    ).scalars():
        duty.driver_id = None

    await db.delete(target)
    await db.commit()
    return removed


async def run_plugin_hook(
    plugin_name: str, data: dict, **kwargs
) -> dict:
    """Execute a registered plugin in complete isolation (Task HD-5.1).

    Guarantees plugin failure can never crash core dispatch: every exception
    is caught, logged, and surfaced as a structured ``{"ok": False, ...}``
    dict. No database transaction is started, altered, or rolled back by a
    plugin hook, so dispatch logic remains deterministic regardless of
    third-party adapter behaviour.
    """
    plugin = plugin_registry.get(plugin_name)
    if plugin is None:
        return {
            "ok": False,
            "plugin": plugin_name,
            "error": f"Plugin '{plugin_name}' is not registered.",
        }
    try:
        if not await plugin.validate():
            return {
                "ok": False,
                "plugin": plugin_name,
                "error": f"Plugin '{plugin_name}' failed validation.",
            }
        result = await plugin.execute(data, **kwargs)
        return {"ok": True, "plugin": plugin_name, "result": result}
    except Exception as exc:  # isolation boundary - never propagates
        logger.exception("Plugin '%s' execution failed", plugin_name)
        return {"ok": False, "plugin": plugin_name, "error": str(exc)}


async def validate_vehicle_readiness(
    session: AsyncSession, vehicle_id: int
) -> Vehicle:
    """Safety interceptor (Task HD-5.2): blocks load assignment to Grounded vehicles.

    Raises SafetyViolationError if the vehicle does not exist or its status is
    'Grounded'. Returns the vehicle when dispatch-ready.
    """
    vehicle = await session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise SafetyViolationError(
            f"Vehicle with ID {vehicle_id} not found. Cannot assign a load."
        )
    if vehicle.status == "Grounded":
        raise SafetyViolationError(
            f"Vehicle {vehicle.unit_number} (ID {vehicle.id}) is Grounded and "
            "cannot be assigned a load. Resolve maintenance before dispatching "
            "this asset."
        )
    return vehicle


def update_vehicle_odometer(
    db: Session, vehicle_id: int, new_reading: int, notes: str = None
) -> OdometerLog:
    """
    Atomically creates an OdometerLog entry and updates Vehicle.current_odometer.
    Enforces that new readings cannot be lower than the current reading.
    """
    # Fetch a fresh, active instance inside the current db session
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise ValueError(f"Vehicle with ID {vehicle_id} not found.")

    if new_reading < vehicle.current_odometer:
        raise ValueError(
            f"Invalid reading ({new_reading:,} miles): Cannot be lower than "
            f"current odometer reading ({vehicle.current_odometer:,} miles)."
        )

    # 1. Create audit log
    log_entry = OdometerLog(
        vehicle_id=vehicle.id, reading=new_reading, notes=notes
    )

    # 2. Update parent vehicle reading
    vehicle.current_odometer = new_reading

    # 3. Commit atomically
    db.add(log_entry)
    db.commit()
    db.refresh(vehicle)
    db.refresh(log_entry)

    return log_entry


async def create_dispatched_load(
    session: AsyncSession,
    load_number: str,
    load_weight: int,
    commodity: str,
    pickup_ref: str,
    delivery_ref: str,
    dispatcher_notes: str = None,
    assigned_driver_id: int = None,
    assigned_vehicle_id: int = None,
    pickup_address: str = None,
    delivery_address: str = None,
    target_pickup_at=None,
    target_delivery_at=None,
) -> Load:
    """Atomically inserts a new Load record with 'dispatched' status."""
    if assigned_vehicle_id is not None:
        try:
            await validate_vehicle_readiness(session, assigned_vehicle_id)
        except SafetyViolationError:
            await session.rollback()
            raise

    db_load = Load(
        load_number=load_number,
        load_weight=load_weight,
        commodity=commodity,
        pickup_ref=pickup_ref,
        delivery_ref=delivery_ref,
        pickup_address=pickup_address,
        delivery_address=delivery_address,
        target_pickup_at=target_pickup_at,
        target_delivery_at=target_delivery_at,
        dispatcher_notes=dispatcher_notes,
        status="dispatched",
        carrier_id=1,
        assigned_driver_id=assigned_driver_id,
        assigned_vehicle_id=assigned_vehicle_id,
    )
    session.add(db_load)
    await session.commit()
    await session.refresh(db_load)
    return db_load


async def create_authorized_load(
    session: AsyncSession,
    *,
    human_authorized: bool = False,
    load_number: str,
    load_weight: int,
    commodity: str,
    pickup_ref: str,
    delivery_ref: str,
    dispatcher_notes: str = None,
    assigned_driver_id: int = None,
    assigned_vehicle_id: int = None,
    pickup_address: str = None,
    delivery_address: str = None,
    target_pickup_at=None,
    target_delivery_at=None,
) -> Load:
    """Human-in-the-Loop (HITL) guarded load commit (Task TASK-6.5).

    Parsed FreightSlip rate-confirmation data must NEVER be committed to the
    database automatically. This guardrail requires an explicit
    ``human_authorized=True`` flag (only set after an operator clicks the
    'Authorize & Commit Load' button and inspects the auto-filled fields).
    Without authorization it raises ``PermissionError`` and the transaction
    is left untouched, preventing zero-click database insertions on PDF upload.
    """
    if not human_authorized:
        raise PermissionError(
            "Human-in-the-loop authorization required. Verify the extracted "
            "FreightSlip rate confirmation data before committing the load."
        )
    return await create_dispatched_load(
        session=session,
        load_number=load_number,
        load_weight=load_weight,
        commodity=commodity,
        pickup_ref=pickup_ref,
        delivery_ref=delivery_ref,
        dispatcher_notes=dispatcher_notes,
        assigned_driver_id=assigned_driver_id,
        assigned_vehicle_id=assigned_vehicle_id,
        pickup_address=pickup_address,
        delivery_address=delivery_address,
        target_pickup_at=target_pickup_at,
        target_delivery_at=target_delivery_at,
    )


async def dispatch_load_with_plugins(
    session: AsyncSession,
    *,
    load_number: str = None,
    load_weight: int = None,
    commodity: str = None,
    pickup_ref: str = None,
    delivery_ref: str = None,
    dispatcher_notes: str = None,
    assigned_driver_id: int = None,
    assigned_vehicle_id: int = None,
    pickup_address: str = None,
    delivery_address: str = None,
    ratecon_bytes: bytes = None,
    origin: str = None,
    destination: str = None,
    hos_driving_hours: float = None,
    hos_start_time: str = None,
) -> tuple[Load, dict]:
    """Dispatch a load while consulting modular plugin hooks (Task HD-5.1).

    1. ``freightslip`` parses an optional RateCon payload to auto-fill load
       fields (commodity, weight, refs) when the caller left them unset.
    2. ``lanesight`` computes route distance / transit time and, optionally,
       the DOT HOS plan - appended to dispatcher notes as a summary.

    Every plugin call is isolated via ``run_plugin_hook``: a failing or
    misconfigured plugin returns a structured error dict and dispatch simply
    continues with the provided (or defaulted) payload. Plugin hooks never
    raise ``SafetyViolationError`` and never roll back the session. The SD-5.2
    safety interceptor still runs once, inside ``create_dispatched_load``.
    """
    enrichment: dict = {}

    if ratecon_bytes is not None:
        hook = await run_plugin_hook(
            "freightslip", {"action": "parse", "file_bytes": ratecon_bytes}
        )
        enrichment["freightslip"] = hook
        if hook.get("ok"):
            parsed = hook["result"]
            load_number = load_number or parsed.get("load_number")
            load_weight = load_weight or parsed.get("weight")
            commodity = commodity or parsed.get("commodity")
            pickup_ref = pickup_ref or parsed.get("pickup_ref")
            delivery_ref = delivery_ref or parsed.get("delivery_ref")

    notes_bits = []
    if dispatcher_notes:
        notes_bits.append(dispatcher_notes)

    if origin and destination:
        hook = await run_plugin_hook(
            "lanesight", {"action": "route", "origin": origin, "destination": destination}
        )
        enrichment["lanesight"] = hook
        if hook.get("ok"):
            route = hook["result"]
            notes_bits.append(
                "est. {0:,.1f} mi / {1:.2f} hr".format(
                    float(route["distance_miles"]), float(route["duration_hours"])
                )
            )

    if hos_driving_hours is not None and hos_start_time:
        hook = await run_plugin_hook(
            "lanesight",
            {"action": "hos", "driving_hours": hos_driving_hours, "start_time": hos_start_time},
        )
        enrichment["lanesight_hos"] = hook
        if hook.get("ok"):
            hos = hook["result"]
            notes_bits.append(
                "HOS: {} stops / avail {}".format(
                    hos["rest_break_count"],
                    hos["sleeper_berth_reset"]["available_at"],
                )
            )

    load_number = load_number or f"PLG-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    load_weight = load_weight if load_weight is not None else 0
    commodity = commodity or "TBD"
    pickup_ref = pickup_ref or "N/A"
    delivery_ref = delivery_ref or "N/A"

    load = await create_dispatched_load(
        session,
        load_number=load_number,
        load_weight=load_weight,
        commodity=commodity,
        pickup_ref=pickup_ref,
        delivery_ref=delivery_ref,
        dispatcher_notes=" | ".join(notes_bits) if notes_bits else None,
        assigned_driver_id=assigned_driver_id,
        assigned_vehicle_id=assigned_vehicle_id,
        pickup_address=pickup_address,
        delivery_address=delivery_address,
    )
    return load, enrichment


async def update_load_status(
    session: AsyncSession, load_id: int, status: str, gps_lat: float = None, gps_lng: float = None
) -> LoadStatusLog:
    """Sets a Load's active status and logs a timestamped entry (with optional GPS) for the board timeline."""
    load = await session.get(Load, load_id)
    if not load:
        raise ValueError(f"Load with ID {load_id} not found.")

    load.status = status
    log_entry = LoadStatusLog(
        load_id=load.id,
        status=status,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
    )
    session.add(log_entry)
    await session.commit()
    await session.refresh(load)
    await session.refresh(log_entry)
    return log_entry


async def create_repair_report(
    session: AsyncSession,
    driver_id: int,
    category: str,
    description: str = None,
    photo_path: str = None,
    vehicle_id: int = None,
    load_id: int = None,
    gps_lat: float = None,
    gps_lng: float = None,
) -> RepairReport:
    """Atomically persists a structured driver issue report (Task DS-4.3)."""
    report = RepairReport(
        category=category,
        description=description,
        photo_path=photo_path,
        status="reported",
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        load_id=load_id,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def get_recent_repair_reports(
    session: AsyncSession, driver_id: int = None, limit: int = 20
):
    """Returns recent repair reports, optionally filtered to one driver."""
    from sqlalchemy import select

    stmt = select(RepairReport).order_by(RepairReport.created_at.desc()).limit(limit)
    if driver_id is not None:
        stmt = stmt.where(RepairReport.driver_id == driver_id)
    return (await session.execute(stmt)).scalars().all()


# Only Owner/Mechanic roles may release a grounded asset back to the road
# (Task HD-5.3). Dispatchers and drivers cannot override the safety lockout.
UNGROUND_AUTHORIZED_ROLES = ("Owner", "Mechanic")


async def ground_vehicle(session: AsyncSession, vehicle_id: int) -> Vehicle:
    """Flags a vehicle as 'Grounded' (Task HD-5.3 lifecycle).

    Called when a driver reports a safety issue affecting an asset. Once
    grounded, the HD-5.2 interceptor blocks any load assignment until a
    Mechanic/Owner performs the repair and un-grounds the vehicle.
    """
    vehicle = await session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise ValueError(f"Vehicle with ID {vehicle_id} not found.")

    if vehicle.status == "Grounded":
        raise ValueError(f"Vehicle {vehicle.unit_number} is already Grounded.")

    vehicle.status = "Grounded"
    await session.commit()
    await session.refresh(vehicle)
    return vehicle


async def unground_vehicle(
    session: AsyncSession, vehicle_id: int, actor_role: str = None
) -> Vehicle:
    """Sets a grounded vehicle's status back to 'Active' after repairs.

    Strictly restricted to authorized roles (Mechanic/Owner). Callers must
    supply the actor's role — Dispatchers and Drivers cannot release an asset.
    """
    if actor_role not in UNGROUND_AUTHORIZED_ROLES:
        raise PermissionError(
            f"Role '{actor_role}' is not authorized to un-ground vehicles. "
            f"Only {', '.join(UNGROUND_AUTHORIZED_ROLES)} may release an asset."
        )

    vehicle = await session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise ValueError(f"Vehicle with ID {vehicle_id} not found.")

    vehicle.status = "Active"
    await session.commit()
    await session.refresh(vehicle)
    return vehicle


async def get_active_loads(session: AsyncSession):
    """Returns active dispatched loads with driver/vehicle and status-history timeline."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    stmt = (
        select(Load)
        .options(selectinload(Load.driver), selectinload(Load.vehicle), selectinload(Load.status_logs))
        .order_by(Load.created_at.desc())
    )
    return (await session.execute(stmt)).scalars().all()


async def get_driver_briefing(session: AsyncSession, driver_id: int):
    """Returns active loads assigned to a driver, newest first, with vehicle details."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    stmt = (
        select(Load)
        .options(selectinload(Load.vehicle), selectinload(Load.status_logs))
        .where(Load.assigned_driver_id == driver_id)
        .order_by(Load.created_at.desc())
    )
    return (await session.execute(stmt)).scalars().all()


async def log_duty_start(
    session: AsyncSession,
    driver_id: int,
    duty_state: str,
    gps_lat: float = None,
    gps_lng: float = None,
) -> DutyLog:
    """Atomically logs a driver duty-state start (Task DS-4.4).

    When the state is 'Off Duty' or 'Sleeper Berth', the 10-hour availability
    return countdown begins and target_available_at is set accordingly.
    """
    if duty_state not in DutyLog.DUTY_STATES:
        raise ValueError(
            f"Invalid duty state '{duty_state}'. Choose one of {DutyLog.DUTY_STATES}."
        )

    now = datetime.now(timezone.utc)
    rests = {"Off Duty", "Sleeper Berth"}
    off_duty_started_at = now if duty_state in rests else None
    target_available_at = (
        now + timedelta(hours=DutyLog.REST_HOURS) if duty_state in rests else None
    )

    log_entry = DutyLog(
        driver_id=driver_id,
        duty_state=duty_state,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        off_duty_started_at=off_duty_started_at,
        target_available_at=target_available_at,
    )
    session.add(log_entry)
    await session.commit()
    await session.refresh(log_entry)
    return log_entry


async def get_latest_duty_log(session: AsyncSession, driver_id: int) -> DutyLog:
    """Returns the most recent duty log for a driver, or None."""
    from sqlalchemy import select

    stmt = (
        select(DutyLog)
        .where(DutyLog.driver_id == driver_id)
        .order_by(DutyLog.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def get_duty_summary(session: AsyncSession, driver_id: int):
    """Returns a dict summarizing the driver's 10-hour availability countdown.

    Includes the latest duty log, the off-duty start time, the availability
    return time, and the seconds remaining until available (0 if already available).
    """
    latest = await get_latest_duty_log(session, driver_id)
    summary = {
        "latest_log": latest,
        "off_duty_started_at": None,
        "target_available_at": None,
        "seconds_remaining": None,
        "is_resting": False,
    }
    if latest is None:
        return summary

    if latest.target_available_at is None:
        return summary

    now = datetime.now(timezone.utc)
    target = latest.target_available_at
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    seconds_remaining = max(int((target - now).total_seconds()), 0)

    summary.update(
        {
            "off_duty_started_at": latest.off_duty_started_at,
            "target_available_at": target,
            "seconds_remaining": seconds_remaining,
            "is_resting": seconds_remaining > 0,
        }
    )
    return summary


async def get_recent_duty_logs(
    session: AsyncSession, driver_id: int = None, limit: int = 20
):
    """Returns recent duty logs, optionally filtered to one driver."""
    from sqlalchemy import select

    stmt = select(DutyLog).order_by(DutyLog.created_at.desc()).limit(limit)
    if driver_id is not None:
        stmt = stmt.where(DutyLog.driver_id == driver_id)
    return (await session.execute(stmt)).scalars().all()


# ==========================================
# TASK-6.7: Load Profitability & ROI Analyzer
# ==========================================
# Status badge thresholds (percentage margin):
#   >= 20%  -> Highly Profitable
#   5%–19%  -> Marginal
#   < 5%    -> Unprofitable
PROFIT_HIGHLY_PROFITABLE_STATUS = "🟢 Highly Profitable"
PROFIT_MARGINAL_STATUS = "🟡 Marginal"
PROFIT_UNPROFITABLE_STATUS = "🔴 Unprofitable"
PROFIT_HIGHLY_PROFITABLE_MARGIN = 20.0
PROFIT_MARGINAL_MARGIN = 5.0


def calculate_load_profitability(
    gross_payout: float,
    total_miles: float,
    mpg: float,
    fuel_price: float,
    driver_cpm: float,
    fixed_cpm_reserve: float = 0.15,
) -> dict:
    """Instantly compute load profitability (Task TASK-6.7).

    Combines the gross payout with fuel, driver, and fixed overhead reserves
    to surface net profit, rate-per-mile (RPM), cost-per-mile (CPM), profit
    margin percentage, and a color-coded decision badge.

    Guardrails: division by zero is impossible. When ``total_miles``,
    ``gross_payout``, or ``mpg`` are zero (or negative) the function never
    raises — it reports ``valid=False``, zeroes every derived money figure, and
    badge status maps to Unprofitable so the UI can nudge the owner to enter a
    realistic trip.
    """
    gross_payout = float(gross_payout or 0.0)
    total_miles = float(total_miles or 0.0)
    mpg = float(mpg or 0.0)
    fuel_price = float(fuel_price or 0.0)
    driver_cpm = float(driver_cpm or 0.0)
    fixed_cpm_reserve = float(fixed_cpm_reserve or 0.0)

    usable_miles = total_miles > 0
    usable_payout = gross_payout > 0
    usable_mpg = mpg > 0

    # Zero-division guards: an unusable MPG leaves fuel cost indeterminate but
    # never crashes the calculator — the caller is warned via ``valid``.
    if usable_miles and usable_mpg:
        fuel_cost = (total_miles / mpg) * fuel_price
    else:
        fuel_cost = 0.0
    driver_cost = total_miles * driver_cpm
    overhead_reserve = total_miles * fixed_cpm_reserve
    total_cost = fuel_cost + driver_cost + overhead_reserve
    net_profit = gross_payout - total_cost

    if usable_miles:
        rpm = gross_payout / total_miles
        cpm = total_cost / total_miles
    else:
        rpm = 0.0
        cpm = 0.0

    if usable_payout:
        profit_margin_pct = (net_profit / gross_payout) * 100
    else:
        profit_margin_pct = 0.0

    if not usable_miles or not usable_payout or not usable_mpg:
        status = PROFIT_UNPROFITABLE_STATUS
        is_valid = False
    elif profit_margin_pct >= PROFIT_HIGHLY_PROFITABLE_MARGIN:
        status = PROFIT_HIGHLY_PROFITABLE_STATUS
        is_valid = True
    elif profit_margin_pct >= PROFIT_MARGINAL_MARGIN:
        status = PROFIT_MARGINAL_STATUS
        is_valid = True
    else:
        status = PROFIT_UNPROFITABLE_STATUS
        is_valid = True

    return {
        "valid": is_valid,
        "gross_payout": round(gross_payout, 2),
        "total_miles": total_miles,
        "fuel_price": round(fuel_price, 2),
        "fuel_cost": round(fuel_cost, 2),
        "driver_cost": round(driver_cost, 2),
        "overhead_reserve": round(overhead_reserve, 2),
        "total_cost": round(total_cost, 2),
        "net_profit": round(net_profit, 2),
        "rpm": round(rpm, 2),
        "cpm": round(cpm, 2),
        "profit_margin_pct": round(profit_margin_pct, 2),
        "status": status,
    }