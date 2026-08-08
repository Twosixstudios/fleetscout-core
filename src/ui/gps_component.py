from pathlib import Path

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


def gps_location(key: str = "fleetscout_gps"):
    """Returns {lat, lng} or None; never raises on component load failures.

    If the custom iframe component fails or is unavailable the yellow Streamlit
    warning banner is suppressed and None is returned, which renders the
    "GPS: Location unavailable" fallback text in the driver UI.
    """
    if _gps_location is None:
        return None
    try:
        result = _gps_location(key=key)
    except Exception:
        return None
    if not result:
        return None
    lat = result.get("lat")
    lng = result.get("lng")
    if lat is None or lng is None:
        return None
    return {"lat": float(lat), "lng": float(lng)}