# 🚛 Fleet Scout Terminal

A lightweight fleet management and dispatch terminal built with Python, FastAPI, Streamlit, and SQLAlchemy. Designed by Two Six Studios.

---

## 💡 What It Does

Fleet Scout bridges the gap between office dispatchers and drivers in the cab:

* Role-Based Interfaces: Automatically routes drivers to a clean, low-distraction mobile console and dispatchers to a full-featured desktop dashboard.
* Owner Hat-Switcher: Allows fleet owners to switch between Dispatcher and Driver views on the fly directly from the sidebar without logging out.
* Strict Odometer Validation: Prevents bad data entry by ensuring new mileage entries cannot be lower than the previous recorded reading.
* Database-Backed Auth: Uses FastAPI and SQLite with hashed passwords (bcrypt) to manage user permissions (Owner, Dispatcher, Driver).

---

## 🛠️ Tech Stack

* Frontend: Streamlit
* Backend API: FastAPI + Uvicorn
* Database & ORM: SQLite + SQLAlchemy
* Auth: OAuth2 Password Flow + Passlib/Bcrypt

---

## 🚀 How to Run It

1. Set Up Environment:
   git clone https://github.com/Twosixstudios/fleetscout-core.git
   cd fleetscout-core
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

2. Seed Test Accounts:
   python reset_users.py

3. Launch App:
   Terminal 1 (Backend): uvicorn main:app --reload
   Terminal 2 (Frontend): streamlit run app.py

---

## 🔑 Test Credentials

* Owner: owner@twosix.com | password123 | Full admin access + Live Hat-Switcher
* Dispatcher: dispatcher@twosix.com | password123 | Desktop dispatch dashboard & fleet logs
* Driver: driver@twosix.com | password123 | Streamlined mobile driver view

---

## 📌 Roadmap

- [x] Phase 1: Core DB models, VIN validation, and odometer integrity check.
- [x] Phase 2: User auth, dynamic role routing, and Owner Hat-Switcher.
- [ ] Phase 3: Active load dispatching and truck/driver assignments.
- [ ] Phase 4: Driver trip proof uploading and maintenance alerts.
