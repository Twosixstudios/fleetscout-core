import math
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

_FRONTEND_DIR = Path(__file__).parent / "gps_frontend"
COMPONENT_ROOT = str(_FRONTEND_DIR)

# Streamlit Cloud restricts static iframe assets, so only declare the path-based
# component when the inline HTML/JS build actually exists. Otherwise fall back to
# the built-in "Location unavailable" UI instead of rendering a warning banner.
if (_FRONTEND_DIR / "index.html").is_file():
    try:
        _gps_location = components.declare_component(
            "fleetscout_gps_location",
            path=COMPONENT_ROOT,
        )
    except Exception:
        _gps_location = None
else:
    _gps_location = None

# =========================================================================
# TASK-6.4: Mock GPS Telemetry Engine (SoCal I-10 / LA / Inland Empire)
# =========================================================================
# Whenever the live browser component returns nothing, raises, or yields an
# incomplete payload, we inject a realistic fleet snapshot instead of a blank
# "unavailable" state so the demo map always renders something meaningful.
MOCK_CENTER_LAT = 34.0522  # Downtown Los Angeles
MOCK_CENTER_LNG = -118.2437
MOCK_CORRIDOR_LABEL = "I-10 / LA Corridor"
MOCK_TELEMETRY_LABEL = f"📍 GPS: Live Demo Telemetry ({MOCK_CORRIDOR_LABEL})"
_LIVE_LABEL = "📍 GPS: Live Browser Position"

# Base fleet snapshot pinned to the freight corridor (unit, status, base
# lat/lon, base speed + heading_deg). The full dynamic feed is derived from this.
MOCK_FLEET = [
    {
        "unit": "TRK-001",
        "status": "In Transit",
        "lat": 34.0522,
        "lon": -118.2437,
        "speed_mph": 61,
        "heading_deg": 270,
    },
    {
        "unit": "TRK-002",
        "status": "Docked",
        "lat": 34.0600,
        "lon": -118.1300,
        "speed_mph": 0,
        "heading_deg": 0,
    },
    {
        "unit": "TRK-003",
        "status": "In Transit",
        "lat": 34.0452,
        "lon": -118.0137,
        "speed_mph": 52,
        "heading_deg": 45,
    },
    {
        "unit": "TRK-004",
        "status": "En Route",
        "lat": 34.0702,
        "lon": -117.9537,
        "speed_mph": 42,
        "heading_deg": 90,
    },
    {
        "unit": "TRK-005",
        "status": "Docked",
        "lat": 34.0702,
        "lon": -118.3837,
        "speed_mph": 0,
        "heading_deg": 180,
    },
    {
        "unit": "TRK-006",
        "status": "En Route",
        "lat": 34.0302,
        "lon": -117.8500,
        "speed_mph": 58,
        "heading_deg": 120,
    },
]


def generate_mock_telemetry(ref_time: int = 0) -> list[dict]:
    """Builds the demo fleet feed for a snapshot time.

    Deterministic per ``ref_time`` bucket: moving units drift slightly along
    the corridor while Docked units stay pinned to their exact base position
    with zero ground speed. Every marker carries ``demo: True`` so the UI can
    label the feed as live demo telemetry.
    """
    feed = []
    for i, base in enumerate(MOCK_FLEET):
        marker = dict(base)
        marker["demo"] = True
        marker["heading_deg"] = base["heading_deg"]
        if base["status"] == "Docked":
            marker["speed_mph"] = 0
            marker["lat"] = base["lat"]
            marker["lon"] = base["lon"]
        else:
            # Gentle deterministic drift between LA and the Inland Empire.
            marker["lat"] = round(
                base["lat"] + 0.004 * math.sin(ref_time / 60.0 + i), 6
            )
            marker["lon"] = round(
                base["lon"] + 0.006 * math.cos(ref_time / 90.0 + i * 1.7), 6
            )
            marker["speed_mph"] = base["speed_mph"]
        feed.append(marker)
    return feed


def _stable_seed(key: str) -> int:
    """Deterministic hash so the mock anchor stays stable across reruns."""
    return sum((i + 1) * ord(ch) for i, ch in enumerate(key or "fleetscout_gps"))


def mock_telemetry(key: str = "fleetscout_gps"):
    """Returns a demo telemetry payload for the given session ``key``.

    Fully deterministic per key: the drift anchor is derived from a stable
    hash of ``key`` rather than the wall clock, so the same session key always
    reproduces the identical fleet feed across reruns.
    """
    seed = _stable_seed(key)
    # Small deterministic nudge around the corridor center per session key.
    center_lat = MOCK_CENTER_LAT + ((seed % 37) - 18) * 0.0006
    center_lng = MOCK_CENTER_LNG + (((seed // 5) % 37) - 18) * 0.0006
    return {
        "demo": True,
        "fallback": True,
        "lat": center_lat,
        "lng": center_lng,
        "label": MOCK_TELEMETRY_LABEL,
        "vehicles": generate_mock_telemetry(ref_time=seed * 7 + 11),
    }


def format_gps_summary(gps):
    """Human-readable GPS line for captions; never shows a blank state."""
    if not gps:
        return "GPS"
    if gps.get("demo"):
        return gps.get("label") or MOCK_TELEMETRY_LABEL
    return f"{gps['lat']:.5f}, {gps['lng']:.5f}"


def gps_location(key: str = "fleetscout_gps"):
    """Returns a telemetry payload; never raises.

    FIX-5.9 defensive guards are preserved — if the custom iframe component is
    unavailable, raises on load, or returns an incomplete coordinate, a
    realistic mock telemetry payload is injected (TASK-6.4) instead of the
    blank "Location unavailable" state. Live GPS passes straight through.
    """
    if _gps_location is None:
        return mock_telemetry(key)
    try:
        result = _gps_location(key=key)
    except Exception:
        return mock_telemetry(key)
    if not result:
        return mock_telemetry(key)
    lat = result.get("lat")
    lng = result.get("lng")
    if lat is None or lng is None:
        return mock_telemetry(key)
    return {
        "lat": float(lat),
        "lng": float(lng),
        "demo": False,
        "fallback": False,
        "vehicles": [],
    }


def render_demo_map(key: str = "fleetscout_gps_demo"):
    """Renders the interactive demo telemetry map (Streamlit st.map layer).

    Shows the "📍 GPS: Live Demo Telemetry (I-10 / LA Corridor)" caption plus
    a per-marker table of unit, status, speed, and heading. A broken map layer
    gracefully degrades to the marker table so customer demos never crash.
    """
    telemetry = gps_location(key=key)
    label = telemetry.get("label") or MOCK_TELEMETRY_LABEL
    st.caption(label)

    vehicles = telemetry.get("vehicles")
    if not vehicles:
        # Live browser position: pin a single marker at the returned coords.
        vehicles = [
            {
                "unit": "LIVE-POS",
                "status": "Live GPS",
                "lat": telemetry.get("lat", MOCK_CENTER_LAT),
                "lon": telemetry.get("lng", MOCK_CENTER_LNG),
                "speed_mph": 0,
                "heading": 0,
                "demo": telemetry.get("demo", False),
            }
        ]

    try:
        st.map(pd.DataFrame(vehicles)[["lat", "lon"]])
    except Exception:
        # Map layer unavailable (e.g. bare/offline runner) — keep the demo alive.
        st.write("Interactive map layer unavailable — demo markers below.")

    marker_rows = [
        {
            "Unit": v["unit"],
            "Status": v["status"],
            "Speed (mph)": v.get("speed_mph", 0),
            "Heading (°)": v.get("heading", v.get("heading_deg", 0)),
        }
        for v in vehicles
    ]
    st.dataframe(marker_rows, use_container_width=True, hide_index=True)