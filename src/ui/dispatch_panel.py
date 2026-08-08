import asyncio
from datetime import timezone

import streamlit as st
from sqlalchemy import select

from src.core.database import AsyncSessionLocal, SessionLocal
from src.core.exceptions import SafetyViolationError
from src.core.models import User, Vehicle
from src.core.ratecon_parser import (
    RateConfirmationParseError,
    parse_rate_confirmation_bytes,
    ratecon_to_form,
)
from src.core.services import create_authorized_load, create_dispatched_load
from src.ui.yard_board import fetch_data, render_yard_board


def run_async(coro):
    return asyncio.run(coro)


def _parse_target_time(value):
    """Parses 'MM/DD/YYYY HH:MM AM/PM' into a UTC-aware datetime, or None."""
    if not value or not value.strip():
        return None
    from datetime import datetime
    try:
        naive = datetime.strptime(value.strip(), "%m/%d/%Y %I:%M %p")
        return naive.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _active_assignments():
    with SessionLocal() as db:
        drivers = (
            db.execute(
                select(User).where(User.role == "Driver", User.is_active == True)
            )
            .scalars()
            .all()
        )
        vehicles = (
            db.execute(select(Vehicle).where(Vehicle.status == "Active"))
            .scalars()
            .all()
        )
        return drivers, vehicles


def render_dispatch_panel():
    st.subheader("🚚 Load Creation & Dispatch Panel")
    st.caption("Create a new load, assign it to a driver + active vehicle, and dispatch it to the yard board.")

    drivers, vehicles = _active_assignments()

    # TASK-6.5: FreightSlip rate confirmation PDF import (HITL gated).
    uploaded_pdf = st.file_uploader(
        "📄 Import Rate Confirmation PDF (FreightSlip AI)",
        type=["pdf"],
        key="ratecon_pdf_upload",
        help="FreightSlip parses broker, rate, pickup/delivery, weight, and "
        "references into the form below.",
    )

    staging_key = "ratecon_staged"
    staged = st.session_state.get(staging_key)
    if uploaded_pdf is not None:
        raw = uploaded_pdf.getvalue()
        committed_bytes = st.session_state.get("ratecon_committed_bytes")
        if committed_bytes != raw:
            st.session_state.pop("ratecon_committed", None)
            try:
                staged = parse_rate_confirmation_bytes(raw)
                st.session_state[staging_key] = staged
            except RateConfirmationParseError as parse_err:
                st.error(str(parse_err))
                st.session_state.pop(staging_key, None)
                staged = None

    auto_fill = ratecon_to_form(staged) if staged else {}

    # HITL guardrail: auto-filled fields are surfaced for inspection and the
    # commit is blocked until the Operator clicks the Authorize button.
    if staged:
        st.warning(
            "⚠️ **Verify Extracted FreightSlip Data:** *Please inspect all "
            "auto-filled fields against your original PDF rate confirmation "
            "before authorizing.*"
        )

    with st.form(key="dispatch_load_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            load_number = st.text_input(
                "Load Number", value=auto_fill.get("load_number", "")
            )
            commodity = st.text_input("Commodity", value=auto_fill.get("commodity", ""))
        with col2:
            default_weight = int(auto_fill["load_weight"]) if auto_fill.get("load_weight") else 0
            load_weight = st.number_input(
                "Load Weight (lbs)", min_value=0, step=1, value=default_weight
            )
            pickup_ref = st.text_input(
                "Pickup Reference", value=auto_fill.get("pickup_ref", "")
            )
        with col3:
            delivery_ref = st.text_input(
                "Delivery Reference", value=auto_fill.get("delivery_ref", "")
            )

        st.markdown("**Addresses & Target Times (optional)**")
        addr_col1, addr_col2 = st.columns(2)
        with addr_col1:
            pickup_address = st.text_input(
                "Pickup Address", value=auto_fill.get("pickup_address", "")
            )
            target_pickup_at = st.text_input(
                "Target Pickup (MM/DD/YYYY HH:MM AM/PM)",
                value=auto_fill.get("target_pickup_at", ""),
                help="e.g. 08/07/2026 06:00 AM",
            )
        with addr_col2:
            delivery_address = st.text_input(
                "Delivery Address", value=auto_fill.get("delivery_address", "")
            )
            target_delivery_at = st.text_input(
                "Target Delivery (MM/DD/YYYY HH:MM AM/PM)",
                value=auto_fill.get("target_delivery_at", ""),
                help="e.g. 08/07/2026 04:00 PM",
            )

        dispatch_note_default = ""
        if basic_notes := auto_fill.get("dispatcher_notes"):
            dispatch_note_default = basic_notes
        dispatcher_notes = st.text_area(
            "Dispatcher Notes", value=dispatch_note_default
        )

        driver_options = {f"{d.username or d.email} (ID {d.id})": d.id for d in drivers}
        driver_label = st.selectbox(
            "Driver Assignment",
            options=list(driver_options),
            help="Assign this load to an active driver.",
        )

        vehicle_options = {
            f"Truck #{v.unit_number} (ID {v.id})": v.id for v in vehicles
        }
        vehicle_label = st.selectbox(
            "Assign Vehicle (Active)",
            options=list(vehicle_options),
            help="Active vehicle this load will be dispatched to.",
        )

        # HITL: when rateconfirmation data is staged, the submit action is the
        # explicit human authorization → the only write path to the database.
        submit_label = "✅ Authorize & Commit Load" if staged else "Dispatch Load"
        submit = st.form_submit_button(submit_label)

        if submit:
            assigned_driver_id = driver_options.get(driver_label)
            assigned_vehicle_id = vehicle_options.get(vehicle_label)

            if not assigned_driver_id:
                st.error("Dispatch failed: No active driver available to assign.")
            elif not assigned_vehicle_id:
                st.error("Dispatch failed: No active vehicle available to assign.")
            elif not load_number.strip():
                st.error("Load Number is required.")
            else:
                parsed_pickup = _parse_target_time(target_pickup_at)
                parsed_delivery = _parse_target_time(target_delivery_at)
                if (target_pickup_at and target_pickup_at.strip() and not parsed_pickup) or (
                    target_delivery_at and target_delivery_at.strip() and not parsed_delivery
                ):
                    st.error(
                        "Target time format invalid. Use MM/DD/YYYY HH:MM AM/PM (e.g. 08/07/2026 04:00 PM)."
                    )
                    return
                try:
                    async def _insert():
                        async with AsyncSessionLocal() as session:
                            if staged:
                                # TASK-6.5 HITL: the submit button clicked was the
                                # explicit "✅ Authorize & Commit Load" human check.
                                return await create_authorized_load(
                                    session=session,
                                    human_authorized=True,
                                    load_number=load_number.strip(),
                                    load_weight=int(load_weight),
                                    commodity=commodity.strip(),
                                    pickup_ref=pickup_ref.strip(),
                                    delivery_ref=delivery_ref.strip(),
                                    pickup_address=pickup_address.strip() if pickup_address.strip() else None,
                                    delivery_address=delivery_address.strip() if delivery_address.strip() else None,
                                    target_pickup_at=parsed_pickup,
                                    target_delivery_at=parsed_delivery,
                                    dispatcher_notes=dispatcher_notes.strip() if dispatcher_notes.strip() else None,
                                    assigned_driver_id=assigned_driver_id,
                                    assigned_vehicle_id=assigned_vehicle_id,
                                )
                            return await create_dispatched_load(
                                session=session,
                                load_number=load_number.strip(),
                                load_weight=int(load_weight),
                                commodity=commodity.strip(),
                                pickup_ref=pickup_ref.strip(),
                                delivery_ref=delivery_ref.strip(),
                                pickup_address=pickup_address.strip() if pickup_address.strip() else None,
                                delivery_address=delivery_address.strip() if delivery_address.strip() else None,
                                target_pickup_at=parsed_pickup,
                                target_delivery_at=parsed_delivery,
                                dispatcher_notes=dispatcher_notes.strip() if dispatcher_notes.strip() else None,
                                assigned_driver_id=assigned_driver_id,
                                assigned_vehicle_id=assigned_vehicle_id,
                            )

                    new_load = run_async(_insert())
                    if uploaded_pdf is not None:
                        st.session_state["ratecon_committed_bytes"] = uploaded_pdf.getvalue()
                    st.session_state.pop(staging_key, None)
                    st.session_state["dispatch_success"] = (
                        f"Load {new_load.load_number} dispatched to {driver_label} on {vehicle_label}!"
                    )
                    st.rerun()
                except PermissionError as hitl_err:
                    # TASK-6.5: human authorization never silently skipped.
                    st.session_state["dispatch_blocked"] = str(hitl_err)
                    st.rerun()
                except SafetyViolationError as sve:
                    # Task HD-5.3: user-friendly alert when the safety interceptor
                    # (HD-5.2) blocks an assignment to a Grounded truck.
                    st.session_state["dispatch_blocked"] = str(sve)
                    st.rerun()
                except Exception as ex:
                    st.error(f"Failed to dispatch load: {ex}")

    # Auto-refresh: show success toast on the rerun triggered by dispatch
    if success_msg := st.session_state.pop("dispatch_success", None):
        st.toast(success_msg, icon="✅")
        st.success(success_msg)

    # Task HD-5.3: Surface the safety lockout as a prominent alert
    if blocked_msg := st.session_state.pop("dispatch_blocked", None):
        st.toast(blocked_msg, icon="🛑")
        st.error(blocked_msg)

    st.divider()

    # Yard Board grid that auto-refreshes after a new dispatch
    vehicles_data, users, loads = fetch_data()
    render_yard_board(vehicles_data, users, loads)


def main():
    render_dispatch_panel()


if __name__ == "__main__":
    main()