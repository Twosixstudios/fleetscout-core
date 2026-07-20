import streamlit as st
import requests
from sqlalchemy import select
from zoneinfo import ZoneInfo
from src.core.database import SessionLocal
from src.core.models import Vehicle, User, Load, OdometerLog
from src.core.services import update_vehicle_odometer

# Set page config
st.set_page_config(
    page_title="Fleet Scout Terminal",
    page_icon="�",
)


def format_timestamp(ts):
    """Converts a UTC timestamp to Pacific Time and formats as 'MM/DD/YYYY HH:MM AM/PM'."""
    if ts is None:
        return "N/A"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    pacific_time = ts.astimezone(ZoneInfo("America/Los_Angeles"))
    return pacific_time.strftime("%m/%d/%Y %I:%M %p")


def format_vehicle_option(vehicle):
    """Formats vehicle options for select boxes with Unit # and VIN fallback."""
    if not vehicle:
        return "Select a vehicle"
    unit = getattr(vehicle, "unit_number", "Unknown")
    vin = getattr(vehicle, "vin", None)
    vin_str = f" ({vin})" if vin else ""
    return f"Truck #{unit}{vin_str} | Odo: {vehicle.current_odometer:,} mi"


# ==========================================
# AUTHENTICATION & LOGIN (AR-2.1)
# ==========================================
def login():
    st.subheader("Login to Fleet Scout")
    with st.form(key="login_form", clear_on_submit=False):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button(label="Login")

        if submit_button:
            try:
                # 1. Authenticate against FastAPI OAuth2 endpoint
                response = requests.post(
                    "http://localhost:8000/api/auth/token",
                    data={"username": email, "password": password},
                )
                response.raise_for_status()
                data = response.json()

                # 2. Fetch User Record from DB to get actual assigned Role
                db = SessionLocal()
                try:
                    user = db.query(User).filter_by(email=email).first()
                    if not user:
                        st.error("Auth succeeded, but no user record was found in the database.")
                        return
                    user_role = user.role
                except Exception as db_err:
                    db.rollback()
                    st.error(f"Database error during user lookup: {db_err}")
                    return
                finally:
                    db.close()

                # 3. Store authentication and role state
                st.session_state["is_authenticated"] = True
                st.session_state["access_token"] = data["access_token"]
                st.session_state["user_email"] = email
                st.session_state["user_role"] = user_role

                # Set initial view mode based on role
                if user_role in ["Owner", "Dispatcher"]:
                    st.session_state["active_view"] = "Dispatch View"
                else:
                    st.session_state["active_view"] = "Driver View"

                st.success(f"Welcome back! Logged in as {user_role}.")
                st.rerun()
            except requests.exceptions.RequestException as e:
                st.error(f"Failed to log in: {e}")


# ==========================================
# DISPATCHER VIEWS
# ==========================================
def active_fleet():
    db = SessionLocal()
    try:
        st.subheader("Active Fleet Vehicles")
        with st.expander("Register New Vehicle"):
            with st.form(key="add_vehicle_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    unit_number = st.text_input("Unit Number (e.g. 101)")
                    make = st.text_input("Make (e.g. Freightliner)")
                    year = st.number_input("Year", min_value=1990, max_value=2030, value=2024)
                with col2:
                    vin = st.text_input("VIN (17 Characters)")
                    model = st.text_input("Model (e.g. Cascadia)")
                    initial_odometer = st.number_input("Initial Odometer (Miles)", min_value=0, value=0)

                status = st.selectbox("Status", ["Active", "In Transit", "Maintenance"])
                submit_vehicle = st.form_submit_button("Register Vehicle")

                if submit_vehicle:
                    if not unit_number.strip():
                        st.error("Unit Number is required.")
                    else:
                        try:
                            new_v = Vehicle(
                                unit_number=unit_number.strip(),
                                vin=vin.strip() if vin.strip() else None,
                                make=make.strip() if make.strip() else None,
                                model=model.strip() if model.strip() else None,
                                year=int(year),
                                current_odometer=int(initial_odometer),
                                status=status,
                                carrier_id=1,
                            )
                            db.add(new_v)
                            db.commit()
                            st.success(f"Vehicle #{unit_number} registered successfully!")
                            st.rerun()
                        except IntegrityError:
                            db.rollback()
                            st.error("Registration failed: A vehicle with this Unit Number or VIN is already registered in the system.")
                        except Exception as ex:
                            db.rollback()
                            st.error(f"Failed to register vehicle: {ex}")

        stmt = select(Vehicle)
        results = db.execute(stmt).scalars().all()

        if results:
            data = [
                {
                    "Vehicle ID": v.id,
                    "Unit #": v.unit_number,
                    "VIN": v.vin or "N/A",
                    "Make/Model/Year": f"{v.year or ''} {v.make or ''} {v.model or ''}".strip() or "N/A",
                    "Current Odometer": f"{v.current_odometer:,} mi",
                    "Status": v.status,
                }
                for v in results
            ]
            st.dataframe(data, use_container_width=True)
        else:
            st.info("No active vehicles currently reported.")
    except Exception as e:
        db.rollback()
        st.error(f"Error connecting to the fleet database: {e}")
    finally:
        db.close()


def odometer_updates():
    db = SessionLocal()
    try:
        st.subheader("Odometer & Maintenance Logging")

        stmt_v = select(Vehicle)
        vehicles = db.execute(stmt_v).scalars().all()

        if not vehicles:
            st.warning("No vehicles available in the database. Please register a vehicle first under 'Active Fleet'.")
            return

        with st.expander("Log New Odometer Reading", expanded=True):
            with st.form(key="add_odo_form", clear_on_submit=True):
                selected_vehicle = st.selectbox(
                    "Select Vehicle",
                    options=vehicles,
                    format_func=format_vehicle_option,
                )
                new_reading = st.number_input("New Odometer Reading (Miles)", min_value=0, step=1)
                notes = st.text_input("Notes (e.g., Scheduled PM, Driver Shift Change)")
                submit_odo = st.form_submit_button("Submit Update")

                if submit_odo:
                    if not selected_vehicle:
                        st.error("Please select a valid vehicle.")
                    else:
                        try:
                            update_vehicle_odometer(
                                db=db,
                                vehicle_id=selected_vehicle.id,
                                new_reading=int(new_reading),
                                notes=notes if notes.strip() else None,
                            )
                            st.success(
                                f"Odometer updated for Truck #{selected_vehicle.unit_number} to {new_reading:,} miles!"
                            )
                            st.rerun()
                        except ValueError as ve:
                            st.error(str(ve))

        st.subheader("Odometer Audit History")
        stmt_o = select(OdometerLog).order_by(OdometerLog.logged_at.desc())
        results_o = db.execute(stmt_o).scalars().all()

        if results_o:
            data_o = [
                {
                    "Log ID": o.id,
                    "Truck #": o.vehicle.unit_number if o.vehicle else f"ID: {o.vehicle_id}",
                    "Odometer Reading": f"{o.reading:,} mi",
                    "Notes": o.notes or "-",
                    "Logged At": format_timestamp(o.logged_at),
                }
                for o in results_o
            ]
            st.dataframe(data_o, use_container_width=True)
        else:
            st.info("No odometer logs recorded yet.")
    except Exception as e:
        db.rollback()
        st.error(f"Error connecting to the database: {e}")
    finally:
        db.close()


def active_loads():
    db = SessionLocal()
    try:
        st.subheader("Active Loads")
        stmt = select(Load)
        results = db.execute(stmt).scalars().all()

        if results:
            data = [
                {
                    "Load #": l.load_number,
                    "Commodity": l.commodity,
                    "Weight (lbs)": f"{l.load_weight:,}",
                    "Pickup Ref": l.pickup_ref,
                    "Delivery Ref": l.delivery_ref,
                    "Status": l.status,
                }
                for l in results
            ]
            st.dataframe(data, use_container_width=True)
        else:
            st.info("No active loads available.")
    except Exception as e:
        db.rollback()
        st.error(f"Error connecting to the fleet database: {e}")
    finally:
        db.close()


# ==========================================
# DRIVER VIEW (MOBILE OPTIMIZED)
# ==========================================
def driver_console():
    st.subheader("� Driver Mobile Terminal")
    st.info("Welcome to your on-road console. Keep your odometer logs updated before and after shift trips.")

    db = SessionLocal()
    try:
        stmt_v = select(Vehicle)
        vehicles = db.execute(stmt_v).scalars().all()

        if vehicles:
            st.markdown("### Assigned / Active Fleet Quick Overview")
            for v in vehicles:
                with st.container():
                    st.markdown(f"**Truck #{v.unit_number}** — `{v.status}`")
                    st.caption(f"VIN: {v.vin or 'N/A'} | Current Odometer: **{v.current_odometer:,} mi**")
                    st.divider()
        else:
            st.info("No active vehicles currently assigned.")
    except Exception as e:
        db.rollback()
        st.error(f"Error loading driver console: {e}")
    finally:
        db.close()


# ==========================================
# MAIN ROUTING & HAT-SWITCHER (AR-2.2 & AR-2.3)
# ==========================================
def main():
    st.title("Fleet Scout Terminal")
    st.markdown("### Two Six Studios")

    if "is_authenticated" not in st.session_state:
        st.session_state["is_authenticated"] = False

    if not st.session_state["is_authenticated"]:
        menu = st.sidebar.selectbox("Navigation", ["Login"])
        if menu == "Login":
            login()
        return

    # User Header Info
    user_email = st.session_state.get("user_email", "User")
    user_role = st.session_state.get("user_role", "Driver")

    st.sidebar.markdown(f"Logged in as: **{user_email}**")
    st.sidebar.markdown(f"Assigned Role: **`{user_role}`**")

    # AR-2.3: Owner Role Toggle (Hat-Switcher)
    if user_role == "Owner":
        st.sidebar.divider()
        st.sidebar.markdown("### � Owner Hat-Switcher")
        owner_view_choice = st.sidebar.radio(
            "Select Viewport Mode:",
            ["Dispatch View", "Driver View"],
            index=0 if st.session_state.get("active_view") == "Dispatch View" else 1,
        )
        st.session_state["active_view"] = owner_view_choice

    elif user_role == "Dispatcher":
        st.session_state["active_view"] = "Dispatch View"
    else:
        st.session_state["active_view"] = "Driver View"

    active_view = st.session_state.get("active_view", "Dispatch View")
    st.sidebar.caption(f"Active Mode: **{active_view}**")

    if st.sidebar.button("Logout"):
        st.session_state["is_authenticated"] = False
        st.session_state["access_token"] = None
        st.session_state["user_role"] = None
        st.rerun()

    st.sidebar.divider()

    # AR-2.2: Routing Logic based on Active View
    if active_view == "Dispatch View":
        menu = st.sidebar.selectbox("Navigation", ["Active Fleet", "Odometer Updates", "Active Loads"])
        if menu == "Active Fleet":
            active_fleet()
        elif menu == "Odometer Updates":
            odometer_updates()
        elif menu == "Active Loads":
            active_loads()

    elif active_view == "Driver View":
        menu = st.sidebar.selectbox("Navigation", ["Driver Console", "Log Odometer"])
        if menu == "Driver Console":
            driver_console()
        elif menu == "Log Odometer":
            odometer_updates()


if __name__ == "__main__":
    main()