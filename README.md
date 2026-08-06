Markdown
# 🚛 FleetScout Core

A lightweight, role-based fleet management and dispatch orchestration system built with Python, Streamlit, SQLAlchemy, and SQLite. Designed by Two Six Studios.

---

## 🎯 Active Status & Roadmap Progress
* **Current Status:** Phase 3 Complete (Desktop Dispatch Portal)
* **Overall Progress:** 11 / 18 Tasks Completed (61.1%)
* **Next Focus:** Phase 4 — Mobile Driver Suite

---

## ✨ Features & Modules

### 🏢 Desktop Dispatch Portal (Phase 3 Complete)
* **Interactive Yard Board Grid:** Real-time visual tracking of vehicles in the yard, status filters, and one-click ground/un-ground controls.
* **Load Creation & Dispatch Panel:** Streamlined dispatcher entry for custom loads, driver/vehicle dropdown assignments, and real-time board updates.
* **Active Load Watch Board:** Live dispatch monitoring featuring progress timelines, status timestamps, and vehicle/driver associations.
* **Maintenance & Override Hub:** Central mechanic log to view grounded assets and review driver odometer notes.

### 🔐 Auth & Role-Based Access (Phase 2 Complete)
* Role-driven UI routing for Owners, Dispatchers, Mechanics, and Drivers.
* Dynamic hat-switcher for Fleet Owners to view real-time operations across roles.
* Native `bcrypt` password hashing for security.

---

## 🛠️ Tech Stack & Architecture

* **Frontend:** Streamlit
* **Database & ORM:** SQLite with SQLAlchemy (`AsyncSession` native engine)
* **Testing:** Pytest (`python -m pytest`)
* **Environment Management:** Python `venv` + `requirements.txt`

---

## 🚀 Quick Start

1. **Clone the Repository:**
   ```bash
   git clone [https://github.com/Twosixstudios/fleetscout-core.git](https://github.com/Twosixstudios/fleetscout-core.git)
   cd fleetscout-core
Set Up Virtual Environment & Dependencies:

Bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
Seed Database & Run Application:

Bash
python -m src.core.seed
streamlit run app.py
Run Test Suite:

Bash
python -m pytest