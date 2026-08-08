import asyncio
from zoneinfo import ZoneInfo

import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.database import AsyncSessionLocal
from src.core.models import OdometerLog, Vehicle
from src.core.services import unground_vehicle, UNGROUND_AUTHORIZED_ROLES

GROUNDED_STATUSES = ("Grounded", "Maintenance")


def run_async(coro):
    return asyncio.run(coro)


def _load_grounded():
    async def _query():
        async with AsyncSessionLocal() as session:
            vehicles = (
                (
                    await session.execute(
                        select(Vehicle)
                        .options(selectinload(Vehicle.odometer_logs))
                        .order_by(Vehicle.unit_number.asc())
                    )
                )
                .scalars()
                .all()
            )
            return [
                v
                for v in vehicles
                if v.status in GROUNDED_STATUSES
            ]

    return run_async(_query())


def _unground(vehicle_id, actor_role=None):
    async def _mutate():
        async with AsyncSessionLocal() as session:
            return await unground_vehicle(session, vehicle_id, actor_role=actor_role)

    return run_async(_mutate())


def _format_timestamp(ts):
    if ts is None:
        return "N/A"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    pacific = ts.astimezone(ZoneInfo("America/Los_Angeles"))
    return pacific.strftime("%m/%d/%Y %I:%M %p")


def _maintenance_notes(vehicle):
    if not vehicle.odometer_logs:
        return []
    return [
        log for log in vehicle.odometer_logs if log.notes
    ]


def render_maintenance_hub(actor_role=None):
    st.subheader("🔧 Maintenance & Override Hub")
    st.caption("Review grounded vehicles and recent maintenance notes, then un-ground after repairs.")

    # Task HD-5.3: Unground is restricted to Mechanics/Owners.
    can_unground = actor_role in UNGROUND_AUTHORIZED_ROLES
    if not can_unground:
        st.warning(
            f"Unground actions are restricted to **{', '.join(UNGROUND_AUTHORIZED_ROLES)}** "
            "roles. Your role (`"
            + (actor_role or "unknown")
            + "`) can review but cannot release grounded assets."
        )

    vehicles = _load_grounded()

    if not vehicles:
        st.success("No grounded vehicles. Your fleet is all clear!")
        return

    for vehicle in vehicles:
        with st.container(border=True):
            st.markdown(
                f"### 🚛 Truck #{vehicle.unit_number} — `{vehicle.status.upper()}`"
            )
            st.caption(
                f"VIN: {vehicle.vin or 'N/A'} | Current Odometer: {vehicle.current_odometer:,} mi"
            )

            notes = _maintenance_notes(vehicle)
            if notes:
                st.markdown("**Reported maintenance notes:**")
                for log in sorted(
                    notes, key=lambda n: n.logged_at, reverse=True
                ):
                    st.markdown(
                        f"- `{_format_timestamp(log.logged_at)}` — {log.notes}"
                    )
            else:
                st.caption("No maintenance notes on file for this vehicle.")

            if can_unground and st.button(
                f"Un-Ground Truck #{vehicle.unit_number}",
                key=f"unground_{vehicle.id}",
                type="primary",
            ):
                try:
                    updated = _unground(vehicle.id, actor_role=actor_role)
                    st.session_state["unground_success"] = (
                        f"Truck #{updated.unit_number} has been un-grounded and is back to Active!"
                    )
                    st.rerun()
                except PermissionError as pe:
                    st.error(str(pe))
                except Exception as ex:
                    st.error(f"Failed to un-ground vehicle: {ex}")

    if success_msg := st.session_state.pop("unground_success", None):
        st.toast(success_msg, icon="✅")
        st.success(success_msg)


def main():
    render_maintenance_hub()


if __name__ == "__main__":
    main()