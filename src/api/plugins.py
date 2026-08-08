"""FastAPI router exposing modular plugin capabilities.

Registered in ``src/main.py`` under the ``/api/plugins`` prefix. All
handlers are strictly asynchronous and never touch the database.

Also hosts the dynamic :class:`PluginRegistry` used by ``src.core.services``
so plugin hooks can be wired into the dispatch flow while staying isolated.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from src.plugins.base import BasePlugin
from src.plugins.freightslip_adapter import FreightSlipAdapter
from src.plugins.lanesight_adapter import LaneSightAdapter

router = APIRouter()

freightslip_adapter = FreightSlipAdapter()
lanesight_adapter = LaneSightAdapter()


class PluginRegistry:
    """Dynamic registry of modular FleetScout plugins, keyed by name.

    Plugins are registered, retrieved, listed, and safely executed here.
    :meth:`execute` guarantees plugin failures never escape: every exception
    is trapped and surfaced as a structured error dict so callers can decide
    how to degrade without crashing core dispatch or rolling back any
    database transaction.
    """

    def __init__(self) -> None:
        self._plugins: Dict[str, BasePlugin] = {}

    def register(self, plugin: BasePlugin) -> BasePlugin:
        """Register a plugin adapter under its ``name`` (idempotency not allowed)."""
        if not isinstance(plugin, BasePlugin):
            raise TypeError(
                f"Expected a BasePlugin instance, got {type(plugin).__name__}."
            )
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin '{plugin.name}' is already registered.")
        self._plugins[plugin.name] = plugin
        return plugin

    def get(self, name: str) -> Optional[BasePlugin]:
        """Retrieve a registered plugin by name, or None if unknown."""
        return self._plugins.get(name)

    def names(self) -> list:
        """Return registered plugin names in registration order."""
        return list(self._plugins)

    def list(self) -> Dict[str, Any]:
        """Return metadata for every registered plugin."""
        return {
            name: plugin.metadata()
            for name, plugin in self._plugins.items()
        }

    async def execute(
        self, name: str, data: Dict[str, Any], **kwargs: Any
    ) -> Dict[str, Any]:
        """Safely run a registered plugin, trapping all execution errors."""
        plugin = self.get(name)
        if plugin is None:
            return {
                "ok": False,
                "plugin": name,
                "error": f"Plugin '{name}' is not registered.",
            }
        try:
            if not await plugin.validate():
                return {
                    "ok": False,
                    "plugin": name,
                    "error": f"Plugin '{name}' failed validation.",
                }
            result = await plugin.execute(data, **kwargs)
            return {"ok": True, "plugin": name, "result": result}
        except Exception as exc:
            return {"ok": False, "plugin": name, "error": str(exc)}


plugin_registry = PluginRegistry()
plugin_registry.register(freightslip_adapter)
plugin_registry.register(lanesight_adapter)


@router.get("", tags=["Plugins"])
async def list_registered_plugins() -> Dict[str, Any]:
    """List the modular plugins available in the registry."""
    return {"plugins": list(plugin_registry.list().values())}


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