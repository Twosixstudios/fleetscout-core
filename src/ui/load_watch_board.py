import asyncio
from zoneinfo import ZoneInfo

import streamlit as st

from src.core.database import AsyncSessionLocal
from src.core.services import get_active_loads

ACTIVE_STATUSES = ("dispatched", "en_route", "at_shipper", "delivered")
STATUS_STAGES = {
    "dispatched": 0,
    "en_route": 1,
    "at_shipper": 2,
    "delivered": 3,
}
STATUS_ICONS = {
    "dispatched": "📦",
    "en_route": "🚛",
    "at_shipper": "🏭",
    "delivered": "✅",
}


def run_async(coro):
    return asyncio.run(coro)


def _load_active():
    async def _query():
        async with AsyncSessionLocal() as session:
            loads = await get_active_loads(session)
            return [
                load
                for load in loads
                if load.status in ACTIVE_STATUSES
            ]

    return run_async(_query())


def _format_timestamp(ts):
    if ts is None:
        return "N/A"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    pacific = ts.astimezone(ZoneInfo("America/Los_Angeles"))
    return pacific.strftime("%m/%d/%Y %I:%M %p")


def render_load_watch_board():
    st.subheader("📡 Active Load Watch Board")
    st.caption("Real-time progress timelines for all dispatched loads.")

    loads = _load_active()

    if not loads:
        st.info("No active dispatched loads right now.")
        return

    with st.expander("🔁 Auto-Refresh", expanded=False):
        st.caption("Rerun this page (or use Streamlit's auto-rerun) to pull the latest statuses from the database.")

    for load in loads:
        status = load.status
        stage = STATUS_STAGES.get(status, 0)
        icon = STATUS_ICONS.get(status, "📦")

        driver_name = (
            load.driver.username or load.driver.email
            if load.driver
            else "Unassigned"
        )
        vehicle_name = (
            f"Truck #{load.vehicle.unit_number}"
            if load.vehicle
            else "No Vehicle"
        )

        with st.container(border=True):
            st.markdown(
                f"### {icon} Load **{load.load_number}** — `{status.upper()}`"
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"**Commodity:** {load.commodity}")
                st.markdown(f"**Weight:** {load.load_weight:,} lbs")
            with col2:
                st.markdown(f"**Driver:** {driver_name}")
                st.markdown(f"**Vehicle:** {vehicle_name}")
            with col3:
                st.markdown(f"**Pickup Ref:** {load.pickup_ref}")
                st.markdown(f"**Delivery Ref:** {load.delivery_ref}")

            st.progress(
                (stage + 1) / len(STATUS_STAGES),
                text=f"Stage {stage + 1} of {len(STATUS_STAGES)}",
            )

            st.markdown("**Timeline (UTC timestamps):**")
            if load.status_logs:
                for log in sorted(
                    load.status_logs, key=lambda l: l.timestamp, reverse=True
                ):
                    st.markdown(
                        f"`{log.status.upper()}` — {_format_timestamp(log.timestamp)}"
                    )
            else:
                st.caption("No status updates logged yet.")

            if load.dispatcher_notes:
                st.caption(f"📝 Dispatcher Notes: {load.dispatcher_notes}")

            st.divider()


def main():
    render_load_watch_board()


if __name__ == "__main__":
    main()