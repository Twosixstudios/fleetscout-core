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
	Owner role account, dynamic white-label carrier branding, Executive Owner Dashboard (Fleet Command Center, Driver Console, Team & Access, Carrier Settings), team roster with full deletion/access controls, onboarding invite/redemption, and password overrides.
	
	**Overall Progress:** 6 / 6 Tasks Completed (100%)


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

	**Overall Progress:** 6 / 6 Tasks Completed (100%)

- [x] **Task 6.1: Owner Portal, Dynamic Branding & Default Field Placeholders (`TASK-6.1`)** `#priority/high`
	- **Description:** Establish the Owner role, auto-seed `owner@fleetscout.com` with realistic carrier defaults, build the Owner Portal UI (Carrier Settings form with greyed-out placeholders, pre-populated values, save -> live header rerun, Team Roster), and implement dynamic white-label headers.
	- **Prerequisites:** Task 5.9
	- **Verification:** `venv/bin/python -m pytest` (60 passed)
- [x] **Task 6.2: Startup Self-Healing Database Auto-Seeding (`FIX-6.2`)** `#priority/high`
	- **Description:** Add an automatic startup check in `app.py` (`init_db()`) that counts `User` rows via an async query and, when the database is empty or unseeded (e.g. fresh Streamlit Cloud boot), auto-executes an idempotent `seed_database()` to populate the baseline Owner (`owner@fleetscout.com`), Dispatcher, Drivers, Carrier, Vehicles, and Active Loads — without wiping existing data or raising unique/primary key errors on reruns.
	- **Prerequisites:** Task 6.1
	- **Verification:** `venv/bin/python -m pytest` (61 passed)
- [x] **Task 6.3: Owner Team Provisioning Engine (`TASK-6.2`)** `#priority/high`
	- **Description:** Add `create_team_member()` to `services.py` (role validation for `Dispatcher`/`Driver`, bcrypt hashing via `get_password_hash()`, duplicate email/username guard) and a "➕ Provision New Team Member" form in the Owner Portal (`owner_portal.py`) that provisions new accounts bound to the active Owner's `carrier_id`, surfaces success/errors, and live-reruns to refresh the Team Roster.
	- **Prerequisites:** Task 6.2
	- **Verification:** `venv/bin/python -m pytest` (64 passed)
- [x] **Task 6.4: Admin Controls, Dispatcher Recovery & Email Onboarding Invitations (`TASK-6.3`)** `#priority/high`
	- **Description:** Build comprehensive account administration for Owners (Edit User, Password Overrides, Deactivate/Reactivate), password recovery tools for Dispatchers, a `UserInvite` token schema with `create_onboarding_invite()` / `accept_onboarding_invite()` services, a "Send Onboarding Invite" form with Pending Invitations list in the Owner Portal, and a public `?invite_token=` redemption screen on the login page.
	- **Prerequisites:** Task 6.3
	- **Verification:** `venv/bin/python -m pytest` (71 passed)
- [x] **Task 6.5: Executive Owner Dashboard & Complete Account Controls (`TASK-6.4`)** `#priority/high`
	- **Description:** Replace the sidebar hat-switcher with a tabbed Executive Owner Dashboard (📊 Fleet Command Center, 🚛 Driver Console View, 👥 Team & Access Management, ⚙️ Carrier Settings), add `delete_or_deactivate_user()` (strict carrier scoping, Owner + self-deletion guardrails, historical trip/report/duty logs preserved with detached references), add a Team Roster Action Column with 🗑️ Delete/Remove, 🔑 Reset Password, and ✏️ Edit Details controls, and keep email onboarding invites/redemption.
	- **Prerequisites:** Task 6.4
	- **Verification:** `venv/bin/python -m pytest` (75 passed)
- [x] **Task 6.6: Mock GPS Telemetry & Interactive Demo Mapping (`TASK-6.4`)** `#priority/high`
	- **Description:** Enhance the mock engine and fleet maps so that whenever live browser GPS is unavailable or blocked (e.g. Streamlit Cloud), the system auto-injects realistic mock GPS telemetry along the SoCal I-10 / LA freight corridor (hub `34.0522, -118.2437` — TRK-001 In Transit, TRK-002 Docked, etc. with simulated speed/heading/status) and renders a live interactive `st.map` overlay in the Fleet Command Center, Driver Console, and Dispatch views with the 📍 Live Demo Telemetry (I-10 / LA Corridor) indicator.
	- **Prerequisites:** Task 6.5
	- **Verification:** `venv/bin/python -m pytest` (76 passed)




%% kanban:settings
```
{"kanban-plugin":"list","show-checkboxes":true}
```
%%