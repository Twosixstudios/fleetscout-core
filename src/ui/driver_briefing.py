import asyncio
from zoneinfo import ZoneInfo

import streamlit as st

from src.core.database import AsyncSessionLocal
from src.core.services import get_driver_briefing


def run_async(coro):
    return asyncio.run(coro)


def _load_briefing(driver_id):
    async def _query():
        async with AsyncSessionLocal() as session:
            loads = await get_driver_briefing(session, driver_id)
            return loads

    return run_async(_query())


def _format_target_time(ts):
    if ts is None:
        return "Not set"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    pacific = ts.astimezone(ZoneInfo("America/Los_Angeles"))
    return pacific.strftime("%m/%d/%Y %I:%M %p")


def _location(address, ref):
    if address and address.strip():
        return address.strip()
    if ref and ref.strip():
        return f"{ref.strip()} (ref only)"
    return "TBD"


def render_driver_briefing(driver_id, driver_name=None):
    st.subheader("📋 Quick-Ref Load Briefing")
    st.caption(
        "Your assigned active loads at a glance. Tap each card for pickup, delivery, and dispatcher notes."
    )

    loads = _load_briefing(driver_id)

    if not loads:
        st.info("No active loads assigned to you right now. Check back after dispatch.")
        return

    for load in loads:
        with st.container(border=True):
            st.markdown(f"### 📦 Load **{load.load_number}** — `{load.status.upper()}`")
            st.caption(
                f"Commodity: **{load.commodity}** | Weight: **{load.load_weight:,} lbs**"
            )

            pickup_col, delivery_col = st.columns(2)
            with pickup_col:
                st.markdown("**📍 Pickup**")
                st.markdown(f"{_location(load.pickup_address, load.pickup_ref)}")
                st.caption(
                    f"Target: {_format_target_time(load.target_pickup_at)}"
                )
            with delivery_col:
                st.markdown("**🏁 Delivery**")
                st.markdown(f"{_location(load.delivery_address, load.delivery_ref)}")
                st.caption(
                    f"Target: {_format_target_time(load.target_delivery_at)}"
                )

            if load.dispatcher_notes:
                st.markdown("**📝 Dispatcher Notes**")
                st.markdown(f"> {load.dispatcher_notes}")

            if load.vehicle:
                st.caption(
                    f"Assigned Truck: **#{load.vehicle.unit_number}**"
                )

            st.divider()


def main():
    render_driver_briefing(driver_id=2)


if __name__ == "__main__":
    main()
