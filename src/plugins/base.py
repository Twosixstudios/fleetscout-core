"""Base abstraction for modular FleetScout plugins.

Plugin adapters wrap the public interfaces of external projects
(FreightSlip, LaneSight) behind a uniform, stable contract so that
core FleetScout business logic depends on an abstraction rather than a
concrete third-party implementation (Dependency Inversion Principle).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BasePlugin(ABC):
    """Abstract interface shared by every FleetScout plugin adapter."""

    name: str = "base"
    version: str = "0.1.0"
    description: str = ""

    @abstractmethod
    async def run(self, action: str, **kwargs: Any) -> Dict[str, Any]:
        """Dispatch a named capability exposed by this plugin."""

    async def health_check(self) -> Dict[str, Any]:
        """Report plugin readiness and metadata without network I/O."""
        return {
            "plugin": self.name,
            "version": self.version,
            "description": self.description,
            "status": "ok",
        }

    def metadata(self) -> Dict[str, Optional[str]]:
        """Return static plugin metadata for registry displays."""
        return {"name": self.name, "version": self.version, "description": self.description}