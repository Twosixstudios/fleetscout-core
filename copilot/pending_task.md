# Task ID: TASK-6.6: Live Fuel API Service & EIA Diesel Benchmark Engine

## Objective
Build a lightweight, resilient fuel price service (`src/core/fuel_service.py`) that auto-fetches weekly U.S. On-Highway Diesel Fuel Prices, caches the value to avoid unnecessary network calls, applies optional carrier fuel card discounts, and provides graceful fallbacks during network outages.

## Target Files
- `src/core/fuel_service.py`
- `src/core/models.py`
- `tests/test_end_to_end.py`
- `Tasks.md`

## Step-by-Step Requirements
1. **Fuel Price Fetching & Caching Engine (`src/core/fuel_service.py`):**
   - Implement `get_current_diesel_price(region: str = "national") -> dict`:
     * Auto-fetches current diesel benchmarks (e.g., U.S. EIA or open market benchmark feeds).
     * Implements local caching (24-hour TTL in SQLite or file cache) so Streamlit reruns do not spam external HTTP requests.
     * Returns structured metadata: `{"price_per_gal": float, "updated_at": str, "source": str, "is_fallback": bool}`.
   - Implement robust try/except error handling: if offline or API is down, fallback seamlessly to `$3.85/gal` with `is_fallback: True`.

2. **Effective Fuel Cost Calculator:**
   - Implement `get_effective_fuel_cost(carrier_discount: float = 0.0) -> float`:
     * Subtracts the carrier's fuel card discount (e.g. `$0.45/gal`) from the benchmark price.
     * Ensures calculated fuel price never drops below `$0.00`.

3. **Carrier Settings Schema Upgrade (`src/core/models.py`):**
   - Ensure Carrier settings model supports optional default fields: `default_mpg` (default `6.5`), `default_driver_cpm` (default `$0.60`), and `carrier_fuel_discount` (default `$0.00`).

4. **Automated Verification:**
   - Add unit tests for API parsing, fallback handling on network errors, 24-hour caching logic, and discount deductions.
   - Run `venv/bin/python -m pytest` to confirm all 76+ tests pass green.

## Guardrails & Verification
- Never allow network timeouts or API failure to crash the application.
- Run `git add . && git commit -m "feat(fuel): add live diesel fuel benchmark service with caching and fallback guards" && git push origin main`.