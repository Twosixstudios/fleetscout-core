# Task ID: FIX-5.8: Resolve DetachedInstanceError in Status Toggle Logs

## Objective
Fix `sqlalchemy.orm.exc.DetachedInstanceError` when accessing `load.status_logs` in `src/ui/status_toggles.py` by eager-loading `Load.status_logs` during active load briefing queries in `src/core/services.py`.

## Target Files
- `src/core/services.py`
- `src/ui/status_toggles.py`
- `tests/test_end_to_end.py`

## Step-by-Step Requirements
1. **Eager Load Relationship in Service Layer:**
   - In `src/core/services.py` (specifically functions querying active driver loads like `get_driver_load_briefing`), add `selectinload(Load.status_logs)` to the SQLAlchemy `select` statement options.
   - Import `selectinload` from `sqlalchemy.orm`.
2. **Safe Fallback in Status Toggles UI:**
   - Ensure `src/ui/status_toggles.py` safely checks `getattr(load, 'status_logs', [])` or extracts the latest timestamp without triggering un-sessioned ORM lazy loads.
3. **Automated Verification:**
   - Run `venv/bin/python -m pytest` to confirm all 58+ tests pass and no detached ORM instance exceptions occur.

## Guardrails & Verification
- Do not modify database models or schema definitions.
- Ensure all async database operations continue to execute cleanly inside `AsyncSession`.
- Run `git add . && git commit -m "fix(ui): eager load status_logs to resolve DetachedInstanceError in status toggles" && git push origin main` upon successful verification.