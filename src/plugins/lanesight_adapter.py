"""LaneSight routing and HOS calculations adapter.

Wraps the LaneSight routing engine (OSRM over HTTP) and its HOS estimator
behind a uniform async interface. Network calls are made with ``httpx`` and
degrade gracefully to a Haversine geodesic fallback when the OSRM service is
unreachable, keeping core FleetScout logic offline-first.
"""

import math
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.plugins.base import BasePlugin

OSRM_BASE_URL = "https://router.project-osrm.org/route/v1/driving"
TIMEOUT_SECONDS = 10.0
AVERAGE_MPH = 45.0
METERS_PER_MILE = 1609.344
DRIVE_BLOCK_HOURS = 8.0
REST_BREAK_HOURS = 0.5
MAX_DAILY_DRIVE_HOURS = 11.0
SLEEPER_RESET_HOURS = 10.0

COORD_PAIR_PATTERN = re.compile(
    r"([+-]?\d{1,3}(?:\.\d+)?)\s*,\s*([+-]?\d{1,3}(?:\.\d+)?)"
)


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two coordinate pairs in meters."""
    earth_radius_m = 6371008.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * earth_radius_m * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_coordinate_pair(location: str) -> Optional[Tuple[float, float]]:
    """Parse a ``"lat,lng"`` location string into a coordinate tuple."""
    match = COORD_PAIR_PATTERN.search(location.strip())
    if match is None:
        return None
    return float(match.group(1)), float(match.group(2))


def _parse_start_time(start_time: str) -> datetime:
    """Parse an ISO-8601 datetime or a ``HH:MM`` clock time into a datetime."""
    stripped = start_time.strip()
    try:
        return datetime.fromisoformat(stripped)
    except ValueError:
        pass
    try:
        hour_text, minute_text = stripped.split(":")
        base_date = datetime(2000, 1, 1)
        return base_date.replace(hour=int(hour_text), minute=int(minute_text))
    except ValueError as exc:
        raise ValueError(f"Invalid start_time: {start_time!r}. Use ISO-8601 or HH:MM.") from exc


class LaneSightAdapter(BasePlugin):
    """Plugin adapter exposing LaneSight routing and HOS planning capabilities."""

    name = "lanesight"
    version = "0.1.0"
    description = "OSRM route lookup (with geodesic fallback) and DOT HOS scheduling."

    def _extract_coordinates(self, origin: str, destination: str) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Validate and return the ``(lat, lng)`` tuples for both endpoints."""
        origin_coords = _parse_coordinate_pair(origin)
        destination_coords = _parse_coordinate_pair(destination)
        if origin_coords is None or destination_coords is None:
            raise ValueError("origin and destination must be 'lat,lng' coordinate pairs.")
        return origin_coords, destination_coords

    async def get_route(
        self,
        origin: str,
        destination: str,
        transport: Optional[httpx.Transport] = None,
    ) -> Dict[str, Any]:
        """Return routing geometry and duration, preferring OSRM via httpx.

        Falls back to a Haversine geodesic estimate when the OSRM service is
        unreachable or times out.
        """
        schema = {
            "origin": origin,
            "destination": destination,
        }
        try:
            (lat1, lon1), (lat2, lon2) = self._extract_coordinates(origin, destination)
        except ValueError:
            schema["provider"] = "unavailable"
            schema["distance_miles"] = None
            schema["duration_hours"] = None
            schema["geometry"] = []
            schema["error"] = "Origin and destination must resolve to lat,lng coordinate pairs."
            return schema

        request_url = f"{OSRM_BASE_URL}/{lon1},{lat1};{lon2},{lat2}"

        timeout = httpx.Timeout(TIMEOUT_SECONDS)
        async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
            try:
                response = await client.get(request_url)
                return self._build_osrm_response(response.json(), origin, destination)
            except (httpx.HTTPError, KeyError, IndexError, ValueError):
                return self._haversine_fallback(origin, destination, (lat1, lon1), (lat2, lon2))

    @staticmethod
    def _build_osrm_response(payload: Dict[str, Any], origin: str, destination: str) -> Dict[str, Any]:
        route = payload["routes"][0]
        distance_meters = route["distance"]
        duration_seconds = route["duration"]
        geometry = route["geometry"].get("coordinates", [])
        return {
            "provider": "osrm",
            "origin": origin,
            "destination": destination,
            "distance_miles": distance_meters / METERS_PER_MILE,
            "duration_hours": duration_seconds / 3600.0,
            "duration_seconds": duration_seconds,
            "geometry": geometry,
        }

    @staticmethod
    def _haversine_fallback(
        origin: str,
        destination: str,
        origin_coord: Tuple[float, float],
        destination_coord: Tuple[float, float],
    ) -> Dict[str, Any]:
        (lat1, lon1) = origin_coord
        (lat2, lon2) = destination_coord
        distance_meters = _haversine_meters(lat1, lon1, lat2, lon2)
        distance_miles = distance_meters / METERS_PER_MILE
        duration_hours = distance_miles / AVERAGE_MPH
        return {
            "provider": "haversine",
            "origin": origin,
            "destination": destination,
            "distance_miles": distance_miles,
            "duration_hours": duration_hours,
            "duration_seconds": duration_hours * 3600.0,
            "geometry": [[lon1, lat1], [lon2, lat2]],
        }

    def calculate_hos_schedule(self, driving_hours: float, start_time: str) -> Dict[str, Any]:
        """Plan a DOT-compliant driving schedule.

        Inserts mandatory 30-minute rest breaks after every 8 hours of
        driving, enforces the 11-hour daily driving limit with a 10-hour
        sleeper berth reset, and reports the next 10-hour reset availability.
        """
        total_hours = float(driving_hours)
        if total_hours <= 0:
            raise ValueError("driving_hours must be a positive number.")
        current = _parse_start_time(start_time)
        remaining = total_hours
        driven_today = 0.0
        segments: List[Dict[str, Any]] = []

        while remaining > 1e-9:
            block = min(DRIVE_BLOCK_HOURS, remaining)
            if driven_today + block > MAX_DAILY_DRIVE_HOURS + 1e-9:
                allowed = MAX_DAILY_DRIVE_HOURS - driven_today
                if allowed <= 1e-9:
                    segments.append(self._segment("rest", current, SLEEPER_RESET_HOURS, "10h sleeper reset"))
                    current += timedelta(hours=SLEEPER_RESET_HOURS)
                    driven_today = 0.0
                    continue
                block = allowed

            drive_start = current
            current += timedelta(hours=block)
            segments.append(self._segment("driving", drive_start, block, "drive"))
            remaining -= block
            driven_today += block

            if remaining > 1e-9:
                segments.append(self._segment("rest", current, REST_BREAK_HOURS, "mandatory 30min after 8h"))
                current += timedelta(hours=REST_BREAK_HOURS)

        return {
            "total_driving_hours": total_hours,
            "start_time": _iso(_parse_start_time(start_time)),
            "end_time": _iso(current),
            "segments": segments,
            "rest_break_count": sum(1 for s in segments if s["type"] == "rest"),
            "sleeper_berth_reset": {
                "reset_hours": SLEEPER_RESET_HOURS,
                "available_at": _iso(current + timedelta(hours=SLEEPER_RESET_HOURS)),
            },
        }

    @staticmethod
    def _segment(kind: str, start: datetime, hours: float, reason: str) -> Dict[str, Any]:
        end = start + timedelta(hours=hours)
        return {
            "type": kind,
            "start_time": _iso(start),
            "end_time": _iso(end),
            "duration_hours": hours,
            "reason": reason,
        }

    async def run(self, action: str, **kwargs: Any) -> Dict[str, Any]:
        if action == "route":
            return await self.get_route(kwargs["origin"], kwargs["destination"])
        if action == "hos":
            return self.calculate_hos_schedule(kwargs["driving_hours"], kwargs["start_time"])
        raise ValueError(f"LaneSight does not support action: {action}")

    async def health_check(self) -> Dict[str, Any]:
        return {
            "plugin": self.name,
            "version": self.version,
            "description": self.description,
            "osrm_endpoint": OSRM_BASE_URL,
            "fallback": "haversine",
            "status": "ok",
        }


def _iso(value: datetime) -> str:
    """Render a datetime as an ISO-8601 string."""
    return value.isoformat()