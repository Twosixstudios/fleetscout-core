"""FreightSlip rate confirmation parsing + Form auto-fill engine (TASK-6.5).

Pure, dependency-free parser that extracts the load metadata a dispatcher or
owner needs straight off a Rate Confirmation text/PDF payload:

* Broker / Shipper Name
* Rate ($ Payout, from Linehaul + Total pay figures)
* Pickup Location & Date
* Delivery Location & Date
* Commodity / Weight / Reference #

Everything parsed here is only *staged* for the Load Creation form — no
database write ever happens inside this module. The caller must pass the
data through the Human-in-the-Loop (HITL) authorization guardrail in
``services.create_authorized_load`` before it is committed.
"""

import re
from datetime import datetime
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Regex extractors (mirror the FreightSlip plugin grammar, plus richer geo and
# party fields needed by the auto-fill engine).
# ---------------------------------------------------------------------------
BROKER_PATTERN = re.compile(
    r"(?i)\bbroker\b\s*[:#]\s*([A-Za-z][^\r\n]*?)\s*(?:[\r\n]|$)"
)
SHIPPER_PATTERN = re.compile(
    r"(?i)\bshipper\b\s*[:#]\s*([A-Za-z][^\r\n]*?)\s*(?:[\r\n]|$)"
)
LOAD_NUMBER_PATTERN = re.compile(
    r"(?i)\bload\s*(?:#|number|ne\.?)?\s*[:#]\s*([A-Za-z0-9][A-Za-z0-9\-_/]*)"
)
WEIGHT_PATTERN = re.compile(r"(?i)\bweight\b\s*[:#]\s*([\d,]+)")
COMMODITY_PATTERN = re.compile(
    r"(?i)\bcommodity\b\s*[:#]\s*([A-Za-z][^\r\n]*?)\s*(\r|\n|$)"
)
PICKUP_REF_PATTERN = re.compile(
    r"(?i)\bpickup\s*(?:ref(?:erence)?)?\s*[:#]\s*([A-Za-z0-9][A-Za-z0-9\-_/]*)"
)
DELIVERY_REF_PATTERN = re.compile(
    r"(?i)\bdelivery\s*ref(?:erence)?\s*[:#]\s*([A-Za-z0-9][A-Za-z0-9\-_/]*)"
)
DELIVERY_REF_VARIANT = re.compile(
    r"(?i)\bdeliver\s*ref(?:erence)?\s*[:#]\s*([A-Za-z0-9][A-Za-z0-9\-_/]*)"
)
LINEHAUL_PATTERN = re.compile(
    r"(?i)\bline\s*haul(?:[_ ]?rate)?\s*[:#]\s*\$?\s*([\d,]+\.?\d*)"
)
TOTAL_PAY_PATTERN = re.compile(
    r"(?i)\btotal\s*pay(?:out|ment)?\s*[:#]\s*\$?\s*([\d,]+\.?\d*)"
)

PICKUP_LOCATION_PATTERN = re.compile(
    r"(?i)\bpickup\s+(?:location|addr(?:ess)?|city|origin)\b\s*[:#]\s*([^\r\n]+)"
)
PICKUP_DATE_PATTERN = re.compile(
    r"(?i)\bpickup\s+(?:date|dt)\b\s*[:#]\s*([0-9]{2}/[0-9]{2}/[0-9]{4})"
)
DELIVERY_LOCATION_PATTERN = re.compile(
    r"(?i)\bdeliver(?:y)?\s+(?:location|addr(?:ess)?|city|dest(?:ination)?)\b\s*[:#]\s*([^\r\n]+)"
)
DELIVERY_DATE_PATTERN = re.compile(
    r"(?i)\bdeliver(?:y)?\s+(?:date|dt)\b\s*[:#]\s*([0-9]{2}/[0-9]{2}/[0-9]{4})"
)

# Target times are fed to the Load Creation form in the classic Streamlit
# text format used by dispatch_panel._parse_target_time.
FORM_TIME_FORMAT = "%m/%d/%Y %I:%M %p"


class RateConfirmationParseError(ValueError):
    """Raised when no usable freight dispatch data is found in a payload."""


def _decode_utf8(raw: bytes) -> str:
    """Best-effort UTF-8 decoding with a Latin-1 fallback for PDF text layers."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


def _strip(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip().rstrip(",#:").strip()
    return cleaned or None


def parse_rate_reconfirmation_text(text: str) -> Dict[str, Any]:
    """Parse a rate-confirmation text blob into structured load metadata.

    Returns a flat dict with the keys the Load Creation form consumes:
    ``broker_name``, ``shipper_name``, ``load_number``, ``load_weight``,
    ``commodity``, ``pickup_ref``, ``delivery_ref``, ``pickup_location``,
    ``pickup_date``, ``delivery_location``, ``delivery_date``,
    ``linehaul_rate``, ``total_pay`` and ``payout``.
    """
    if not text:
        raise RateConfirmationParseError(
            "Unable to parse the uploaded file as a Rate Confirmation."
        )

    data: Dict[str, Any] = {}

    broker_m = BROKER_PATTERN.search(text)
    if broker_m:
        data["broker_name"] = _strip(broker_m.group(1))

    shipper_m = SHIPPER_PATTERN.search(text)
    if shipper_m:
        data["shipper_name"] = _strip(shipper_m.group(1))

    load_m = LOAD_NUMBER_PATTERN.search(text)
    if load_m:
        data["load_number"] = _strip(load_m.group(1))

    weight_m = WEIGHT_PATTERN.search(text)
    if weight_m:
        data["load_weight"] = int(weight_m.group(1).replace(",", ""))

    commodity_m = COMMODITY_PATTERN.search(text)
    if commodity_m:
        data["commodity"] = _strip(commodity_m.group(1))

    pickup_ref_m = PICKUP_REF_PATTERN.search(text)
    if pickup_ref_m:
        data["pickup_ref"] = _strip(pickup_ref_m.group(1))

    delivery_ref_m = DELIVERY_REF_PATTERN.search(text) or DELIVERY_REF_VARIANT.search(text)
    if delivery_ref_m:
        data["delivery_ref"] = _strip(delivery_ref_m.group(1))

    pickup_loc_m = PICKUP_LOCATION_PATTERN.search(text)
    if pickup_loc_m:
        data["pickup_location"] = _strip(pickup_loc_m.group(1))

    pickup_date_m = PICKUP_DATE_PATTERN.search(text)
    if pickup_date_m:
        data["pickup_date"] = _strip(pickup_date_m.group(1))

    delivery_loc_m = DELIVERY_LOCATION_PATTERN.search(text)
    if delivery_loc_m:
        data["delivery_location"] = _strip(delivery_loc_m.group(1))

    delivery_date_m = DELIVERY_DATE_PATTERN.search(text)
    if delivery_date_m:
        data["delivery_date"] = _strip(delivery_date_m.group(1))

    linehaul_m = LINEHAUL_PATTERN.search(text)
    if linehaul_m:
        data["linehaul_rate"] = float(linehaul_m.group(1).replace(",", ""))

    total_m = TOTAL_PAY_PATTERN.search(text)
    if total_m:
        data["total_pay"] = float(total_m.group(1).replace(",", ""))

    # A "payout" for the dispatcher summary = the money to the carrier.
    data["payout"] = data.get("total_pay") or data.get("linehaul_rate")

    if not any(
        k in data
        for k in ("load_number", "load_weight", "commodity", "pickup_ref", "delivery_ref")
    ):
        raise RateConfirmationParseError(
            "Unable to parse the uploaded file as a Rate Confirmation."
        )
    data["provider"] = "ratecon_ocr"
    return data


def parse_rate_confirmation_bytes(raw: bytes) -> Dict[str, Any]:
    """Parse a PDF/.txt payload (raw bytes) into load metadata.

    Backed by the FreightSlip grammar extractors above; the caller feeds the
    same bytes that ``st.file_uploader`` returns (``.getvalue()``).
    """
    text = _decode_utf8(raw)
    return parse_rate_reconfirmation_text(text)


def date_to_form_time(date_str: Optional[str], hour: int = 8, minute: int = 0) -> str:
    """Convert a ``MM/DD/YYYY`` date into the form's time-column string."""
    if not date_str:
        return ""
    try:
        parsed = datetime.strptime(date_str.strip(), "%m/%d/%Y")
    except ValueError:
        return date_str
    return parsed.replace(hour=hour, minute=minute).strftime(FORM_TIME_FORMAT)


def ratecon_to_form(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Auto-fill mapping: parsed metadata -> dispatch form field defaults."""
    return {
        "load_number": parsed.get("load_number") or "",
        "load_weight": parsed.get("load_weight"),
        "commodity": parsed.get("commodity") or "",
        "pickup_ref": parsed.get("pickup_ref") or "",
        "delivery_ref": parsed.get("delivery_ref") or "",
        "pickup_address": parsed.get("pickup_location") or "",
        "delivery_address": parsed.get("delivery_location") or "",
        "target_pickup_at": date_to_form_time(parsed.get("pickup_date"), 8, 0),
        "target_delivery_at": date_to_form_time(parsed.get("delivery_date"), 17, 0),
        "dispatcher_notes": _build_dispatch_notes(parsed),
        "broker_name": parsed.get("broker_name") or parsed.get("shipper_name") or "",
    }


def _build_dispatch_notes(parsed: Dict[str, Any]) -> str:
    """Fold Broker + payout summary into the dispatcher notes (no DB column)."""
    bits = []
    broker = parsed.get("broker_name") or parsed.get("shipper_name")
    if broker:
        bits.append(f"FreightSlip Broker: {broker}")
    payout = parsed.get("payout")
    if payout is not None:
        bits.append(f"Payout: ${payout:,.2f}")
    return " · ".join(bits) if bits else ""