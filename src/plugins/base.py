"""Base abstraction for modular FleetScout plugins.

Plugin adapters wrap the public interfaces of external projects
(FreightSlip, LaneSight) behind a uniform, stable contract so that
core FleetScout business logic depends on an abstraction rather than a
concrete third-party implementation (Dependency Inversion Principle).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BasePlugin(ABC):
    """Abstract interface shared by every FleetScout plugin adapter.

    Adapters expose two mandatory contract methods:

    - ``validate()``: a cheap, offline guard reporting whether the plugin's
      runtime preconditions are satisfied before execution.
    - ``execute(data)``: the single entry point that runs the plugin against a
      structured payload and returns a structured result dict.
    """

    name: str = "base"
    version: str = "0.1.0"
    description: str = ""

    @abstractmethod
    async def validate(self) -> bool:
        """Return True when the plugin's preconditions are satisfied."""

    @abstractmethod
    async def execute(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Execute the plugin against a named payload and return structured output."""

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