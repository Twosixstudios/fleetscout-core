from pathlib import Path

import streamlit.components.v1 as components

COMPONENT_ROOT = str(Path(__file__).parent / "gps_frontend")

_gps_location = components.declare_component(
    "fleetscout_gps_location",
    path=COMPONENT_ROOT,
)


def gps_location(key: str = "fleetscout_gps"):
    """Renders the browser geolocation component and returns {lat, lng} or None."""
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