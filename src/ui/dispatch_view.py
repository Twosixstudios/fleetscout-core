import asyncio
import secrets
import string

import streamlit as st
from sqlalchemy import select

from src.core.database import AsyncSessionLocal
from src.core.models import User
from src.core.services import admin_reset_password
from src.ui.gps_component import render_demo_map


def run_async(coro):
    return asyncio.run(coro)


def _load_carrier_team(carrier_id=1):
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
                        .order_by(User.role.asc(), User.email.asc())
                    )
                )
                .scalars()
                .all()
            )
            return list(users)

    return run_async(_query())


def _reset_password(carrier_id, target_user_id, new_password):
    async def _mutate():
        async with AsyncSessionLocal() as session:
            return await admin_reset_password(
                db=session,
                target_user_id=target_user_id,
                new_password=new_password,
                carrier_id=carrier_id,
            )

    return run_async(_mutate())


def generate_recovery_pin(length=8):
    """Generates a human-readable recovery code from a safe alphabet."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def render_dispatch_view(carrier_id=1):
    """Dispatcher password-recovery tool (Task TASK-6.3).

    Let dispatchers issue temporary passwords or auto-generate a recovery PIN
    for a driver/dispatcher in their own carrier network. Strictly carrier
    scoped via ``admin_reset_password``.
    """
    st.subheader("🔑 Account Recovery Tools")
    st.caption("Reset a driver or dispatcher's access instantly within your carrier.")

    team = _load_carrier_team(carrier_id)

    if not team:
        st.info("No dispatchers or drivers are linked to this carrier yet.")
        return

    with st.form(key="dispatch_recovery_form", clear_on_submit=False):
        member_options = {
            f"{u.username or u.email} ({u.role})": u.id for u in team
        }
        member_label = st.selectbox(
            "Recover Account For",
            options=list(member_options),
            key="recovery_target",
        )
        target_id = member_options[member_label]

        pw_mode = st.radio(
            "Password Mode",
            options=["Generate Recovery PIN", "Set Temporary Password"],
            index=0,
            key="recovery_mode",
        )

        if pw_mode == "Set Temporary Password":
            manual_pw = st.text_input(
                "Temporary Password",
                type="password",
                key="recovery_manual_pw",
                placeholder="Enter a temporary password",
            )
        else:
            manual_pw = None

        reset_clicked = st.form_submit_button("Apply Recovery Password", type="primary")

    if reset_clicked:
        try:
            if pw_mode == "Set Temporary Password":
                new_pw = manual_pw or ""
            else:
                new_pw = generate_recovery_pin()
            updated = _reset_password(
                carrier_id=carrier_id,
                target_user_id=target_id,
                new_password=new_pw,
            )
            target_label = f"{updated.username or updated.email}"
            st.toast(f"Credential override applied for **{target_label}**", icon="✅")

            st.markdown(
                f"#### ✅ Recovery code for **{target_label}**\n\n"
                f"**`{new_pw}`**\n\n"
                "Share this securely with the team member. They will be asked "
                "to change it on next sign-in."
            )
        except (ValueError, PermissionError) as ve:
            st.error(str(ve))
        except Exception as ex:
            st.error(f"Failed to apply recovery password: {ex}")

    # TASK-6.4: interactive demo telemetry map so Dispatchers can walk
    # customers through live fleet positions even without browser GPS.
    st.divider()
    st.markdown("**🗺️ Live Dispatch Telemetry**")
    render_demo_map()


def main():
    render_dispatch_view()


if __name__ == "__main__":
    main()