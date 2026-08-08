"""Live diesel fuel benchmark service with caching and fallback guards (TASK-6.6).

Fetches the latest U.S. On-Highway Diesel price from the EIA's public weekly
gasoline & diesel CSV feed, caches the result on the local filesystem for a
24-hour TTL so Streamlit reruns never spam the external HTTP endpoint, applies
an optional carrier fuel-card discount via ``get_effective_fuel_cost()``, and
degrades gracefully to a hardcoded demo floor (``$3.85/gal``, ``is_fallback
True``) whenever the network or the upstream feed is unavailable.

The service is deliberately dependency-free: only stdlib (urllib, csv, json,
tempfile) is used so it runs on Streamlit Cloud and in plain CI workers.
"""

import csv
import io
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone

logger = logging.getLogger("fleetscout.fuel")

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------
FALLBACK_PRICE_PER_GAL = 3.85
CACHE_TTL_HOURS = 24
CACHE_TTL_SECONDS = CACHE_TTL_HOURS * 3600
DEFAULT_CACHE_DIR_ENV = "FLEETSCOUT_FUEL_CACHE_DIR"

EIA_WEEKLY_GAS_DIESEL_URL = (
    "https://www.eia.gov/petroleum/gasdiesel/gasdiesel.csv"
)

SOURCE_EIA = "U.S. EIA On-Highway Diesel (Weekly)"
SOURCE_CACHE = "Local 24h Cache (EIA)"
SOURCE_STALE = "Stale Local Cache (EIA)"
SOURCE_FALLBACK = "Fallback Benchmark (Numericals offline)"


def _now_ts() -> float:
    """Wall-clock epoch used for cache freshness decisions (monkeypatchable)."""
    return time.time()


def _cache_dir() -> str:
    return os.environ.get(DEFAULT_CACHE_DIR_ENV) or os.path.join(
        tempfile.gettempdir(), "fleetscout"
    )


def _cache_path(region: str) -> str:
    safe_region = (region or "national").strip().lower() or "national"
    return os.path.join(_cache_dir(), f"fuel_price_{safe_region}.json")


def _read_cache(region: str) -> dict:
    try:
        with open(_cache_path(region), "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        return payload if isinstance(payload, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def _write_cache(region: str, payload: dict) -> None:
    try:
        os.makedirs(_cache_dir(), exist_ok=True)
        with open(_cache_path(region), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
    except OSError:
        logger.warning("Could not persist fuel price cache for region '%s'.", region)


def clear_cache(region: str = "national") -> None:
    """Delete the on-disk cache entry so the next call fetches fresh."""
    try:
        os.remove(_cache_path(region))
    except OSError:
        pass


def _is_fresh(cached: dict, now: float) -> bool:
    if not cached:
        return False
    fetched_at = cached.get("cache_ts")
    return bool(fetched_at) and (now - float(fetched_at)) < CACHE_TTL_SECONDS


def _to_public(cached: dict) -> dict:
    return {
        "price_per_gal": round(float(cached["price_per_gal"]), 3),
        "updated_at": cached["updated_at"],
        "source": cached["source"],
        "is_fallback": bool(cached.get("is_fallback", False)),
    }


# ---------------------------------------------------------------------------
#  EIA CSV parsing
# ---------------------------------------------------------------------------
def parse_diesel_price_csv(text: str) -> float:
    """Extract the latest weekly on-highway diesel price from EIA's CSV feed.

    The historic ``gasdiesel.csv`` layout places Period in column 0 and the
    U.S. On-Highway Diesel average in column 4 (Period, Regular, Midgrade,
    Premium, Diesel). Parsing is tolerant: header rows (no date token) are
    skipped, the newest data row wins, and if column 4 is missing/empty the
    last numeric cell of the newest row is used. Raises ValueError when no
    usable price is found so callers can fall back.
    """
    rows = list(csv.reader(io.StringIO(text)))
    for row in reversed(rows):
        cells = [c.strip() for c in row]
        if not cells or not any(ch.isdigit() for ch in cells[0]):
            continue  # header / empty row

        prices = []
        for cell in cells[1:]:
            try:
                prices.append(float(cell.replace(",", "")))
            except ValueError:
                prices.append(None)

        if not prices or all(p is None for p in prices):
            continue

        if len(prices) >= 4 and prices[3] is not None:
            value = prices[3]  # traditional on-highway diesel column
        else:
            value = next((p for p in reversed(prices) if p is not None), None)

        if value is not None and value > 0:
            return round(value, 3)

    raise ValueError("No usable on-highway diesel price found in EIA CSV feed.")


def _http_get(url: str, timeout: float = 10.0) -> str:
    """Fetch a URL body as text via stdlib urllib (no third-party deps)."""
    import urllib.request

    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _fetch_benchmark(region: str = "national") -> float:
    """Fetch the current benchmark price, raising on any failure.

    Network timeouts, DNS failures, and parse errors all propagate to the
    caller (``get_current_diesel_price``) so they are never fatal.
    """
    payload = _http_get(EIA_WEEKLY_GAS_DIESEL_URL)
    price = parse_diesel_price_csv(payload)
    if price is None or price <= 0:
        raise ValueError(f"Unusable diesel price parsed from EIA feed: {price!r}")
    return price


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------
def get_current_diesel_price(region: str = "national") -> dict:
    """Return ``{price_per_gal, updated_at, source, is_fallback}`` for diesel.

    1. Serve a fresh (< 24 h) local cache immediately — no network call.
    2. Otherwise fetch the live EIA benchmark and refresh the cache.
    3. On any failure, serve a stale cache if one exists, else fall back to
       the hardcoded demo floor (``$3.85``) with ``is_fallback=True``.

    This never raises: an offline run still produces a usable price dict.
    """
    now = _now_ts()
    cached = _read_cache(region)

    if cached is not None and _is_fresh(cached, now):
        return {
            "price_per_gal": round(float(cached["price_per_gal"]), 3),
            "updated_at": cached["updated_at"],
            "source": SOURCE_CACHE,
            "is_fallback": False,
        }

    try:
        price = _fetch_benchmark(region)
        if price is None or price <= 0:
            raise RuntimeError(f"Invalid benchmark price: {price!r}")
    except Exception as exc:  # network / parse failures are never fatal
        logger.exception("Diesel benchmark fetch failed: %s", exc)
        if cached and cached.get("price_per_gal"):
            stale = dict(cached)
            stale["source"] = SOURCE_STALE
            stale["is_fallback"] = True
            return _to_public(stale)
        return {
            "price_per_gal": FALLBACK_PRICE_PER_GAL,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source": SOURCE_FALLBACK,
            "is_fallback": True,
        }

    payload = {
        "price_per_gal": round(float(price), 3),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_EIA,
        "is_fallback": False,
        "cache_ts": now,
    }
    _write_cache(region, payload)
    return _to_public(payload)


def get_effective_fuel_cost(carrier_discount: float = 0.0) -> float:
    """Fuel price per gallon after the carrier's fuel-card discount.

    Subtracts the carrier discount (e.g. ``$0.45``/gal) from the current
    benchmark price and clamps the result so it never drops below ``$0.00``.
    """
    benchmark = float(get_current_diesel_price()["price_per_gal"])
    discount = float(carrier_discount or 0.0)
    return round(max(benchmark - discount, 0.0), 2)