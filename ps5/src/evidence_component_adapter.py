"""Adapter from evidence CSV rows to the application's ComponentSpec contract.

Technical fields are retained verbatim. Supply/risk fields stay ``None`` rather
than being generated when the evidence source does not provide them.
"""
import csv
from typing import Any, Dict

from src.models import ComponentSpec

INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


def adapt_evidence_row(row: Dict[str, str], component_id: str) -> ComponentSpec:
    mpn = (row.get("mpn") or "").strip()
    if not component_id or not mpn:
        raise ValueError("Evidence adapter requires a stable component_id and an exact MPN.")
    technical = {key: (value.strip() if isinstance(value, str) and value.strip() else INSUFFICIENT_DATA) for key, value in row.items() if key not in {"mpn", "manufacturer", "component_type", "description", "package"}}
    return ComponentSpec(
        component_id=component_id,
        part_number=mpn,
        manufacturer=(row.get("manufacturer") or INSUFFICIENT_DATA).strip(),
        category=(row.get("component_type") or "generic").strip().lower(),
        package=(row.get("package") or INSUFFICIENT_DATA).strip(),
        specs={"description": (row.get("description") or INSUFFICIENT_DATA).strip(), **technical},
        lifecycle_status=None, lead_time_weeks=None, stock=None, has_second_source=None, criticality=None,
    )


def load_evidence_components(path: str, component_ids_by_mpn: Dict[str, str]) -> Dict[str, ComponentSpec]:
    with open(path, encoding="utf-8-sig", newline="") as source:
        rows = csv.DictReader(source)
        return {component_ids_by_mpn[row["mpn"].upper()]: adapt_evidence_row(row, component_ids_by_mpn[row["mpn"].upper()]) for row in rows if row.get("mpn", "").upper() in component_ids_by_mpn}
