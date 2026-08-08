import asyncio

import streamlit as st
from sqlalchemy import select

from src.core.database import AsyncSessionLocal
from src.core.models import Carrier, User, UserInvite
from src.core.services import (
    admin_reset_password,
    create_team_member,
    create_onboarding_invite,
    list_onboarding_invites,
    toggle_user_active_status,
    update_team_member,
)

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


def _toggle_active(carrier_id, target_user_id, active_status):
    async def _mutate():
        async with AsyncSessionLocal() as session:
            return await toggle_user_active_status(
                db=session,
                target_user_id=target_user_id,
                active_status=active_status,
                carrier_id=carrier_id,
                actor_user_id=1,
            )

    return run_async(_mutate())


def render_owner_portal(carrier_id=1):
    st.subheader("👑 Owner Portal")
    st.caption("Manage carrier branding and review your dispatch team.")

    carrier = _load_carrier(carrier_id)

    # 1. Carrier Settings Form (TASK-6.1, step 3)
    current_name = getattr(carrier, "name", None) or DEFAULT_CARRIER_NAME
    current_dot = getattr(carrier, "dot_number", None) or DEFAULT_DOT_NUMBER

    with st.container(border=True):
        st.markdown("### ⚙️ Carrier Settings")
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
            final_name = carrier_name.strip() or DEFAULT_CARRIER_NAME
            final_dot = dot_number.strip() or DEFAULT_DOT_NUMBER
            saved = _save_carrier(final_name, final_dot, carrier_id=carrier_id)
            st.session_state["owner_carrier_saved"] = saved.name
            # Immediately rerun so the white-label header updates live.
            st.rerun()

    if saved_name := st.session_state.pop("owner_carrier_saved", None):
        st.toast(f"Carrier branding updated: **{saved_name}**", icon="✅")
        st.success(f"Carrier settings saved. Branding now reads: **{saved_name}**")

    # 2. Team Provisioning — Owners create new Dispatcher/Driver accounts.
    st.markdown("### ➕ Provision New Team Member")
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
            st.session_state["owner_provisioned"] = (
                new_member.role, new_member.email
            )
            st.rerun()
        except ValueError as ve:
            # Duplicate email/username and validation failures surface here.
            st.error(str(ve))
        except Exception as ex:
            st.error(f"Failed to provision team member: {ex}")

    if provisioned := st.session_state.pop("owner_provisioned", None):
        role, email = provisioned
        st.toast(f"{role} account created: **{email}**", icon="✅")
        st.success(f"{role} provisioned successfully. {email} can now sign in.")

    # 3. Send Onboarding Invites (TASK-6.3) — recruits set up accounts before Day 1.
    st.markdown("### 📧 Send Onboarding Invite")
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
                invite.role, invite.email, payload["registration_link"]
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

    # 3b. Pending Invitations status list.
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

    # 4. Team Roster — all Dispatchers & Drivers on this carrier, with admin controls.
    st.markdown("### 📋 Team Roster")
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
        }
        for member in team
    ]
    st.dataframe(roster, use_container_width=True)

    # TASK-6.3: Interactive per-member admin controls.
    st.markdown("#### 🛠️ Member Controls")
    for member in team:
        member_label = f"{member.username or member.email} ({member.role})"
        with st.expander(member_label):
            col_a, col_b, col_c = st.columns(3)

            # Edit Details
            with col_a:
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
                    edit_clicked = st.form_submit_button(
                        "Save Details", key=f"edit_save_{member.id}"
                    )
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

            # Reset Password
            with col_b:
                st.markdown("**🔑 Reset Password**")
                with st.form(key=f"reset_pw_{member.id}"):
                    new_pw = st.text_input(
                        "New Temporary Password",
                        type="password",
                        key=f"reset_pw_input_{member.id}",
                    )
                    reset_clicked = st.form_submit_button(
                        "Override Password", key=f"reset_btn_{member.id}"
                    )
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

            # Deactivate / Reactivate
            with col_c:
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
                            )
                            st.session_state["member_update_ref"] = (
                                f"**{member.username or member.email}** was reactivated."
                            )
                            st.rerun()
                        except (ValueError, PermissionError) as ve:
                            st.error(str(ve))

    if member_msg := st.session_state.pop("member_update_ref", None):
        st.success(member_msg)


def main():
    render_owner_portal()


if __name__ == "__main__":
    main()