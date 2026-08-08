import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from src.core.database import AsyncSessionLocal
from src.core.services import get_driver_briefing, update_load_status
from src.ui.gps_component import gps_location

# Task DS-4.2: One-tap status toggles for a driver's active load.
DRIVER_STATUSES = [
    {"key": "at_shipper", "label": "At Shipper", "icon": "🏭", "hue": "ok"},
    {"key": "loaded", "label": "Loaded", "icon": "📦", "hue": "ok"},
    {"key": "en_route", "label": "En Route", "icon": "🚛", "hue": "ok"},
    {"key": "delivered", "label": "Delivered", "icon": "✅", "hue": "ok"},
]

ACTIVE_STATUSES = ("dispatched", "at_shipper", "loaded", "en_route", "delivered")


def run_async(coro):
    return asyncio.run(coro)


def _load_briefing(driver_id):
    async def _query():
        async with AsyncSessionLocal() as session:
            loads = await get_driver_briefing(session, driver_id)
            return [
                load
                for load in loads
                if load.status in ACTIVE_STATUSES
            ]

    return run_async(_query())


def _apply_status(load_id, status, gps=None):
    gps_lat = gps.get("lat") if gps else None
    gps_lng = gps.get("lng") if gps else None

    async def _mutate():
        async with AsyncSessionLocal() as session:
            return await update_load_status(
                session,
                load_id,
                status,
                gps_lat=gps_lat,
                gps_lng=gps_lng,
            )

    return run_async(_mutate())


def _format_timestamp(ts):
    if ts is None:
        return "N/A"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    pacific = ts.astimezone(ZoneInfo("America/Los_Angeles"))
    return pacific.strftime("%m/%d/%Y %I:%M %p")


def _gps_summary(gps):
    if not gps:
        return "📍 Location unavailable"
    if gps.get("demo"):
        return gps.get("label") or "📍 GPS: Live Demo Telemetry (I-10 / LA Corridor)"
    return f"📍 {gps['lat']:.5f}, {gps['lng']:.5f}"


def _utc_now():
    return datetime.now(timezone.utc)


def render_status_toggles(driver_id, driver_name=None):
    st.subheader("🎛️ One-Tap Status Toggles")
    st.caption(
        "Mark your current stage with a single tap. Updates log your GPS position and a timestamp."
    )

    loads = _load_briefing(driver_id)

    if not loads:
        st.info("No active loads to update right now. Your status controls appear here once a load is dispatched to you.")
        return

    st.markdown("**🛰️ GPS Position**")
    gps = gps_location(key="fleetscout_gps_toggles")
    st.caption(f"{_gps_summary(gps)}")

    st.divider()

    for load in loads:
        with st.container(border=True):
            st.markdown(
                f"### 📦 Load **{load.load_number}** — `{load.status.upper()}`"
            )

            cols = st.columns(len(DRIVER_STATUSES))
            for col, opt in zip(cols, DRIVER_STATUSES):
                with col:
                    current = load.status == opt["key"]
                    if st.button(
                        f"{opt['icon']} {opt['label']}",
                        key=f"status_{load.id}_{opt['key']}",
                        type="primary" if current else "secondary",
                        use_container_width=True,
                    ):
                        try:
                            log = _apply_status(load.id, opt["key"], gps)
                            st.session_state["toggle_success"] = (
                                f"Load {load.load_number} updated to **{opt['label']}** "
                                f"at {_format_timestamp(log.timestamp)}."
                            )
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Failed to update status: {ex}")

            last_log = (getattr(load, 'status_logs', None) or [None])[0]
            st.caption(
                f"Last update: {_format_timestamp(last_log.timestamp) if last_log else 'No status logged yet'}"
            )

            st.divider()

    if success_msg := st.session_state.pop("toggle_success", None):
        st.toast(success_msg, icon="✅")
        st.success(success_msg)


def main():
    render_status_toggles(driver_id=2)


if __name__ == "__main__":
    main()