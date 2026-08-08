import asyncio

import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.database import AsyncSessionLocal
from src.core.models import Carrier, Load, User, UserInvite, Vehicle
from src.core.services import (
    admin_reset_password,
    create_team_member,
    create_onboarding_invite,
    delete_or_deactivate_user,
    list_onboarding_invites,
    toggle_user_active_status,
    update_team_member,
)
from src.ui.driver_briefing import render_driver_briefing
from src.ui.driver_reset_planner import render_driver_reset_planner
from src.ui.gps_component import render_demo_map
from src.ui.repair_form import render_repair_form
from src.ui.status_toggles import render_status_toggles

# TASK-6.1: Baseline demo defaults. Forms NEVER render blank - these fallbacks
# give the Owner Portal a clean starting point until a Carrier row is saved.
DEFAULT_CARRIER_NAME = "Two-Six Logistics LLC"
DEFAULT_DOT_NUMBER = "USDOT-3829104"


def run_async(coro):
    return asyncio.run(coro)


def _load_carrier(carrier_id=1):
    async def _query():
        async with AsyncSessionLocal() as session:
            carrier = await session.get(Carrier, carrier_id)
            return carrier

    return run_async(_query())


def _save_carrier(name, dot_number, carrier_id=1):
    async def _mutate():
        async with AsyncSessionLocal() as session:
            carrier = await session.get(Carrier, carrier_id)
            if carrier is None:
                carrier = Carrier(id=carrier_id, name=name, dot_number=dot_number)
                session.add(carrier)
            else:
                carrier.name = name
                carrier.dot_number = dot_number
            await session.commit()
            await session.refresh(carrier)
            return carrier

    return run_async(_mutate())


def _load_team(carrier_id=1):
    async def _query():
        async with AsyncSessionLocal() as session:
            users = (
                (
                    await session.execute(
                        select(User)
                        .where(
                            User.carrier_id == carrier_id,
                            User.role.in_(["Dispatcher", "Driver"]),
                        )
                        .order_by(User.is_active.desc(), User.role.asc(), User.email.asc())
                    )
                )
                .scalars()
                .all()
            )
            return list(users)

    return run_async(_query())


def _load_command_center(carrier_id=1):
    """Loads active loads + vehicles for the Fleet Command Center tab."""

    async def _query():
        async with AsyncSessionLocal() as session:
            loads = (
                (
                    await session.execute(
                        select(Load)
                        .options(
                            selectinload(Load.driver),
                            selectinload(Load.vehicle),
                            selectinload(Load.status_logs),
                        )
                        .where(Load.carrier_id == carrier_id)
                        .order_by(Load.created_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            vehicles = (
                (
                    await session.execute(
                        select(Vehicle)
                        .where(Vehicle.carrier_id == carrier_id)
                        .order_by(Vehicle.unit_number.asc())
                    )
                )
                .scalars()
                .all()
            )
            return list(loads), list(vehicles)

    return run_async(_query())


def _load_pending_invites(carrier_id=1):
    async def _query():
        async with AsyncSessionLocal() as session:
            return await list_onboarding_invites(session, carrier_id)

    return run_async(_query())


def _provision_team_member(carrier_id, email, username, password, role):
    async def _mutate():
        async with AsyncSessionLocal() as session:
            return await create_team_member(
                db=session,
                carrier_id=carrier_id,
                email=email,
                username=username,
                password=password,
                role=role,
            )

    return run_async(_mutate())


def _send_onboarding_invite(carrier_id, email, role):
    async def _mutate():
        async with AsyncSessionLocal() as session:
            return await create_onboarding_invite(
                db=session, carrier_id=carrier_id, email=email, role=role
            )

    return run_async(_mutate())


def _admin_reset_password(carrier_id, target_user_id, new_password):
    async def _mutate():
        async with AsyncSessionLocal() as session:
            return await admin_reset_password(
                db=session,
                target_user_id=target_user_id,
                new_password=new_password,
                carrier_id=carrier_id,
            )

    return run_async(_mutate())


def _update_team_member(carrier_id, target_user_id, username, email, role):
    async def _mutate():
        async with AsyncSessionLocal() as session:
            return await update_team_member(
                db=session,
                target_user_id=target_user_id,
                username=username,
                email=email,
                role=role,
                carrier_id=carrier_id,
            )

    return run_async(_mutate())


def _toggle_active(carrier_id, target_user_id, active_status, actor_user_id):
    async def _mutate():
        async with AsyncSessionLocal() as session:
            return await toggle_user_active_status(
                db=session,
                target_user_id=target_user_id,
                active_status=active_status,
                carrier_id=carrier_id,
                actor_user_id=actor_user_id,
            )

    return run_async(_mutate())


def _delete_user(carrier_id, target_user_id, actor_user_id):
    async def _mutate():
        async with AsyncSessionLocal() as session:
            return await delete_or_deactivate_user(
                db=session,
                target_user_id=target_user_id,
                carrier_id=carrier_id,
                actor_user_id=actor_user_id,
            )

    return run_async(_mutate())


# ==========================================
# Executive Dashboard tabs (TASK-6.x)
# ==========================================
def _render_fleet_command_center(carrier_id):
    st.markdown("### 📊 Fleet Command Center")
    st.caption("Live snapshot of your dispatch board, assets, and in-progress loads.")

    loads, vehicles = _load_command_center(carrier_id)

    grounded = sum(1 for v in vehicles if v.status == "Grounded")
    road_ready = len(vehicles) - grounded
    working_drivers = {l.assigned_driver_id for l in loads if l.assigned_driver_id}

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🚛 Active Loads", len(loads))
    m2.metric("🚚 Fleet Vehicles", len(vehicles))
    m3.metric("🟢 Road-Ready", road_ready)
    m4.metric("🛠️ Grounded", grounded)

    st.markdown("#### ▶️ Live Dispatch Map")
    with st.container(border=True):
        # TASK-6.4: interactive demo telemetry map (st.map) injected whenever
        # live browser GPS is unavailable or blocked.
        render_demo_map()
        st.divider()
        if not loads:
            st.info("No active loads to track right now.")
        else:
            for load in loads:
                pickup = (load.pickup_address or load.pickup_ref or "TBD").strip()
                delivery = (load.delivery_address or load.delivery_ref or "TBD").strip()
                driver = (
                    load.driver.username or load.driver.email
                    if load.driver
                    else "Unassigned"
                )
                truck = load.vehicle.unit_number if load.vehicle else "No truck"
                st.markdown(
                    f"- **{load.load_number}** · `{load.status.upper()}` · "
                    f"{pickup} **→** {delivery}\n"
                    f"  - 👤 {driver} · 🚚 #{truck} · 📦 {load.commodity}"
                )

    st.divider()

    if loads:
        st.markdown("**Active Load Board**")
        load_rows = [
            {
                "Load #": l.load_number,
                "Driver": (l.driver.username or l.driver.email) if l.driver else "Unassigned",
                "Truck": l.vehicle.unit_number if l.vehicle else "-",
                "Commodity": l.commodity,
                "Weight (lbs)": f"{l.load_weight:,.0f}",
                "Status": l.status.upper(),
            }
            for l in loads
        ]
        st.dataframe(load_rows, use_container_width=True)
    else:
        st.info("No loads are currently dispatched.")

    if vehicles:
        st.markdown("**Vehicle Statuses**")
        vehicle_rows = [
            {
                "Unit #": v.unit_number,
                "VIN": (v.vin or "-")[:12],
                "Status": v.status,
                "Odometer": f"{v.current_odometer:,} mi",
            }
            for v in vehicles
        ]
        st.dataframe(vehicle_rows, use_container_width=True)
    else:
        st.info("No fleet vehicles registered yet.")

    st.caption(
        "Dispatch map statuses reflect each unit's most recently reported "
        "trip stage from the Driver Console."
    )


def _render_driver_console_view(actor_user_id):
    """🚛 Driver Console View for solo owner-operators."""
    st.markdown("### 🚛 Driver Console View")
    st.caption(
        "Solo owner-operator mode: your briefing, status toggles, repair forms, "
        "and HOS duty clock all in one place."
    )

    if not actor_user_id:
        st.warning("No active user identity found for the owner-operator console.")
        return

    st.markdown("**🗺️ On-Road Telemetry**")
    render_demo_map()

    render_driver_briefing(driver_id=actor_user_id, driver_name="Owner-Operator")
    render_status_toggles(driver_id=actor_user_id, driver_name="Owner-Operator")
    render_repair_form(driver_id=actor_user_id, driver_name="Owner-Operator")
    render_driver_reset_planner(driver_id=actor_user_id, driver_name="Owner-Operator")


def _render_carrier_settings(carrier, carrier_id):
    """⚙️ Carrier Settings — white-label branding form."""
    current_name = getattr(carrier, "name", None) or DEFAULT_CARRIER_NAME
    current_dot = getattr(carrier, "dot_number", None) or DEFAULT_DOT_NUMBER

    st.markdown("### ⚙️ Carrier Settings")
    st.caption("White-label branding appears in every header across FleetScout.")

    with st.form(key="carrier_settings_form", clear_on_submit=False):
        carrier_name = st.text_input(
            "Carrier Name",
            value=current_name,
            placeholder="e.g. Two-Six Logistics LLC",
            key="owner_carrier_name",
        )
        dot_number = st.text_input(
            "DOT Number",
            value=current_dot,
            placeholder="e.g. USDOT 3829104",
            key="owner_carrier_dot",
        )
        save_clicked = st.form_submit_button("Save Carrier Settings", type="primary")

    if save_clicked:
        final_name = (carrier_name or "").strip() or DEFAULT_CARRIER_NAME
        final_dot = (dot_number or "").strip() or DEFAULT_DOT_NUMBER
        saved = _save_carrier(final_name, final_dot, carrier_id=carrier_id)
        st.session_state["owner_carrier_saved"] = saved.name
        # Immediately rerun so the white-label header updates live.
        st.rerun()

    if saved_name := st.session_state.pop("owner_carrier_saved", None):
        st.toast(f"Carrier branding updated: **{saved_name}**", icon="✅")
        st.success(f"Carrier settings saved. Branding now reads: **{saved_name}**")


def _render_team_provisioning(carrier_id):
    """➕ Provision New Team Member — creates Dispatcher/Driver accounts."""
    st.markdown("#### ➕ Provision New Team Member")
    with st.form(key="provision_team_form", clear_on_submit=True):
        p_email = st.text_input(
            "Email Address",
            placeholder="e.g. newdriver@fleetscout.com",
            key="owner_provision_email",
        )
        p_username = st.text_input(
            "Username / Name",
            placeholder="e.g. jdoe",
            key="owner_provision_username",
        )
        p_password = st.text_input(
            "Temporary Password",
            type="password",
            placeholder="Set an initial password",
            key="owner_provision_password",
        )
        p_role = st.selectbox(
            "Assigned Role",
            options=["Dispatcher", "Driver"],
            index=1,
            key="owner_provision_role",
        )
        provision_clicked = st.form_submit_button(
            "Provision Team Member", type="primary"
        )

    if provision_clicked:
        try:
            new_member = _provision_team_member(
                carrier_id=carrier_id,
                email=p_email,
                username=p_username,
                password=p_password,
                role=p_role,
            )
            st.session_state["owner_provisioned"] = (new_member.role, new_member.email)
            st.rerun()
        except ValueError as ve:
            st.error(str(ve))
        except Exception as ex:
            st.error(f"Failed to provision team member: {ex}")

    if provisioned := st.session_state.pop("owner_provisioned", None):
        role, email = provisioned
        st.toast(f"{role} account created: **{email}**", icon="✅")
        st.success(f"{role} provisioned successfully. {email} can now sign in.")


def _render_onboarding_invites(carrier_id):
    """📧 Send Onboarding Invite — issues redeemable tokens to new recruits."""
    st.markdown("#### 📧 Send Onboarding Invite")
    st.caption("Invite a new hire by email — they'll complete their own registration.")
    with st.form(key="send_invite_form", clear_on_submit=True):
        inv_email = st.text_input(
            "Recruit Email",
            placeholder="e.g. recruit@fleetscout.com",
            key="owner_invite_email",
        )
        inv_role = st.selectbox(
            "Assigned Role",
            options=["Driver", "Dispatcher"],
            index=0,
            key="owner_invite_role",
        )
        invite_clicked = st.form_submit_button("Send Invite", type="primary")

    if invite_clicked:
        try:
            payload = _send_onboarding_invite(
                carrier_id=carrier_id, email=inv_email, role=inv_role
            )
            invite = payload["invite"]
            st.session_state["owner_invite_sent"] = (
                invite.role,
                invite.email,
                payload["registration_link"],
            )
            st.rerun()
        except ValueError as ve:
            st.error(str(ve))
        except Exception as ex:
            st.error(f"Failed to send invite: {ex}")

    if invite_sent := st.session_state.pop("owner_invite_sent", None):
        invite_role, invite_email, link = invite_sent
        st.toast(f"Invite dispatched to **{invite_email}**", icon="✅")
        st.success(
            f"{invite_role} invite sent to **{invite_email}**.\n\n"
            "Registration link (simulated email payload):\n\n"
            f"`{link}`"
        )

    with st.expander("🕓 Pending Invitations", expanded=False):
        invites = _load_pending_invites(carrier_id)
        if not invites:
            st.info("No invites have been dispatched yet.")
        else:
            invite_rows = [
                {
                    "Role": i.role,
                    "Email": i.email,
                    "Status": i.status,
                    "Expires": i.expires_at.strftime("%m/%d/%Y") if i.expires_at else "-",
                }
                for i in invites
            ]
            st.dataframe(invite_rows, use_container_width=True)


def _render_team_roster(carrier_id, actor_user_id):
    """📋 Team Roster — unified roster with an Actions column + member controls."""
    team = _load_team(carrier_id)

    if not team:
        st.info("No dispatchers or drivers are linked to this carrier yet.")
        return

    roster = [
        {
            "Member ID": member.id,
            "Role": member.role,
            "Email": member.email,
            "Username": member.username or "-",
            "Status": "Active" if member.is_active else "Deactivated",
            "Actions": "✏️ Edit | 🔑 Reset | 🗑️ Delete",
        }
        for member in team
    ]
    st.markdown("#### Team Access")
    st.dataframe(roster, use_container_width=True)

    st.markdown("#### 🛠️ Member Controls")
    for member in team:
        member_label = f"{member.username or member.email} ({member.role})"
        with st.expander(member_label):
            # --- Row 1: Edit Details + Reset Password ---
            col_edit, col_reset = st.columns(2)

            with col_edit:
                st.markdown("**✏️ Edit Details**")
                with st.form(key=f"edit_member_{member.id}", clear_on_submit=True):
                    e_username = st.text_input(
                        "Username",
                        value=member.username or "",
                        key=f"edit_username_{member.id}",
                    )
                    e_email = st.text_input(
                        "Email",
                        value=member.email,
                        key=f"edit_email_{member.id}",
                    )
                    e_role = st.selectbox(
                        "Role",
                        options=["Dispatcher", "Driver"],
                        index=0 if member.role == "Dispatcher" else 1,
                        key=f"edit_role_{member.id}",
                    )
                    edit_clicked = st.form_submit_button("Save Details")
                if edit_clicked:
                    try:
                        _update_team_member(
                            carrier_id=carrier_id,
                            target_user_id=member.id,
                            username=e_username,
                            email=e_email,
                            role=e_role,
                        )
                        st.session_state["owner_action"] = (
                            f"Details updated for **{e_username or e_email}**."
                        )
                        st.rerun()
                    except (ValueError, PermissionError) as ve:
                        st.error(str(ve))

            with col_reset:
                st.markdown("**🔑 Reset Password**")
                with st.form(key=f"reset_pw_{member.id}"):
                    new_pw = st.text_input(
                        "New Temporary Password",
                        type="password",
                        key=f"reset_pw_input_{member.id}",
                    )
                    reset_clicked = st.form_submit_button("Override Password")
                if reset_clicked:
                    try:
                        _admin_reset_password(
                            carrier_id=carrier_id,
                            target_user_id=member.id,
                            new_password=new_pw,
                        )
                        st.session_state["owner_update_ref"] = (
                            f"Password reset for **{member.username or member.email}**."
                        )
                        st.rerun()
                    except (ValueError, PermissionError) as ve:
                        st.error(str(ve))

            # --- Row 2: Account Access + Delete / Remove ---
            col_access, col_delete = st.columns(2)

            with col_access:
                st.markdown("**👤 Account Access**")
                if member.is_active:
                    deact_clicked = st.button(
                        "Deactivate Account",
                        key=f"deactivate_{member.id}",
                        type="secondary",
                    )
                    if deact_clicked:
                        try:
                            _toggle_active(
                                carrier_id=carrier_id,
                                target_user_id=member.id,
                                active_status=False,
                                actor_user_id=actor_user_id,
                            )
                            st.session_state["member_update_ref"] = (
                                f"**{member.username or member.email}** was deactivated."
                            )
                            st.rerun()
                        except (ValueError, PermissionError) as ve:
                            st.error(str(ve))
                else:
                    react_clicked = st.button(
                        "Reactivate Account",
                        key=f"reactivate_{member.id}",
                        type="primary",
                    )
                    if react_clicked:
                        try:
                            _toggle_active(
                                carrier_id=carrier_id,
                                target_user_id=member.id,
                                active_status=True,
                                actor_user_id=actor_user_id,
                            )
                            st.session_state["member_update_ref"] = (
                                f"**{member.username or member.email}** was reactivated."
                            )
                            st.rerun()
                        except (ValueError, PermissionError) as ve:
                            st.error(str(ve))

            with col_delete:
                st.markdown("**🗑️ Delete / Remove**")
                confirm_key = f"confirm_delete_{member.id}"
                if st.session_state.get(confirm_key):
                    st.warning(
                        f"Remove **{member.username or member.email}** permanently? "
                        "Historical trip / report logs stay intact."
                    )
                    c_yes, c_no = st.columns(2)
                    if c_yes.button("Yes, Remove", key=f"confirm_yes_{member.id}"):
                        try:
                            _delete_user(
                                carrier_id=carrier_id,
                                target_user_id=member.id,
                                actor_user_id=actor_user_id,
                            )
                            st.session_state.pop(confirm_key, None)
                            st.session_state["member_update_ref"] = (
                                f"**{member.username or member.email}** was "
                                "removed from the fleet."
                            )
                            st.rerun()
                        except (ValueError, PermissionError) as ve:
                            st.error(str(ve))
                            st.session_state.pop(confirm_key, None)
                            st.rerun()
                    if c_no.button("Cancel", key=f"confirm_no_{member.id}"):
                        st.session_state.pop(confirm_key, None)
                        st.rerun()
                else:
                    delete_clicked = st.button(
                        "🗑️ Delete / Remove",
                        key=f"delete_{member.id}",
                        type="secondary",
                    )
                    if delete_clicked:
                        st.session_state[confirm_key] = True
                        st.rerun()


def render_owner_portal(carrier_id=1, actor_user_id=1):
    st.subheader("👑 Executive Owner Dashboard")
    st.caption(
        "One command deck for your dispatch fleet, driver console, team access, "
        "and carrier branding."
    )

    carrier = _load_carrier(carrier_id)

    tab_fleet, tab_driver, tab_team, tab_carrier = st.tabs(
        [
            "📊 Fleet Command Center",
            "🚛 Driver Console View",
            "👥 Team & Access Management",
            "⚙️ Carrier Settings",
        ]
    )

    with tab_fleet:
        _render_fleet_command_center(carrier_id)

    with tab_driver:
        _render_driver_console_view(actor_user_id)

    with tab_team:
        _render_team_provisioning_and_invites(carrier_id)
        _render_team_roster(carrier_id, actor_user_id)

    with tab_carrier:
        _render_carrier_settings(carrier, carrier_id)

    if owner_msg := st.session_state.pop("owner_update_ref", None):
        st.success(owner_msg)


def _render_team_provisioning_and_invites(carrier_id):
    """👥 Team management header: provisioning + onboarding invitations."""
    st.markdown("### 👥 Team & Access Management")
    _render_team_provisioning(carrier_id)
    st.divider()
    _render_onboarding_invites(carrier_id)
    st.divider()


def main():
    render_owner_portal()


if __name__ == "__main__":
    main()