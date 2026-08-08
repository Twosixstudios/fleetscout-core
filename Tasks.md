---

kanban-plugin: list

---

## 🚚 FleetScout - Architecture & Rules

- [ ] **Agent Instructions & Guidelines**
	- Always check `CLAUDE.md`, `copilot/pending_task.md`, and `copilot/build_result.md` before starting work on a task.
	- Only work on tasks marked as `[ ]` under the Active Phase.
	- Once a task is completed and verified, update its status to `[x]` and commit `Tasks.md` alongside code changes.


## 🎯 Current Status

- [x] **Active Phase: Phase 6 - Owner Portal, Branding & Demo Defaults**
	
	**Target Deliverable:**
	Owner role account, dynamic white-label carrier branding, Owner Portal UI with form placeholders and demo fallbacks, and team roster.
	
	**Overall Progress:** 1 / 1 Tasks Completed (100%)


## 🔒 Phase 1: Future-Proof Schema & Database Foundation

- [x] **Task 1.1: Vehicle Table Updates (`F-1.1`)** `#priority/high`
	- **Description:** Add `unit_number`, `status` (`Active`/`Grounded`), and `carrier_id` to Vehicle schema.
	- **Prerequisites:** None
- [x] **Task 1.2: Active Load Table Setup (`F-1.2`)** `#priority/high`
	- **Description:** Create `Load` table tracking `load_id`, `load_number`, `load_weight`, `commodity`, `pickup_ref`, `delivery_ref`, `dispatcher_notes`, `status`, and `carrier_id`.
	- **Prerequisites:** Task 1.1
- [x] **Task 1.3: Role-Based User Table (`F-1.3`)** `#priority/high`
	- **Description:** Extend `User` schema with roles (`Owner`, `Dispatcher`, `Driver`) and `carrier_id` for multi-tenant capability.
	- **Prerequisites:** Task 1.2
- [x] **Task 1.4: Unified Async DB Seeds (`F-1.4`)** `#priority/high`
	- **Description:** Build initialization script (`seed.py`) inserting default carrier, vehicles with unit numbers, active loads, and sample users.
	- **Prerequisites:** Task 1.3


## ⚡ Phase 2: Access & Auth Routing Engine

- [x] **Task 2.1: Unified Login Screen (`AR-2.1`)** `#priority/high`
	- **Description:** Single entry Streamlit login screen verifying credentials and identifying roles (`Owner`, `Dispatcher`, `Driver`).
	- **Prerequisites:** Task 1.4
- [x] **Task 2.2: Interface Hat-Switcher (`AR-2.2`)** `#priority/high`
	- **Description:** Configure routing engine: Redirect `Driver` to mobile view; redirect `Owner`/`Dispatcher` to desktop portal.
	- **Prerequisites:** Task 2.1
- [x] **Task 2.3: Owner Role Toggle (`AR-2.3`)** `#priority/high`
	- **Description:** Quick 'Role Toggle' in sidebar for Owners to switch seamlessly between Dispatch view and Driver view.
	- **Prerequisites:** Task 2.2


## 🖥️ Phase 3: Desktop Dispatch Portal

- [x] **Task 3.1: Interactive Yard Board Grid (`DP-3.1`)** `#priority/high`
	- **Description:** Assemble live grid showing fleet vehicles, active drivers, active load numbers, and physical statuses (`Active` vs `Grounded`).
	- **Prerequisites:** Task 2.3
- [x] **Task 3.2: Load Creation & Dispatch Panel (`DP-3.2`)** `#priority/high`
	- **Description:** Build dispatcher load creation form (Load #, Weight, Commodity, Pickup/Delivery Refs, Dispatcher Notes) connected to Driver Assignment dropdown.
	- **Prerequisites:** Task 3.1
- [x] **Task 3.3: Active Load Watch Board (`DP-3.3`)** `#priority/medium`
	- **Description:** Real-time tracking display showing progress timelines, timestamps, and active status updates for all dispatched drivers.
	- **Prerequisites:** Task 3.2
- [x] **Task 3.4: Maintenance & Override Hub (`DP-3.4`)** `#priority/medium`
	- **Description:** Central mechanic log panel to display reported driver issues. Allow Owners/Mechanics to un-ground vehicles after repairs.
	- **Prerequisites:** Task 3.3


## 📱 Phase 4: Mobile Driver Suite

- [x] **Task 4.1: Quick-Ref Load Briefing (`DS-4.1`)** `#priority/high`
	- **Description:** Lightweight mobile-responsive view showing active load details: Load #, Pickup/Delivery Refs, Commodity, Weight, and Dispatcher Notes.
	- **Prerequisites:** Task 3.4
- [x] **Task 4.2: One-Tap Status Toggles (`DS-4.2`)** `#priority/high`
	- **Description:** Touch-friendly buttons for driver states (`At Shipper`, `Loaded`, `En Route`, `Delivered`). On tap, log GPS & timestamp.
	- **Prerequisites:** Task 4.1
- [x] **Task 4.3: Structured Repair Form (`DS-4.3`)** `#priority/medium`
	- **Description:** 3-field mobile issue report: Category (`Brakes`, `Tires`, `Lights`, `Engine Light`, `Trailer`), Description, and Photo Upload API.
	- **Prerequisites:** Task 4.2
- [x] **Task 4.4: Reset Planner & HOS Duty Clock (`DS-4.4`)** `#priority/low`
	- **Description:** Sleeper Rest Timer and duty state selector allowing drivers to log off-duty starts with 10-hour availability return countdown.
	- **Prerequisites:** Task 4.3


## 📡 Phase 5: Modular Plugins, Hardening & Deploy

	**Overall Progress:** 7 / 7 Tasks Completed (100%)

- [x] **Task 5.1: FreightSlip & LaneSight Modular Plugin Hooks (`HD-5.1`)** `#priority/high`
	- **Description:** Import and execute `freightslip` (RateCon PDF parser function) and `lanesight` (OSRM route & HOS calculation functions) as modular plugin packages inside FleetScout core.
	- **Prerequisites:** Task 4.4
	- **Verification:** `python -m pytest` (58 passed)
- [x] **Task 5.2: Hard Lockout Safety Constraint (`HD-5.2`)** `#priority/high`
	- **Description:** DB Interceptor: If a truck is flagged as `Grounded`, raise safety exception and physically block dispatcher load assignment.
	- **Prerequisites:** Task 5.1
- [x] **Task 5.3: End-to-End Walkthroughs & Mobile Viewport Polish (`HD-5.3`)** `#priority/medium`
	- **Description:** Validate full end-to-end loop (Driver grounds truck -> Dispatcher blocked -> Mechanic ungrounds -> Dispatcher assigns) and apply Streamlit mobile CSS rules.
	- **Prerequisites:** Task 5.2
	- **Verification:** `tests/test_end_to_end.py`, `tests/test_dispatch_api_safety.py`, `python -m scripts.verify_hd_5_3`
- [x] **Task 5.4: Repair Form GPS Fix & Active Load Seeding (`FIX-5.4`)** `#priority/medium`
	- **Description:** Fix `MarshallComponentException` crash in the repair-form GPS component (remove positional args + graceful fallback) and seed an active `dispatched` load for the primary driver so One-Tap Status Toggles render.
	- **Prerequisites:** Task 5.3
	- **Verification:** `python -m pytest`
- [x] **Task 5.7: Unified Database Seeding & User Account Alignment (`FIX-5.7`)** `#priority/high`
	- **Description:** Unify `src/core/seed.py` and `reset_users.py` so `test.db` is reliably seeded with `dispatcher@fleetscout.com` (Dispatcher), `driver@fleetscout.com` (Driver, Active Load), and `driver@twosix.com` (Driver, Active Load), all with bcrypt hashes of `password123`.
	- **Prerequisites:** Task 5.4
	- **Verification:** `venv/bin/python -m pytest` (58 passed)
- [x] **Task 5.8: Resolve DetachedInstanceError in Status Toggle Logs (`FIX-5.8`)** `#priority/high`
	- **Description:** Eager-load `Load.status_logs` in driver briefing queries (`selectinload`) and add a safe `getattr` fallback in `status_toggles.py` so `status_logs` never trigger lazy loads on detached instances.
	- **Prerequisites:** Task 5.7
	- **Verification:** `venv/bin/python -m pytest` (59 passed)
- [x] **Task 5.9: Suppress Custom Component Warning Banners & Clean GPS Fallback (`FIX-5.9`)** `#priority/high`
	- **Description:** Guard `gps_component` path declarations so the inline HTML/JS fallback is used when static frontend assets are unavailable on Streamlit Cloud, and suppress the yellow component load warning banner by returning `None` on any component exception.
	- **Prerequisites:** Task 5.8
	- **Verification:** `venv/bin/python -m pytest` (60 passed)


## 🏠 Phase 6: Owner Portal, Branding & Demo Defaults

	**Overall Progress:** 1 / 1 Tasks Completed (100%)

- [x] **Task 6.1: Owner Portal, Dynamic Branding & Default Field Placeholders (`TASK-6.1`)** `#priority/high`
	- **Description:** Establish the Owner role, auto-seed `owner@fleetscout.com` with realistic carrier defaults, build the Owner Portal UI (Carrier Settings form with greyed-out placeholders, pre-populated values, save -> live header rerun, Team Roster), and implement dynamic white-label headers.
	- **Prerequisites:** Task 5.9
	- **Verification:** `venv/bin/python -m pytest` (60 passed)




%% kanban:settings
```
{"kanban-plugin":"list","show-checkboxes":true}
```
%%