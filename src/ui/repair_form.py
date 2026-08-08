import asyncio
import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from src.core.database import AsyncSessionLocal
from src.core.models import RepairReport
from src.core.services import (
    create_repair_report,
    get_driver_briefing,
    get_recent_repair_reports,
    ground_vehicle,
)
from src.ui.gps_component import gps_location

# Task DS-4.3: Structured 3-field mobile issue report.
REPAIR_CATEGORIES = RepairReport.REPAIR_CATEGORIES

# Local directory where driver-uploaded photos are persisted.
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def run_async(coro):
    return asyncio.run(coro)


def _ensure_upload_dir() -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR


def _load_briefing(driver_id):
    async def _query():
        async with AsyncSessionLocal() as session:
            return await get_driver_briefing(session, driver_id)

    return run_async(_query())


def _persist_report(report_data):
    async def _mutate():
        async with AsyncSessionLocal() as session:
            return await create_repair_report(session, **report_data)

    return run_async(_mutate())


def _ground_vehicle(vehicle_id):
    async def _mutate():
        async with AsyncSessionLocal() as session:
            return await ground_vehicle(session, vehicle_id)

    return run_async(_mutate())


def _save_photo(uploaded) -> str:
    """Persists an uploaded photo to the local uploads dir and returns its path."""
    ext = Path(uploaded.name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. Please upload an image file."
        )
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"repair_{stamp}{ext}"
    target = _ensure_upload_dir() / filename
    target.write_bytes(uploaded.getbuffer())
    return str(target)


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
    return f"{gps['lat']:.5f}, {gps['lng']:.5f}"


def render_repair_form(driver_id, driver_name=None):
    st.subheader("🧰 Repair Report")
    st.caption(
        "See a problem? Tap a category, describe the issue, and attach a photo. "
        "Your report goes straight to maintenance."
    )

    gps = gps_location()
    st.caption(f"📍 GPS: {_gps_summary(gps)}")
    st.divider()

    loads = _load_briefing(driver_id)
    first_load = loads[0] if loads else None

    with st.form(key="repair_report_form", clear_on_submit=True):
        category = st.selectbox(
            "Issue Category",
            options=list(REPAIR_CATEGORIES),
            help="Select the system most affected by the issue.",
        )

        description = st.text_area(
            "Description",
            placeholder="Describe the issue, when it started, any noises, warnings, etc.",
            height=110,
        )

        photo = st.file_uploader(
            "Photo (optional)",
            type=["jpg", "jpeg", "png", "webp", "gif", "bmp"],
            help="Attach a photo of the issue for the mechanic.",
        )

        submit = st.form_submit_button("Submit Repair Report", type="primary")

    if submit:
        if not description.strip():
            st.error("Please describe the issue before submitting.")
            return

        photo_path = None
        if photo is not None:
            try:
                photo_path = _save_photo(photo)
            except ValueError as ve:
                st.error(f"Photo upload failed: {ve}")
                return

        gps_lat = gps.get("lat") if gps else None
        gps_lng = gps.get("lng") if gps else None
        load_id = first_load.id if first_load else None
        vehicle_id = first_load.vehicle.id if first_load and first_load.vehicle else None

        try:
            report = _persist_report(
                {
                    "driver_id": driver_id,
                    "category": category,
                    "description": description.strip(),
                    "photo_path": photo_path,
                    "vehicle_id": vehicle_id,
                    "load_id": load_id,
                    "gps_lat": gps_lat,
                    "gps_lng": gps_lng,
                }
            )

            # Task HD-5.3: A safety issue report grounds the truck immediately so
            # dispatch is blocked until a Mechanic/Owner completes the repair.
            grounded = None
            if vehicle_id is not None:
                try:
                    grounded = _ground_vehicle(vehicle_id)
                except ValueError as gv:
                    # Already grounded — the report itself is the audit record
                    grounded = None
                    st.info(str(gv))

            st.session_state["repair_success"] = (
                f"Repair report #{report.id} for **{category}** submitted successfully.\n"
                f"Thank you — maintenance has been notified."
            )
            if grounded is not None:
                st.session_state["repair_success"] += (
                    f"\n🚛 Truck #{grounded.unit_number} has been **Grounded** "
                    f"pending repairs."
                )
            st.rerun()
        except Exception as ex:
            st.error(f"Failed to submit repair report: {ex}")

    # Recently submitted reports from this driver
    recent = _load_recent(driver_id)
    if recent:
        st.markdown("**📋 Your recent reports:**")
        for report in recent:
            st.markdown(
                f"- `{_format_timestamp(report.created_at)}` — **{report.category}** "
                f"(`{report.status}`)"
            )

    if success_msg := st.session_state.pop("repair_success", None):
        st.toast(success_msg, icon="✅")
        st.success(success_msg)


def _load_recent(driver_id):
    async def _query():
        async with AsyncSessionLocal() as session:
            return await get_recent_repair_reports(session, driver_id=driver_id, limit=4)

    return run_async(_query())


def main():
    render_repair_form(driver_id=2)


if __name__ == "__main__":
    main()