"""Isolated integration and unit tests for modular plugin adapters.

All network-bound OSRM calls are mocked with ``httpx.MockTransport`` so the
suite stays 100% green offline. FreightSlip parsing is exercised on both the
external-engine and regex-fallback paths, and LaneSight covers both OSRM and
Haversine fallback behaviors plus DOT HOS scheduling.
"""

from datetime import datetime, timedelta

import httpx
import pytest

from src.plugins.freightslip_adapter import FreightSlipAdapter
from src.plugins.lanesight_adapter import (
    LaneSightAdapter,
    SLEEPER_RESET_HOURS,
    _haversine_meters,
)

SAMPLE_RATE_CONFIRMATION = (
    "Rate Confirmation\n"
    "Load #: 100001\n"
    "Weight: 42,800 lbs\n"
    "Commodity: Auto Parts\n"
    "Pickup Ref: SHPR-8891\n"
    "Delivery Ref: CO-778\n"
    "Linehaul Rate: 2450.00\n"
    "Fuel Surcharge: 315.75\n"
    "Total Pay: 2765.75\n"
)


# ---------------------------------------------------------------------------
# FreightSlip adapter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_rate_confirmation_regex_fallback():
    adapter = FreightSlipAdapter()
    result = await adapter.parse_rate_confirmation(SAMPLE_RATE_CONFIRMATION.encode("utf-8"))

    assert result["provider"] == "fallback"
    assert result["load_number"] == "100001"
    assert result["weight"] == 42800
    assert result["commodity"] == "Auto Parts"
    assert result["pickup_ref"] == "SHPR-8891"
    assert result["delivery_ref"] == "CO-778"
    assert result["linehaul_rate"] == 2450.00
    assert result["fuel_surcharge"] == 315.75
    assert result["total_pay"] == 2765.75


@pytest.mark.asyncio
async def test_parse_external_provider_wins():
    def fake_parser(file_bytes: bytes) -> dict:
        return {
            "load_number": "EXT-99",
            "weight": 10000,
            "commodity": "Custom Cargo",
            "pickup_ref": "P-1",
            "delivery_ref": "D-1",
        }

    adapter = FreightSlipAdapter(external_parser=fake_parser)
    result = await adapter.parse_rate_confirmation(b"Rate Confirmation\nLoad #: 100001")

    assert result["provider"] == "external"
    assert result["load_number"] == "EXT-99"


@pytest.mark.asyncio
async def test_parse_rate_confirmation_raises_on_garbage():
    adapter = FreightSlipAdapter()
    with pytest.raises(ValueError):
        await adapter.parse_rate_confirmation(b"\x00\x01\x02\x03 no  digits here either")


# ---------------------------------------------------------------------------
# LaneSight adapter - routing
# ---------------------------------------------------------------------------


def _osrm_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "code": "Ok",
            "routes": [
                {
                    "distance": 100000.0,
                    "duration": 3600.0,
                    "geometry": {"type": "LineString", "coordinates": [[-119.7871, 36.7378], [-119.0, 36.7378]]},
                }
            ],
        },
    )


@pytest.mark.asyncio
async def test_get_route_osrm_success():
    transport = httpx.MockTransport(_osrm_handler)
    result = await LaneSightAdapter().get_route(
        origin="36.7378,-119.7871",
        destination="36.7378,-119.0",
        transport=transport,
    )

    assert result["provider"] == "osrm"
    assert result["distance_miles"] == pytest.approx(100000.0 / 1609.344, rel=1e-6)
    assert result["duration_hours"] == pytest.approx(1.0, rel=1e-6)
    assert len(result["geometry"]) == 2


@pytest.mark.asyncio
async def test_get_route_falls_back_to_haversine_when_osrm_unreachable():
    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated network outage")

    transport = httpx.MockTransport(unreachable)
    result = await LaneSightAdapter().get_route(
        origin="36.7378,-119.7871",
        destination="36.7378,-119.0",
        transport=transport,
    )

    assert result["provider"] == "haversine"
    expected_miles = _haversine_meters(36.7378, -119.7871, 36.7378, -119.0) / 1609.344
    assert result["distance_miles"] == pytest.approx(expected_miles, rel=1e-6)
    assert result["duration_hours"] > 0


@pytest.mark.asyncio
async def test_get_route_handles_malformed_coordinates():
    result = await LaneSightAdapter().get_route(origin="Nowhere", destination="Elsewhere")
    assert result["provider"] == "unavailable"
    assert result["error"]


# ---------------------------------------------------------------------------
# LaneSight adapter - HOS scheduling
# ---------------------------------------------------------------------------


def test_hos_schedule_under_eight_hours_no_break():
    plan = LaneSightAdapter().calculate_hos_schedule(driving_hours=7.5, start_time="06:00")
    assert plan["rest_break_count"] == 0
    assert len(plan["segments"]) == 1
    assert plan["segments"][0]["type"] == "driving"


def test_hos_schedule_inserts_thirty_min_break_after_eight_hours():
    plan = LaneSightAdapter().calculate_hos_schedule(driving_hours=9.0, start_time="06:00")
    assert [s["type"] for s in plan["segments"]] == ["driving", "rest", "driving"]
    break_segment = plan["segments"][1]
    assert break_segment["duration_hours"] == 0.5
    assert break_segment["reason"] == "mandatory 30min after 8h"


def test_hos_schedule_sleeper_reset_availability():
    plan = LaneSightAdapter().calculate_hos_schedule(driving_hours=23.0, start_time="2026-08-07T06:00:00")
    end_time = datetime.fromisoformat(plan["end_time"])
    expected_available = end_time + timedelta(hours=SLEEPER_RESET_HOURS)
    assert datetime.fromisoformat(plan["sleeper_berth_reset"]["available_at"]) == expected_available


def test_hos_schedule_rejects_negative_hours():
    with pytest.raises(ValueError):
        LaneSightAdapter().calculate_hos_schedule(driving_hours=-2, start_time="06:00")


# ---------------------------------------------------------------------------
# FastAPI endpoint integration (mocked, offline)
# ---------------------------------------------------------------------------


def test_freightslip_parse_endpoint(client):
    response = client.post(
        "/api/plugins/freightslip/parse",
        files={"file": ("rate_con.pdf", SAMPLE_RATE_CONFIRMATION.encode("utf-8"), "application/pdf")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["load_number"] == "100001"
    assert payload["total_pay"] == 2765.75


def test_lanesight_route_endpoint(client, monkeypatch):
    async def fake_route(origin, destination):
        return {"provider": "haversine", "origin": origin, "destination": destination, "distance_miles": 50.0}

    monkeypatch.setattr("src.api.plugins.lanesight_adapter.get_route", fake_route)
    response = client.post(
        "/api/plugins/lanesight/route",
        json={"origin": "36.7378,-119.7871", "destination": "36.7378,-119.0"},
    )
    assert response.status_code == 200
    assert response.json()["provider"] == "haversine"


def test_lanesight_hos_endpoint(client):
    response = client.post(
        "/api/plugins/lanesight/hos",
        json={"driving_hours": 9.0, "start_time": "06:00"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["rest_break_count"] == 1
    assert len(payload["segments"]) == 3