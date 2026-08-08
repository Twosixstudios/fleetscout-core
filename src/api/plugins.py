"""FastAPI router exposing modular plugin capabilities.

Registered in ``src/main.py`` under the ``/api/plugins`` prefix. All
handlers are strictly asynchronous and never touch the database.
"""

from typing import Any, Dict

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from src.plugins.freightslip_adapter import FreightSlipAdapter
from src.plugins.lanesight_adapter import LaneSightAdapter

router = APIRouter()

freightslip_adapter = FreightSlipAdapter()
lanesight_adapter = LaneSightAdapter()


class RouteRequest(BaseModel):
    """Coordinates/place names for a route lookup."""

    origin: str = Field(..., description="Origin as 'lat,lng' coordinate pair.")
    destination: str = Field(..., description="Destination as 'lat,lng' coordinate pair.")


class HOSRequest(BaseModel):
    """Driving plan inputs for the HOS schedule calculator."""

    driving_hours: float = Field(..., gt=0, description="Planned driving hours.")
    start_time: str = Field(..., description="Start time as ISO-8601 or HH:MM.")


@router.post("/freightslip/parse", tags=["Plugins"])
async def parse_rate_confirmation(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Parse an uploaded RateCon document into structured load/pay fields."""
    content = await file.read()
    try:
        return await freightslip_adapter.parse_rate_confirmation(file_bytes=content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/lanesight/route", tags=["Plugins"])
async def get_route(request: RouteRequest) -> Dict[str, Any]:
    """Resolve routing geometry and travel time for a route lookup."""
    return await lanesight_adapter.get_route(
        origin=request.origin,
        destination=request.destination,
    )


@router.post("/lanesight/hos", tags=["Plugins"])
async def calculate_hos_schedule(request: HOSRequest) -> Dict[str, Any]:
    """Build a DOT-compliant driving and rest schedule."""
    try:
        return lanesight_adapter.calculate_hos_schedule(
            driving_hours=request.driving_hours,
            start_time=request.start_time,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))