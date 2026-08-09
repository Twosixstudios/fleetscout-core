# Task ID: TASK-7.1: Ratecon AI Parser Integration, Master Dev Seeder, & HOS Integrity

## Objective
1. Inspect the dedicated parser project located at `../ratecon-ai-parser` (or `/Users/erikvilla/Projects/Two-Six-Studios/ratecon-ai-parser`) and port/integrate its AI parsing logic into `src/core/ratecon_parser.py` inside `fleetscout-core`.
2. Implement a persistent startup auto-seeder in `app.py` that guarantees a Master Dev Account (`admin@twosix.com` / `DevMaster2026!`) and primary Carrier exist upon every Streamlit Cloud reboot.
3. Remove interactive Duty Status toggles from Owner and Dispatcher views (converting HOS tracking to strictly READ-ONLY availability clocks) to enforce FMCSA driver log compliance.

## Target Files
- `../ratecon-ai-parser` (external source directory)
- `src/core/ratecon_parser.py`
- `app.py`
- `src/core/database.py`
- `src/ui/owner_portal.py`
- `src/ui/dispatch_view.py`
- `tests/test_end_to_end.py`
- `Tasks.md`

## Step-by-Step Requirements
1. **Ratecon AI Parser Porting (`src/core/ratecon_parser.py`):**
   - Read and inspect all files inside `../ratecon-ai-parser` to extract its parsing schemas, regex patterns, or PDF extraction functions.
   - Port and integrate that extraction engine directly into `src/core/ratecon_parser.py` in `fleetscout-core`.
   - Ensure ratecon PDF uploads extract broker/shipper name, rate/total pay, pickup/delivery locations, pickup/delivery dates, weight, commodity, and load reference numbers with maximum accuracy.

2. **Master Dev Account Startup Seeder (`app.py` & `src/core/database.py`):**
   - Ensure `init_db()` auto-runs on Streamlit startup.
   - Auto-seed a default Carrier (`Two-Six Logistics LLC`) if no carriers exist.
   - Auto-seed the Master Dev Account:
     * **Email:** `admin@twosix.com`
     * **Password:** `DevMaster2026!`
     * **Role:** `Owner` (Super-Admin privileges for live sales demos).
   - Auto-seed standard demo accounts (`owner@fleetscout.com`, `dispatcher@fleetscout.com`, `driver@fleetscout.com`) so test suites remain green.

3. **FMCSA Driver HOS Integrity Guardrail:**
   - Audit `src/ui/owner_portal.py` and `src/ui/dispatch_view.py`.
   - **REMOVE** interactive duty status toggles (`Driving`, `On Duty`, `Off Duty`, `Sleeper`) from non-driver views.
   - Display driver hours strictly as **Read-Only Status Badges & Availability Clocks** (11h driving, 14h shift, 10h sleeper rest indicator).

4. **Automated Verification:**
   - Add unit tests verifying `admin@twosix.com` auto-seeding on fresh startup.
   - Add pytest coverage validating the ported `ratecon-ai-parser` logic.
   - Run `venv/bin/python -m pytest` to confirm all test suites pass green.

## Guardrails & Verification
- Never crash if `admin@twosix.com` or default carriers already exist in SQLite.
- Run `git add . && git commit -m "feat(parser): integrate ratecon-ai-parser engine, seed master dev account, enforce read-only HOS" && git push origin main`.