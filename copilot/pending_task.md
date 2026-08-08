# Task ID: TASK-6.1: Owner Portal, Dynamic Branding & Default Field Placeholders [x] - COMPLETE

## Objective
Establish the Owner role, auto-seed an Owner account (`owner@fleetscout.com`) with realistic carrier defaults, build the Owner Portal UI with input placeholders and demo fallback info, and implement dynamic white-label headers.

## Target Files
- `src/core/seed.py`
- `app.py`
- `src/ui/owner_portal.py` (New file)
- `Tasks.md`

## Step-by-Step Requirements
1. **Auto-Seed Owner & Demo Carrier:**
   - Update `seed_database()` to include an Owner account (`owner@fleetscout.com`, Role: `Owner`, Password: `password123`).
   - Ensure the baseline Carrier record has clean demo defaults: `name="Two-Six Logistics LLC"`, `dot_number="USDOT-3829104"`.

2. **Dynamic White-Label Header Component:**
   - Refactor headers in `app.py` so authenticated users see `� [Carrier Name] Terminal` (e.g. `� Two-Six Logistics LLC Terminal`) as the main title with `Powered by FleetScout | Two-Six Studios` in clean subtext.

3. **Owner Portal UI & Form Placeholders (`src/ui/owner_portal.py`):**
   - **Carrier Settings Form:**
     * Include text inputs for Carrier Name & DOT Number with greyed-out placeholders (e.g., `placeholder="e.g. Two-Six Logistics LLC"`, `placeholder="e.g. USDOT 3829104"`).
     * Pre-populate form values with current database records.
     * Upon saving, update `Carrier` in SQLite and immediately trigger a Streamlit rerun so headers update live.
   - **Team Roster:** Display all active Dispatchers and Drivers linked to the Carrier.

4. **App Integration:**
   - Add "Owner View" navigation in `app.py` accessible to users with the `Owner` role.

## Guardrails & Verification
- Ensure forms never render completely blank; always fall back to baseline demo defaults.
- Verify `venv/bin/python -m pytest` passes completely.
- Run `git add . && git commit -m "feat(phase6): add Owner portal with dynamic branding, input placeholders, and demo carrier defaults" && git push origin main` upon successful completion.