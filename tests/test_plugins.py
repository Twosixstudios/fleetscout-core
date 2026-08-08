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
    async def fake_route(self, origin, destination):
        return {"provider": "haversine", "origin": origin, "destination": destination, "distance_miles": 50.0}

    monkeypatch.setattr(LaneSightAdapter, "get_route", fake_route)
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


# ---------------------------------------------------------------------------
# Adapter execute() / validate() contract (HD-5.1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_freightslip_adapter_validate_and_execute():
    adapter = FreightSlipAdapter()
    assert await adapter.validate() is True

    result = await adapter.execute(
        {"action": "parse", "file_bytes": SAMPLE_RATE_CONFIRMATION.encode("utf-8")}
    )
    assert result["load_number"] == "100001"
    assert result["total_pay"] == 2765.75


@pytest.mark.asyncio
async def test_freightslip_execute_accepts_text_content():
    adapter = FreightSlipAdapter()
    result = await adapter.execute({"action": "parse", "content": SAMPLE_RATE_CONFIRMATION})
    assert result["load_number"] == "100001"


@pytest.mark.asyncio
async def test_freightslip_execute_rejects_unknown_action():
    adapter = FreightSlipAdapter()
    with pytest.raises(ValueError):
        await adapter.execute({"action": "heatmap", "file_bytes": b"x"})


@pytest.mark.asyncio
async def test_lanesight_validate_and_execute_route():
    adapter = LaneSightAdapter()
    assert await adapter.validate() is True

    result = await adapter.execute(
        {"action": "route", "origin": "Nowhere", "destination": "Elsewhere"}
    )
    assert result["provider"] == "unavailable"


@pytest.mark.asyncio
async def test_lanesight_execute_hos():
    plan = await LaneSightAdapter().execute(
        {"action": "hos", "driving_hours": 9.0, "start_time": "06:00"}
    )
    assert plan["rest_break_count"] == 1
    assert len(plan["segments"]) == 3


# ---------------------------------------------------------------------------
# Plugin registry (HD-5.1)
# ---------------------------------------------------------------------------


from src.api.plugins import PluginRegistry, plugin_registry  # noqa: E402


def test_registry_register_and_retrieve():
    registry = PluginRegistry()
    adapter = FreightSlipAdapter()
    registry.register(adapter)

    assert registry.get("freightslip") is adapter
    assert registry.names() == ["freightslip"]
    assert registry.list()["freightslip"]["name"] == "freightslip"


def test_registry_rejects_duplicate_registration():
    registry = PluginRegistry()
    registry.register(FreightSlipAdapter())
    with pytest.raises(ValueError):
        registry.register(FreightSlipAdapter())


def test_registry_rejects_non_plugin_instance():
    registry = PluginRegistry()
    with pytest.raises(TypeError):
        registry.register(object())


def test_global_registry_seeded_with_expected_plugins():
    assert set(plugin_registry.names()) == {"freightslip", "lanesight"}
    assert plugin_registry.get("freightslip") is not None
    assert plugin_registry.get("lanesight") is not None


@pytest.mark.asyncio
async def test_registry_execute_freightslip():
    registry = PluginRegistry()
    registry.register(FreightSlipAdapter())
    result = await registry.execute(
        "freightslip", {"action": "parse", "file_bytes": SAMPLE_RATE_CONFIRMATION.encode("utf-8")}
    )
    assert result["ok"] is True
    assert result["result"]["load_number"] == "100001"


@pytest.mark.asyncio
async def test_registry_execute_unknown_plugin_returns_error():
    result = await PluginRegistry().execute("nope", {})
    assert result["ok"] is False
    assert "not registered" in result["error"]


@pytest.mark.asyncio
async def test_registry_execute_traps_plugin_exceptions():
    registry = PluginRegistry()
    registry.register(FreightSlipAdapter())
    result = await registry.execute(
        "freightslip", {"action": "parse", "file_bytes": b"\x00\x01 no  load here"}
    )
    assert result["ok"] is False
    assert "error" in result


# ---------------------------------------------------------------------------
# Service integration: plugin hooks never crash dispatch or roll back DB
# ---------------------------------------------------------------------------


from src.core.database import AsyncSessionLocal, Base, sync_engine  # noqa: E402
from src.core.models import Vehicle, Load  # noqa: E402
from src.core.services import run_plugin_hook, dispatch_load_with_plugins  # noqa: E402
from sqlalchemy import select  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def reset_schema():
    Base.metadata.drop_all(bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)


@pytest.mark.asyncio
async def test_run_plugin_hook_isolates_failing_plugin():
    result = await run_plugin_hook(
        "freightslip", {"action": "parse", "file_bytes": b"\x00\x01 no  digits here"}
    )
    assert result["ok"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_run_plugin_hook_unknown_plugin():
    result = await run_plugin_hook("does-not-exist", {})
    assert result["ok"] is False
    assert "not registered" in result["error"]


@pytest.mark.asyncio
async def test_plugin_failure_does_not_roll_back_session():
    async with AsyncSessionLocal() as session:
        vehicle = Vehicle(unit_number="PLG-DB-LIVE", status="Active", carrier_id=1)
        session.add(vehicle)

        # A failing plugin hook runs inside the same open session.
        result = await run_plugin_hook(
            "freightslip", {"action": "parse", "file_bytes": b"\x00\x01 garbage"}
        )
        assert result["ok"] is False

        # The session transaction must still commit normally afterwards.
        await session.commit()
        await session.refresh(vehicle)
        vehicle_id = vehicle.id

    async with AsyncSessionLocal() as session:
        fresh = await session.get(Vehicle, vehicle_id)
        assert fresh is not None
        assert fresh.unit_number == "PLG-DB-LIVE"


def test_dispatch_with_failing_plugin_hook_still_dispatches():
    """A failing RateCon plugin must not block or crash dispatch."""
    import asyncio

    vehicle_id, load, enrichment = None, None, None

    async def _go():
        nonlocal vehicle_id, load, enrichment
        async with AsyncSessionLocal() as session:
            vehicle = Vehicle(unit_number="PLG-ACTIVE-01", status="Active", carrier_id=1)
            session.add(vehicle)
            await session.commit()
            await session.refresh(vehicle)
            vehicle_id = vehicle.id

        async with AsyncSessionLocal() as session:
            load, enrichment = await dispatch_load_with_plugins(
                session,
                assigned_vehicle_id=vehicle_id,
                ratecon_bytes=b"\x00\x01 totally unparseable \x02",
            )

    asyncio.run(_go())

    assert load is not None
    assert load.status == "dispatched"
    assert enrichment["freightslip"]["ok"] is False

    async def _verify():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Load).where(Load.load_number == load.load_number)
            )
            return result.scalars().first() is not None

    assert asyncio.run(_verify())


def test_dispatch_with_plugin_enrichment_and_route(monkeypatch):
    """RateCon + lanesight enrich the dispatched load's fields/notes (offline)."""
    import asyncio

    from src.plugins.lanesight_adapter import LaneSightAdapter

    async def _fake_route(self, origin, destination, transport=None):
        return {
            "provider": "haversine",
            "origin": origin,
            "destination": destination,
            "distance_miles": 123.4,
            "duration_hours": 2.5,
        }

    monkeypatch.setattr(LaneSightAdapter, "get_route", _fake_route)

    monkeypatch.setattr(LaneSightAdapter, "get_route", _fake_route)

    combined = {}

    async def _go():
        async with AsyncSessionLocal() as session:
            vehicle = Vehicle(unit_number="PLG-ENRICH-01", status="Active", carrier_id=1)
            session.add(vehicle)
            await session.commit()
            await session.refresh(vehicle)
            vehicle_id = vehicle.id

        async with AsyncSessionLocal() as session:
            load, enrichment = await dispatch_load_with_plugins(
                session,
                assigned_vehicle_id=vehicle_id,
                ratecon_bytes=SAMPLE_RATE_CONFIRMATION.encode("utf-8"),
                origin="36.7378,-119.7871",
                destination="36.7378,-119.0",
                hos_driving_hours=9.0,
                hos_start_time="06:00",
            )
            combined["load"] = load
            combined["enrichment"] = enrichment

    asyncio.run(_go())

    load = combined["load"]
    enrichment = combined["enrichment"]

    assert load.commodity == "Auto Parts"
    assert load.pickup_ref == "SHPR-8891"
    assert load.delivery_ref == "CO-778"
    assert enrichment["freightslip"]["ok"] is True
    assert enrichment["lanesight"]["ok"] is True
    assert enrichment["lanesight_hos"]["ok"] is True
    assert "123.4 mi" in load.dispatcher_notes
    assert "HOS:" in load.dispatcher_notes


def test_registry_listing_endpoint(client):
    response = client.get("/api/plugins")
    assert response.status_code == 200
    payload = response.json()
    names = {p["name"] for p in payload["plugins"]}
    assert names == {"freightslip", "lanesight"}