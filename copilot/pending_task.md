# Task ID: TASK-6.7: Owner Ratecon Profitability Calculator & Quick Load Analyzer

## Objective
Build a "📈 Load Profitability & ROI Analyzer" tool inside the Owner Portal (`src/ui/owner_portal.py`) that combines parsed FreightSlip Ratecon data with the live EIA fuel service and carrier cost baselines to instantly display net margin, RPM, CPM, and a profit decision badge.

## Target Files
- `src/ui/owner_portal.py`
- `src/core/services.py`
- `tests/test_end_to_end.py`
- `Tasks.md`

## Step-by-Step Requirements
1. **Profitability Calculation Engine (`src/core/services.py`):**
   - Implement `calculate_load_profitability(gross_payout: float, total_miles: float, mpg: float, fuel_price: float, driver_cpm: float, fixed_cpm_reserve: float = 0.15) -> dict`:
     * `fuel_cost` = `(total_miles / mpg) * fuel_price`
     * `driver_cost` = `total_miles * driver_cpm`
     * `overhead_reserve` = `total_miles * fixed_cpm_reserve`
     * `total_cost` = `fuel_cost + driver_cost + overhead_reserve`
     * `net_profit` = `gross_payout - total_cost`
     * `rpm` (Rate Per Mile) = `gross_payout / total_miles`
     * `cpm` (Cost Per Mile) = `total_cost / total_miles`
     * `profit_margin_pct` = `(net_profit / gross_payout) * 100`
     * Status indicator: `🟢 Highly Profitable` (Margin $\ge$ 20%), `🟡 Marginal` (Margin 5%–19%), or `🔴 Unprofitable` ($<$ 5%).

2. **Quick Load Analyzer UI (`src/ui/owner_portal.py`):**
   - Add a **"📈 Quick Load Analyzer"** tab or expander in the Owner Portal.
   - Include a Ratecon PDF uploader (FreightSlip integration) or manual input for:
     * **Gross Rate / Payout ($)**
     * **Total Trip Distance (Miles)**
   - Pre-populate live fuel cost from `fuel_service.py` and carrier defaults (`default_mpg`, `default_driver_cpm`).
   - Render a high-visibility **Financial Metrics Card**:
     * Gross Payout vs. Total Costs breakdown (Fuel, Driver, Overhead).
     * Net Profit ($), RPM ($/mi), and CPM ($/mi).
     * Color-coded **Profitability Decision Badge**.

3. **Automated Verification:**
   - Add end-to-end tests for accurate math calculations, status badge thresholds, and UI rendering.
   - Run `venv/bin/python -m pytest` to verify all 86+ tests pass green.

## Guardrails & Verification
- Prevent division-by-zero errors when total miles or MPG are zero.
- Run `git add . && git commit -m "feat(owner): add quick load analyzer and ratecon profitability calculator" && git push origin main`.