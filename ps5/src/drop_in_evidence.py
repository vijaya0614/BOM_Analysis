"""Evidence gates for claims that a candidate is a drop-in replacement."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


_ROOT = Path(__file__).resolve().parents[1]
_EVIDENCE_FILE = _ROOT / "data" / "evidence_sources.csv"
_RATING_WORDS = {
    "voltage": ("voltage", "vds", "vce", "vgs"),
    "current": ("current", "id_a", "ic", "output_current"),
    "power": ("power", "watt"),
    "temperature": ("temperature", "junction_temp"),
    "resistance": ("resistance", "rds_on"),
    "capacitance": ("capacitance",),
    "accuracy": ("accuracy",),
}
_PACKAGE_WORDS = ("package", "footprint", "land pattern", "case style")
_PINOUT_WORDS = ("pinout", "pin assignment", "pin mapping", "terminal assignment", "pin function")
_BAD_PROVENANCE = ("synthetic", "fixture", "inferred", "generated", "demo")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _has_locator(record: Dict[str, Any]) -> bool:
    has_identity = bool(_text(record.get("source_id") or record.get("source_title") or record.get("source_document")))
    has_location = bool(_text(record.get("source_url") or record.get("url"))) or bool(
        _text(record.get("source_document")) and _text(record.get("source_page"))
    )
    confidence = _text(record.get("confidence")).upper()
    provenance = " ".join(
        _text(record.get(key))
        for key in ("source_type", "evidence_quality", "provenance", "data_provenance", "notes")
    ).lower()
    return has_identity and has_location and confidence in {"HIGH", "MEDIUM"} and not any(
        marker in provenance for marker in _BAD_PROVENANCE
    )


def _read_exact_mpn_evidence(mpn: str) -> List[Dict[str, str]]:
    if not _EVIDENCE_FILE.is_file():
        return []
    with _EVIDENCE_FILE.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            row for row in csv.DictReader(handle)
            if _text(row.get("mpn")).upper() == _text(mpn).upper()
        ]


def _contains_any(text: str, words: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in words)


def _value_is_cited(value: Any, record: Dict[str, Any]) -> bool:
    cited_text = " ".join(
        _text(record.get(key))
        for key in ("nominal", "min", "max", "evidence_summary", "parameter_supported")
    ).lower()
    if not cited_text:
        return False
    value_text = _text(value).lower()
    if value_text and value_text in cited_text:
        return True
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    options = {str(numeric), f"{numeric:g}"}
    if numeric.is_integer():
        options.add(str(int(numeric)))
    return any(re.search(rf"(?<![a-z0-9.]){re.escape(option)}(?![a-z0-9.])", cited_text) for option in options)


def _component_evidence(component: Any, field: str, rating_parameter: Optional[str] = None) -> Optional[Dict[str, Any]]:
    spec_field = rating_parameter or field
    value = component.get_spec(spec_field) if field != "package" else getattr(component, "package", None)
    if value in (None, "", "UNKNOWN", "INSUFFICIENT_DATA"):
        return None
    if getattr(component, "demo_data", False):
        return None

    ranges = (getattr(component, "specs", {}) or {}).get("_ranges", {}) or {}
    aliases = [rating_parameter or field]
    if rating_parameter:
        aliases.extend(
            key for key, words in _RATING_WORDS.items()
            if _contains_any(rating_parameter, words)
        )
    for key in aliases:
        record = ranges.get(key)
        if record and _has_locator(record) and _value_is_cited(value, record):
            return {
                "source_id": record.get("source_id") or record.get("source_document"),
                "source_document": record.get("source_document"),
                "source_page": record.get("source_page"),
                "source_url": record.get("source_url"),
                "confidence": record.get("confidence"),
                "provenance": record.get("provenance"),
                "supported_value": record.get("nominal") or record.get("min") or record.get("max"),
            }

    words: Iterable[str]
    if field == "package":
        words = _PACKAGE_WORDS
    elif field == "pinout":
        words = _PINOUT_WORDS
    else:
        parameter_name = _text(rating_parameter or field).lower()
        words = next(
            (tokens for key, tokens in _RATING_WORDS.items() if key in parameter_name or _contains_any(parameter_name, tokens)),
            (parameter_name,),
        )

    for row in _read_exact_mpn_evidence(getattr(component, "part_number", "")):
        supported = " ".join((_text(row.get("parameter_supported")), _text(row.get("evidence_summary"))))
        if _contains_any(supported, words) and _has_locator(row) and _value_is_cited(value, row):
            return {
                "source_id": row.get("source_id"),
                "source_title": row.get("source_title"),
                "source_url": row.get("source_url"),
                "source_page": row.get("source_page"),
                "confidence": row.get("confidence"),
                "parameter_supported": row.get("parameter_supported"),
                "evidence_summary": row.get("evidence_summary"),
            }
    return None


def _payload_evidence(spec: Dict[str, Any], field: str, rating_parameter: Optional[str] = None) -> Optional[Dict[str, Any]]:
    evidence = spec.get("evidence") or spec.get("technical_evidence") or {}
    record = evidence.get(field)
    if field == "rating" and rating_parameter:
        ratings = evidence.get("ratings") or {}
        normalized = re.sub(r"[^a-z0-9]+", "_", rating_parameter.lower()).strip("_")
        record = ratings.get(rating_parameter) or ratings.get(normalized) or ratings.get("default")
    if not isinstance(record, dict) or not _has_locator(record):
        return None
    value = _payload_rating_value(spec, rating_parameter or "") if field == "rating" else spec.get(field)
    if not _value_is_cited(value, record):
        return None
    return {
        key: record.get(key)
        for key in ("source_id", "source_title", "source_document", "source_url", "url", "source_page", "confidence")
        if record.get(key)
    }


def _payload_rating_value(spec: Dict[str, Any], parameter: str) -> Any:
    specs = spec.get("specs") or {}
    aliases = [parameter]
    name = parameter.lower()
    if "voltage" in name:
        aliases.extend(("rated_voltage", "voltage_rating_v", "operating_voltage_max"))
    if "current" in name:
        aliases.extend(("rated_current", "current_rating_a", "operating_current_max"))
    if "temperature" in name:
        aliases.extend(("operating_temperature_max", "temperature_rating_c"))
    if "power" in name:
        aliases.extend(("power_rating", "power_rating_w", "power_w"))
    if "resistance" in name:
        aliases.extend(("rds_on_mohm", "resistance_rating"))
    for alias in aliases:
        value = specs.get(alias, spec.get(alias))
        if value not in (None, ""):
            return value
    return None


def _rating_parameters(parameters: Iterable[str]) -> List[str]:
    selected = []
    for parameter in parameters:
        name = _text(parameter).lower()
        if any(_contains_any(name, words) for words in _RATING_WORDS.values()):
            selected.append(_text(parameter))
    return list(dict.fromkeys(selected)) or ["applicable_electrical_rating"]


def _requirement(
    parameter: str,
    field: str,
    original: Any,
    candidate: Any,
    *,
    rating_parameter: Optional[str] = None,
    payload: bool = False,
) -> Dict[str, Any]:
    if payload:
        original_value = _payload_rating_value(original, parameter) if field == "rating" else original.get(parameter)
        candidate_value = _payload_rating_value(candidate, parameter) if field == "rating" else candidate.get(parameter)
        original_ref = _payload_evidence(original, field, rating_parameter)
        candidate_ref = _payload_evidence(candidate, field, rating_parameter)
    else:
        original_value = getattr(original, "package", None) if field == "package" else original.get_spec(rating_parameter or field)
        candidate_value = getattr(candidate, "package", None) if field == "package" else candidate.get_spec(rating_parameter or field)
        original_ref = _component_evidence(original, field, rating_parameter)
        candidate_ref = _component_evidence(candidate, field, rating_parameter)

    def side(value: Any, ref: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "value": value if value not in (None, "") else "INSUFFICIENT_DATA",
            "status": "SUPPORTED" if value not in (None, "") and ref else "INSUFFICIENT_DATA",
            "source": ref,
        }

    return {
        "parameter": parameter,
        "original": side(original_value, original_ref),
        "candidate": side(candidate_value, candidate_ref),
        "status": "SUPPORTED" if original_ref and candidate_ref and original_value not in (None, "") and candidate_value not in (None, "") else "INSUFFICIENT_DATA",
    }


def assess_component_drop_in_evidence(original: Any, candidate: Any, checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Require exact-MPN source-backed package, pinout and comparison ratings."""
    requirements = [
        _requirement("package", "package", original, candidate),
        _requirement("pinout", "pinout", original, candidate),
    ]
    for parameter in _rating_parameters(check.get("parameter", "") for check in checks):
        requirements.append(
            _requirement(parameter, "rating", original, candidate, rating_parameter=parameter)
        )
    return _assessment(requirements)


def assess_payload_drop_in_evidence(original: Dict[str, Any], candidate: Dict[str, Any], rating_parameters: Iterable[str]) -> Dict[str, Any]:
    requirements = [
        _requirement("package", "package", original, candidate, payload=True),
        _requirement("pinout", "pinout", original, candidate, payload=True),
    ]
    for parameter in _rating_parameters(rating_parameters):
        requirements.append(
            _requirement(parameter, "rating", original, candidate, rating_parameter=parameter, payload=True)
        )
    return _assessment(requirements)


def _assessment(requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
    missing = [item["parameter"] for item in requirements if item["status"] != "SUPPORTED"]
    return {
        "status": "SUPPORTED" if not missing else "INSUFFICIENT_DATA",
        "requirements": requirements,
        "unknown_parameters": missing,
        "limitations": [] if not missing else [
            "Drop-in status is withheld until package, pinout, and applicable rating values for both parts have traceable source references."
        ],
    }
