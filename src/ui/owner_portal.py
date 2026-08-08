import asyncio

import streamlit as st
from sqlalchemy import select

from src.core.database import AsyncSessionLocal
from src.core.models import Carrier, User
from src.core.services import create_team_member

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
                            User.is_active.is_(True),
                            User.role.in_(["Dispatcher", "Driver"]),
                        )
                        .order_by(User.role.asc(), User.email.asc())
                    )
                )
                .scalars()
                .all()
            )
            return list(users)

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

    # 3. Team Roster — all active Dispatchers & Drivers on this carrier.
    st.markdown("### 📋 Team Roster")
    team = _load_team(carrier_id)

    if not team:
        st.info("No active dispatchers or drivers are linked to this carrier yet.")
        return

    roster = [
        {
            "Role": member.role,
            "Email": member.email,
            "Username": member.username or "-",
            "Status": "Active",
        }
        for member in team
    ]
    st.dataframe(roster, use_container_width=True)


def main():
    render_owner_portal()


if __name__ == "__main__":
    main()