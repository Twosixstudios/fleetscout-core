"""FreightSlip rate-confirmation parsing adapter.

Wraps the FreightSlip RateCon PDF parsing engine behind a uniform async
interface. When the external package is unavailable on the runtime, the
adapter degrades gracefully to a dependency-free regex/text extractor, so
core business logic never depends on the presence of a heavy PDF library.
"""

import re
from typing import Any, Callable, Dict, Optional

from src.plugins.base import BasePlugin

WEIGHT_PATTERN = re.compile(r"(?i)weight\s*[:#]\s*([\d,]+)")
LOAD_PATTERN = re.compile(r"(?i)load\s*(?:#|number|no\.?)?\s*[:#]\s*([A-Za-z0-9\-_/]+)")
COMMODITY_PATTERN = re.compile(r"(?i)commodity\s*[:#]\s*([A-Za-z][^\r\n]*)")
PICKUP_PATTERN = re.compile(r"(?i)pickup(?:[_ ]?ref(?:erence)?)?\s*[:#]\s*([A-Za-z0-9\-_/]+)")
DELIVERY_PATTERN = re.compile(r"(?i)deliver(?:y)?(?:[_ ]?ref(?:erence)?)?\s*[:#]\s*([A-Za-z0-9\-_/]+)")
LINEHAUL_PATTERN = re.compile(r"(?i)line\s*haul(?:[_ ]?rate)?\s*[:#]\s*\$?\s*([\d,]+\.?\d*)")
FUEL_PATTERN = re.compile(r"(?i)fuel(?:[_ ]?surcharge)?\s*[:#]\s*\$?\s*([\d,]+\.?\d*)")
TOTAL_PATTERN = re.compile(r"(?i)total\s*pay(?:ment)?\s*[:#]\s*\$?\s*([\d,]+\.?\d*)")


class FreightSlipAdapter(BasePlugin):
    """Plugin adapter exposing FreightSlip RateCon parsing capabilities."""

    name = "freightslip"
    version = "0.1.0"
    description = "Parse Rate Confirmations into structured load and pay fields."

    def __init__(self, external_parser: Optional[Callable[[bytes], Dict[str, Any]]] = None) -> None:
        self._external_parser = external_parser or self._load_external_engine()

    def _load_external_engine(self) -> Optional[Callable[[bytes], Dict[str, Any]]]:
        """Attempt to import the real FreightSlip engine if installed."""
        try:
            from freightslip import parse_rate_confirmation  # type: ignore

            return parse_rate_confirmation
        except (ImportError, AttributeError):
            return None

    @staticmethod
    def _decode_payload(file_bytes: bytes) -> str:
        """Decode raw bytes into text across common encodings."""
        for encoding in ("utf-8", "latin-1"):
            try:
                return file_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        return file_bytes.decode("utf-8", errors="ignore")

    @staticmethod
    def _regex_extract(text: str) -> Dict[str, Any]:
        """Dependency-free text-matching fallback for RateCon extraction."""
        data: Dict[str, Any] = {}

        weight_match = WEIGHT_PATTERN.search(text)
        if weight_match:
            data["weight"] = int(weight_match.group(1).replace(",", ""))

        load_match = LOAD_PATTERN.search(text)
        if load_match:
            data["load_number"] = load_match.group(1)

        commodity_match = COMMODITY_PATTERN.search(text)
        if commodity_match:
            data["commodity"] = commodity_match.group(1).strip().strip(",")

        pickup_match = PICKUP_PATTERN.search(text)
        if pickup_match:
            data["pickup_ref"] = pickup_match.group(1)

        delivery_match = DELIVERY_PATTERN.search(text)
        if delivery_match:
            data["delivery_ref"] = delivery_match.group(1)

        for key, pattern in (
            ("linehaul_rate", LINEHAUL_PATTERN),
            ("fuel_surcharge", FUEL_PATTERN),
            ("total_pay", TOTAL_PATTERN),
        ):
            match = pattern.search(text)
            if match:
                data[key] = float(match.group(1).replace(",", ""))

        return data

    async def parse_rate_confirmation(self, file_bytes: bytes) -> Dict[str, Any]:
        """Extract load and payment fields from a RateConfirmation payload.

        Attempts the external FreightSlip engine first, then falls back to
        the built-in regex extractor. Raises ``ValueError`` if nothing usable
        can be parsed.
        """
        if self._external_parser is not None:
            try:
                parsed = self._external_parser(file_bytes)
                if isinstance(parsed, dict) and parsed:
                    parsed["provider"] = "external"
                    return parsed
            except Exception:
                pass

        text = self._decode_payload(file_bytes)
        data = self._regex_extract(text)
        if not data:
            raise ValueError("Unable to parse the uploaded file as a RateConfirmation.")
        data["provider"] = "fallback"
        return data

    async def validate(self) -> bool:
        """The adapter is always usable offline thanks to the regex fallback."""
        return True

    async def execute(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Execute the RateCon parse action against a structured payload."""
        action = data.get("action", "parse")
        if action != "parse":
            raise ValueError(f"FreightSlip does not support action: {action}")
        payload = data.get("file_bytes", data.get("content"))
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        if payload is None:
            raise ValueError("parse requires a 'file_bytes' or 'content' payload.")
        return await self.parse_rate_confirmation(payload)

    async def run(self, action: str, **kwargs: Any) -> Dict[str, Any]:
        """Dispatch the plugin's parse action."""
        if action == "parse":
            return await self.parse_rate_confirmation(kwargs["file_bytes"])
        raise ValueError(f"FreightSlip does not support action: {action}")

    async def health_check(self) -> Dict[str, Any]:
        return {
            "plugin": self.name,
            "version": self.version,
            "description": self.description,
            "external_engine_available": self._external_parser is not None,
            "status": "ok",
        }