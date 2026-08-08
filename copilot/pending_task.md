# Task ID: TASK-6.4: Mock GPS Telemetry & Interactive Demo Mapping

## Objective
Enhance `src/ui/gps_component.py` and the fleet map components so that whenever live browser GPS is unavailable or blocked (such as on Streamlit Cloud), the system automatically injects realistic mock GPS telemetry along major freight corridors (e.g. Southern California I-10 / Ports of LA / Inland Empire) to render a live interactive map for customer demos.

## Target Files
- `src/ui/gps_component.py`
- `src/ui/owner_portal.py`
- `src/ui/dispatch_view.py`
- `tests/test_end_to_end.py`
- `Tasks.md`

## Step-by-Step Requirements
1. **Mock Telemetry Engine (`src/ui/gps_component.py`):**
   - If browser geolocation returns `None` or raises an exception, generate realistic fallback coordinates centered around key carrier hubs (e.g., Los Angeles / Inland Empire freight corridor: `34.0522, -118.2437`).
   - Include mock vehicle markers with simulated speed, heading, and status (e.g. `TRK001 - In Transit`, `TRK002 - Docked`).

2. **Interactive Map Display:**
   - Render the telemetry map using Streamlit's native `st.map()` or PyDeck map layer in both the **Fleet Command Center** and **Driver Console**.
   - Ensure the UI clearly indicates: `📍 GPS: Live Demo Telemetry (I-10 / LA Corridor)`.

3. **Automated Verification:**
   - Add pytest coverage verifying fallback telemetry generation when GPS returns `None`.
   - Run `venv/bin/python -m pytest` to ensure all 75+ tests pass cleanly.

## Guardrails & Verification
- Do not remove existing defensive try/except guards; simply return mock coordinates instead of a blank "unavailable" state.
- Run `git add . && git commit -m "feat(gps): add realistic mock telemetry engine and interactive demo map" && git push origin main`.