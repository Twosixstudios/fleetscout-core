# Task ID: FIX-5.9: Suppress Custom Component Warning Banners & Clean GPS Fallback

## Objective
Clean up the custom GPS component rendering in `src/ui/gps_component.py` so that Streamlit Cloud does not render yellow component load warning banners when custom HTML/JS iframe assets are restricted.

## Target Files
- `src/ui/gps_component.py`
- `tests/test_end_to_end.py`
- `Tasks.md`

## Step-by-Step Requirements
1. **Suppress Component Load Exceptions:**
   - In `src/ui/gps_component.py`, wrap the call to `_gps_location()` in a defensive try/except block that catches all component load and rendering exceptions.
   - If the custom iframe component fails or raises a Streamlit component error, gracefully suppress the yellow Streamlit warning banner and fall back to returning `None` (which correctly displays `� GPS: Location unavailable`).

2. **Verify Component Paths & Static Assets:**
   - Ensure `gps_component` path declarations safely fall back to the inline HTML/JS implementation if the static `frontend/build` path is not present in cloud environments.

3. **Automated Verification:**
   - Run `venv/bin/python -m pytest` to confirm all 59+ tests pass without breaking GPS status checks or driver forms.

## Guardrails & Verification
- Do not alter the core functionality of the repair reporting or HOS reset planner tools.
- Ensure `venv/bin/python -m pytest` passes completely.
- Run `git add . && git commit -m "fix(ui): suppress custom GPS component load warnings and ensure clean fallback UI" && git push origin main` upon successful verification.