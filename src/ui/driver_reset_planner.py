import asyncio
from zoneinfo import ZoneInfo

import streamlit as st

from src.core.database import AsyncSessionLocal
from src.core.models import DutyLog
from src.core.services import (
    get_duty_summary,
    get_recent_duty_logs,
    log_duty_start,
)
from src.ui.gps_component import gps_location

# Task DS-4.4: Reset Planner & HOS Duty Clock.
DUTY_STATES = DutyLog.DUTY_STATES
REST_HOURS = DutyLog.REST_HOURS

# TASK-7.1: FMCSA statutory limits rendered as READ-ONLY badges.
HOS_DRIVING_WINDOW_HOURS = 11
HOS_SHIFT_WINDOW_HOURS = 14
HOS_SLEEPER_REST_HOURS = 10

# FMCSA compliance disclaimer shown whenever the duty clock is rendered.
DISCLAIMER = (
    "DISCLAIMER: This tracker is provided for internal dispatch estimations and "
    "carrier scheduling only. It is NOT an FMCSA-compliant ELD/AOBRD logbook and "
    "must not be used as an official Record of Duty Status (RODS). Drivers and "
    "carriers are required to maintain official logs through certified ELD providers."
)


def run_async(coro):
    return asyncio.run(coro)


def _apply_duty_start(driver_id, duty_state, gps=None):
    gps_lat = gps.get("lat") if gps else None
    gps_lng = gps.get("lng") if gps else None

    async def _mutate():
        async with AsyncSessionLocal() as session:
            return await log_duty_start(
                session,
                driver_id,
                duty_state,
                gps_lat=gps_lat,
                gps_lng=gps_lng,
            )

    return run_async(_mutate())


def _load_summary(driver_id):
    async def _query():
        async with AsyncSessionLocal() as session:
            return await get_duty_summary(session, driver_id)

    return run_async(_query())


def _load_recent(driver_id):
    async def _query():
        async with AsyncSessionLocal() as session:
            return await get_recent_duty_logs(session, driver_id=driver_id, limit=6)

    return run_async(_query())


def _format_timestamp(ts):
    if ts is None:
        return "N/A"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    pacific = ts.astimezone(ZoneInfo("America/Los_Angeles"))
    return pacific.strftime("%m/%d/%Y %I:%M %p")


def _gps_summary(gps):
    if not gps:
        return "Location unavailable"
    if gps.get("demo"):
        return gps.get("label") or "Live Demo Telemetry (I-10 / LA Corridor)"
    return f"{gps['lat']:.5f}, {gps['lng']:.5f}"


def _format_remaining(seconds):
    if seconds is None:
        return "Not currently resting"
    hours, rem = divmod(int(seconds), 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}h {minutes:02d}m {secs:02d}s"


def _render_availability_clock(summary, latest=None):
    """Render the 10-hour availability countdown block (shared read-only logic)."""
    latest = latest if latest is not None else summary["latest_log"]

    st.markdown("**🛏️ Sleeper Rest Timer / 10-Hour Availability**")
    if latest is None:
        st.info("No duty logged yet. Select a duty state above to start the clock.")
    elif latest.target_available_at is None:
        st.caption("Latest duty state logged — no rest countdown is active.")
        st.markdown(f"`{latest.duty_state}` — {_format_timestamp(latest.created_at)}")
    else:
        remaining = summary["seconds_remaining"]
        if summary["is_resting"]:
            st.markdown(
                f"> **Resting since:** {_format_timestamp(summary['off_duty_started_at'])}"
            )
            st.markdown(
                f"> **Available to drive in:** :green[**{_format_remaining(remaining)}**]"
            )
            st.markdown(
                f"> **Availability return at:** {_format_timestamp(summary['target_available_at'])}"
            )
            st.progress(
                min(1.0, (REST_HOURS * 3600 - remaining) / (REST_HOURS * 3600))
                if (REST_HOURS * 3600) > 0
                else 0.0,
                text="Rest progress",
            )
        else:
            st.success("You are fully rested and available to drive! 🚛")


def render_hos_read_only(driver_id, driver_name=None):
    """TASK-7.1: FMCSA read-only HOS status badges & availability clock.

    Strictly read-only — the interactive Duty Status toggles (Driving /
    On Duty / Off Duty / Sleeper) are intentionally absent, so Owner and
    Dispatcher views can only *view* driver hour availability for scheduling,
    never modify a driver's logbook directly.
    """
    st.subheader("🕐 Driver Hours of Service (Read-Only)")
    st.caption(
        "FMCSA limits displayed for scheduling visibility only — no driver "
        "log edits are allowed from this view."
    )
    st.warning(DISCLAIMER)

    summary = _load_summary(driver_id)
    latest = summary["latest_log"]

    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Driving Window", f"{HOS_DRIVING_WINDOW_HOURS}h / 24h")
    b2.metric("Shift Window", f"{HOS_SHIFT_WINDOW_HOURS}h / 24h")
    b3.metric("Sleeper Rest", f"{HOS_SLEEPER_REST_HOURS}h")
    b4.metric("Duty Status", latest.duty_state if latest else "No duty logged")

    st.divider()
    _render_availability_clock(summary, latest)

    if latest:
        st.markdown(
            f"**Latest duty log:** `{latest.duty_state}`"
            f" — {_format_timestamp(latest.created_at)}"
        )


def render_driver_reset_planner(driver_id, driver_name=None, read_only=False):
    if read_only:
        render_hos_read_only(driver_id, driver_name=driver_name)
        return

    st.subheader("⏰ Reset Planner & HOS Duty Clock")
    st.caption(
        "Log your current duty state. Going 'Off Duty' or 'Sleeper Berth' starts "
        f"your **{REST_HOURS}-hour availability return countdown**."
    )

    st.warning(DISCLAIMER)

    gps = gps_location()
    st.caption(f"📍 GPS: {_gps_summary(gps)}")

    st.divider()

    # Duty State Selector
    st.markdown("**🎛️ Duty State Selector**")
    cols = st.columns(len(DUTY_STATES))
    for col, state in zip(cols, DUTY_STATES):
        with col:
            if st.button(
                state,
                key=f"duty_{state}",
                type="primary" if state in ("Off Duty", "Sleeper Berth") else "secondary",
                use_container_width=True,
            ):
                try:
                    log = _apply_duty_start(driver_id, state, gps)
                    st.session_state["duty_success"] = (
                        f"Duty state updated to **{state}** "
                        f"at {_format_timestamp(log.created_at)}."
                    )
                    st.rerun()
                except ValueError as ve:
                    st.error(str(ve))
                except Exception as ex:
                    st.error(f"Failed to log duty state: {ex}")

    st.divider()

    # 10-hour availability clock (read-only availability block)
    _render_availability_clock(_load_summary(driver_id))

    st.divider()

    # Recent duty history
    recent = _load_recent(driver_id)
    if recent:
        st.markdown("**📋 Your recent duty log:**")
        for entry in recent:
            st.markdown(
                f"- `{_format_timestamp(entry.created_at)}` — **{entry.duty_state}**"
            )

    if success_msg := st.session_state.pop("duty_success", None):
        st.toast(success_msg, icon="✅")
        st.success(success_msg)


def main():
    render_driver_reset_planner(driver_id=2)


if __name__ == "__main__":
    main()