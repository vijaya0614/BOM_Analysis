"""Industry vs demo identity helpers and documented spec-parameter aliases.

Industry identity chain:

    original_mpn
    → normalize_mpn()
    → component_models.normalized_mpn
    → component_model_id (mdl_*)
    → engineering evidence tables

Demo catalog identity (data/component_specs.csv) uses component_id / part_number
and must never be consulted as a fallback for an industry BOM reference such as U2.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Set

from src.industry_data.csv_store import find_model_by_mpn, read_csv
from src.industry_data.mpn_resolver import normalize_mpn

INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
INDUSTRY_MODEL_PREFIX = "mdl_"

# Datasheet names observed on real PMIC rows → names already consumed by
# compatibility_rules and the orchestrator catalog-fallback gates.
# Only aliases that mean the same electrical quantity are listed.
PARAMETER_ALIASES: Dict[str, tuple[str, ...]] = {
    "input_voltage_min_v": ("supply_voltage_min_v",),
    "input_voltage_max_v": ("supply_voltage_max_v",),
}

_SYNTHETIC_OPERATING_MARKERS = {
    "SYNTHETIC_DEMO_OPERATING_VALUE",
    "SENTINEL_ENGINEERING_LAYER_DEMO_FIXTURE",
    "SYNTHETIC_CATALOG_LIMIT_PLUS_SYNTHETIC_DEMO_OPERATING_VALUE",
    "MANUFACTURER_LIMIT_PLUS_SYNTHETIC_DEMO_OPERATING_VALUE",
}


def is_industry_model_id(value: Any) -> bool:
    text = str(value or "").strip()
    return text.lower().startswith(INDUSTRY_MODEL_PREFIX)


def is_industry_product(product_id: str) -> bool:
    wanted = str(product_id or "").strip()
    if not wanted:
        return False
    return any(row.get("product_id") == wanted for row in read_csv("products.csv"))


def is_industry_mpn(mpn: str) -> bool:
    normalized = normalize_mpn(mpn)
    if not normalized:
        return False
    return find_model_by_mpn(normalized) is not None


def evidence_join_keys(component: Any) -> Set[str]:
    """Uppercased keys that may appear on an evidence row for this component."""
    keys: Set[str] = set()
    for value in (
        getattr(component, "component_id", ""),
        getattr(component, "part_number", ""),
        normalize_mpn(getattr(component, "part_number", "") or ""),
    ):
        text = str(value or "").strip().upper()
        if text:
            keys.add(text)
    return keys


def row_join_keys(row: Dict[str, str]) -> Set[str]:
    keys: Set[str] = set()
    for field in ("component_model_id", "normalized_mpn"):
        text = str(row.get(field) or "").strip().upper()
        if text:
            keys.add(text)
    return keys


def evidence_row_matches(component: Any, row: Dict[str, str]) -> bool:
    return bool(evidence_join_keys(component) & row_join_keys(row))


def operating_value_is_synthetic(row: Dict[str, str]) -> bool:
    markers = " ".join(
        str(row.get(name) or "")
        for name in ("provenance", "source_type", "source", "condition")
    ).upper()
    return any(marker in markers for marker in _SYNTHETIC_OPERATING_MARKERS)


def apply_parameter_aliases(specs: Dict[str, Any]) -> Dict[str, Any]:
    """Copy documented aliases without overwriting a source parameter that already exists.

    Alias map (identical electrical quantity only):

        input_voltage_min_v → supply_voltage_min_v
        input_voltage_max_v → supply_voltage_max_v

    Range metadata under ``_ranges`` is copied with the same names.
    """
    out = dict(specs)
    ranges = dict(out.get("_ranges") or {})
    for source_name, aliases in PARAMETER_ALIASES.items():
        if source_name not in out and source_name not in ranges:
            continue
        for alias in aliases:
            if source_name in out and alias not in out:
                out[alias] = out[source_name]
            if source_name in ranges and alias not in ranges:
                ranges[alias] = ranges[source_name]
    if ranges:
        out["_ranges"] = ranges
    return out


def scalar_from_eav(row: Dict[str, str]) -> str:
    """Choose the documented scalar for a named parameter without inventing a midpoint."""
    name = str(row.get("parameter_name") or "").strip().lower()
    nominal = str(row.get("nominal_value") or "").strip()
    minimum = str(row.get("min_value") or "").strip()
    maximum = str(row.get("max_value") or "").strip()
    if name.endswith("_min") or name.endswith("_min_v") or name.endswith("_min_c") or name.endswith("_min_a"):
        return minimum or nominal
    if name.endswith("_max") or name.endswith("_max_v") or name.endswith("_max_c") or name.endswith("_max_a"):
        return maximum or nominal
    return nominal or minimum or maximum


def eav_range(row: Dict[str, str]) -> Dict[str, str]:
    return {
        "nominal": str(row.get("nominal_value") or "").strip(),
        "min": str(row.get("min_value") or "").strip(),
        "max": str(row.get("max_value") or "").strip(),
        "unit": str(row.get("unit") or "").strip(),
        "provenance": str(row.get("provenance") or "").strip(),
        "source_document": str(row.get("source_document") or "").strip(),
        "source_page": str(row.get("source_page") or "").strip(),
        "confidence": str(row.get("confidence") or "").strip(),
        "parameter_name": str(row.get("parameter_name") or "").strip(),
    }


def demo_fixture_id(value: str) -> bool:
    text = str(value or "").strip().upper()
    return text.startswith("REG_") or text.startswith("RES_") or text.startswith("CAP_")
