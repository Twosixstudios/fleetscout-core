import asyncio
from datetime import timezone

import streamlit as st
from sqlalchemy import select

from src.core.database import AsyncSessionLocal, SessionLocal
from src.core.exceptions import SafetyViolationError
from src.core.models import User, Vehicle
from src.core.services import create_dispatched_load
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

    with st.form(key="dispatch_load_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            load_number = st.text_input("Load Number")
            commodity = st.text_input("Commodity")
        with col2:
            load_weight = st.number_input("Load Weight (lbs)", min_value=0, step=1)
            pickup_ref = st.text_input("Pickup Reference")
        with col3:
            delivery_ref = st.text_input("Delivery Reference")

        st.markdown("**Addresses & Target Times (optional)**")
        addr_col1, addr_col2 = st.columns(2)
        with addr_col1:
            pickup_address = st.text_input("Pickup Address")
            target_pickup_at = st.text_input(
                "Target Pickup (MM/DD/YYYY HH:MM AM/PM)",
                help="e.g. 08/07/2026 06:00 AM",
            )
        with addr_col2:
            delivery_address = st.text_input("Delivery Address")
            target_delivery_at = st.text_input(
                "Target Delivery (MM/DD/YYYY HH:MM AM/PM)",
                help="e.g. 08/07/2026 04:00 PM",
            )

        dispatcher_notes = st.text_area("Dispatcher Notes")

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

        submit = st.form_submit_button("Dispatch Load")

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
                st.session_state["dispatch_success"] = (
                    f"Load {new_load.load_number} dispatched to {driver_label} on {vehicle_label}!"
                )
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