# Task ID: HD-5.2: Hard Lockout Safety Constraint

## Objective
Implement a database-level safety interceptor that prevents the assignment of a `Load` to a `Vehicle` if the vehicle's status is set to `Grounded`.

## Target Files
- `src/core/services.py` (or `src/api/dispatch.py` if service layer is absent)
- `src/core/exceptions.py` (define `SafetyViolationError`)
- `tests/test_safety.py`

## Step-by-Step Requirements
1. **Define Exception:** Create a custom `SafetyViolationError` in `src/core/exceptions.py` to handle blocked assignments.
2. **Implement Interceptor:** Create a validation function `validate_vehicle_readiness(vehicle_id: int)` that checks the `Vehicle.status` field.
3. **Integrate into Dispatch:** Update the load assignment logic (likely in the dispatch service) to call `validate_vehicle_readiness` before committing the `AsyncSession`.
4. **Unit Testing:** Create `tests/test_safety.py` to verify that:
   - Assigning a load to an `Active` vehicle succeeds.
   - Assigning a load to a `Grounded` vehicle raises `SafetyViolationError`.
   - The database transaction rolls back on failure.

## Guardrails & Verification
- Use `AsyncSession` for all database checks.
- Ensure the error message is descriptive enough for the UI to display a "Vehicle Grounded" alert.
- Run `python -m pytest tests/test_safety.py` to confirm the lockout logic.