# Task ID: FIX-6.2: Startup Self-Healing Database Auto-Seeding

> **STATUS: ✅ COMPLETED** — Sat Aug  8 01:40 PDT 2026 · `venv/bin/python -m pytest` = 61 passed. See `copilot/build_result.md`.

## Objective
Add an automatic startup check in `app.py` so that whenever the application launches against an unseeded or empty database (such as on Streamlit Cloud), it automatically executes `seed_database()` to populate baseline accounts (`owner@fleetscout.com`, `dispatcher@fleetscout.com`, `driver@fleetscout.com`).

## Target Files
- `app.py`
- `src/core/database.py`
- `src/core/seed.py`
- `Tasks.md`

## Step-by-Step Requirements
1. **Startup Check in `app.py`:**
   - During Streamlit app startup (e.g. inside `init_db()` or an `@st.cache_resource` startup hook), execute an async query to count records in the `User` table.
   - If `count == 0`, immediately invoke `seed_database()` to seed the Owner (`owner@fleetscout.com`), Dispatcher, Drivers, Carrier, Vehicles, and Active Loads.

2. **Idempotent Guard:**
   - Ensure `seed_database()` handles existing records cleanly without raising primary key or unique constraint exceptions on subsequent reruns.

3. **Automated Verification:**
   - Add/update an end-to-end test in `tests/test_end_to_end.py` verifying that initializing against a fresh empty database triggers auto-seeding.
   - Run `venv/bin/python -m pytest` to confirm all 60+ tests pass cleanly.

## Guardrails & Verification
- Keep all database checks asynchronous using `AsyncSession`.
- Run `git add . && git commit -m "fix(auth): add self-healing startup database auto-seeding for cloud deployments" && git push origin main` upon successful completion.