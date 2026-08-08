# Task ID: FIX-5.4: Streamlit Repair Form GPS Fix & Active Load Seeding

## Objective
Fix the Streamlit `MarshallComponentException` crash in the repair report form and seed an active test load assigned to the default driver so One-Tap Status Toggles render properly.

## Target Files
- `src/ui/gps_component.py`
- `src/ui/repair_form.py`
- `src/ui/status_toggles.py`
- `reset_users.py`

## Step-by-Step Requirements
1. **Fix GPS Component Marshalling:**
   In `src/ui/gps_component.py`, fix the call to `_gps_location`. Remove the positional `{}` dict parameter and pass only keyword arguments (e.g., `_gps_location(key="fleetscout_gps")`) or provide safe fallback handling if geolocation component fails.
2. **Seed Active Driver Load:**
   Update database seeding (`reset_users.py` / database seed functions) so that the primary driver user (e.g., `driver@fleetscout.com`) has an active load in `DISPATCHED` or `IN_TRANSIT` status assigned in `test.db`.
3. **Verify Status Toggle Rendering:**
   Ensure `src/ui/status_toggles.py` correctly fetches the active load for the logged-in session user and displays the touch-friendly stage buttons.
4. **Automated Verification:**
   Run existing UI/route tests (`python -m pytest tests/`) to verify no regressions.

## Guardrails & Verification
- Ensure `gps_location` catches component initialization errors gracefully without crashing the UI.
- Verify `python -m pytest` passes all tests.
- Run `git add . && git commit -m "fix(ui): resolve GPS component exception and seed active load for status toggles" && git push origin main` upon successful verification.