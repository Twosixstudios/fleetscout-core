import streamlit as st
from sqlalchemy.orm import Session
from src.core.database import SessionLocal
from src.core.models import Vehicle, User, Load

st.set_page_config(page_title="Yard Board", layout="wide")

def fetch_data():
    with SessionLocal() as session:
        from sqlalchemy.orm import joinedload

        vehicles = session.query(Vehicle).options(joinedload(Vehicle.assigned_loads)).all()
        users = {user.id: user for user in session.query(User).all()}
        loads = {load.id: load for load in session.query(Load).all()}
        return vehicles, users, loads

def render_yard_board(vehicles, users, loads):
    st.title("Interactive Yard Board")

    status_filter = st.sidebar.multiselect(
        "Filter Vehicle Status",
        options=["Active", "Grounded"],
        default=["Active", "Grounded"]
    )

    table_data = []
    for vehicle in vehicles:
        if vehicle.status not in status_filter:
            continue

        driver_name = "Unassigned"
        load_number = "No Load Assigned"

        if vehicle.assigned_loads:
            first_load = vehicle.assigned_loads[0]
            load_number = first_load.load_number if first_load else "No Load Assigned"
            if first_load.assigned_driver_id in users:
                driver_name = users[first_load.assigned_driver_id].username

        table_data.append({
            "Unit Number": vehicle.unit_number,
            "Status": "✅ Active" if vehicle.status == "Active" else "❌ Grounded",
            "Assigned Driver": driver_name,
            "Active Load #": load_number
        })

    st.dataframe(table_data, use_container_width=True)

def main():
    vehicles, users, loads = fetch_data()
    render_yard_board(vehicles, users, loads)

if __name__ == "__main__":
    main()
