# Task ID: HD-5.1: FreightSlip & LaneSight Modular Plugin Hooks

## Objective
Implement a modular plugin architecture in FleetScout core to dynamically load and execute `freightslip` (RateCon parser) and `lanesight` (OSRM/HOS calculator) adapters.

## Target Files
- `src/plugins/base.py` (Base plugin interface)
- `src/plugins/freightslip_adapter.py` (RateCon parser adapter)
- `src/plugins/lanesight_adapter.py` (OSRM/HOS calculator adapter)
- `src/api/plugins.py` (Plugin registry)
- `src/core/services.py` (Service integration points)
- `tests/test_plugins.py` (Unit & integration test suite)
- `Tasks.md`

## Step-by-Step Requirements
1. **Define Abstract Plugin Base:** Create `PluginInterface` in `src/plugins/base.py` requiring `execute(data: dict) -> dict` and `validate() -> bool` methods.
2. **Implement Adapters:**
   - Create `FreightSlipAdapter` in `src/plugins/freightslip_adapter.py` to parse raw PDF/text input into structured load parameters (commodity, weight, pickup/delivery refs).
   - Create `LaneSightAdapter` in `src/plugins/lanesight_adapter.py` to calculate route distance, estimated transit time, and HOS duty impact from waypoints.
3. **Build Plugin Registry:** Implement a dynamic registry in `src/api/plugins.py` allowing plugins to be registered, retrieved, and safely executed by carrier configuration.
4. **Service Integration:** Wire plugin hooks into `src/core/services.py`. Ensure all plugin executions are isolated in `try/except` wrappers so plugin failure never crashes core dispatch or rolls back database transactions.
5. **Mark Task Completed:** Update `Tasks.md` to flip Task 5.1 from `[ ]` to `[x]`.

## Guardrails & Verification
- Plugin execution errors must be caught and logged gracefully without raising `SafetyViolationError` or rolling back DB transactions.
- Write unit tests in `tests/test_plugins.py` covering adapter execution, registry lookup, and error isolation.
- Run `python -m pytest` to verify 100% test suite pass rate.
- Run `git add . && git commit -m "feat(phase5): complete Task HD-5.1 - FreightSlip & LaneSight Modular Plugin Hooks" && git push origin main` upon successful verification.