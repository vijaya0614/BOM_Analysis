import csv
import json
import os
from typing import Dict, List, Optional

from src.models import ComponentSpec, PartRiskProfile
from src.risk_engine import compute_risk
from src.risk_merger import merge_risk_data


DEFAULT_CATALOG_PATH = os.path.join("data", "component_specs.csv")


def _parse_bool(value: str) -> Optional[bool]:
    if value == "":
        return None
    return value.strip().lower() in ("true", "1", "yes", "y")


def _parse_int(value: str) -> Optional[int]:
    if value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def load_component_catalog(catalog_path: str = DEFAULT_CATALOG_PATH) -> Dict[str, ComponentSpec]:
    """Loads demo/catalog component specifications keyed by stable component_id."""
    if not os.path.exists(catalog_path):
        return {}

    catalog: Dict[str, ComponentSpec] = {}
    with open(catalog_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            specs = json.loads(row.get("specs_json") or "{}")
            component = ComponentSpec(
                component_id=row["component_id"].strip(),
                part_number=row["part_number"].strip(),
                manufacturer=(row.get("manufacturer") or "").strip() or None,
                refdes=(row.get("refdes") or "").strip() or None,
                category=(row.get("category") or "generic").strip().lower(),
                package=(row.get("package") or "").strip() or None,
                lifecycle_status=(row.get("lifecycle_status") or "").strip() or None,
                lead_time_weeks=_parse_int(row.get("lead_time_weeks") or ""),
                stock=_parse_int(row.get("stock") or ""),
                has_second_source=_parse_bool(row.get("has_second_source") or ""),
                criticality=(row.get("criticality") or "").strip() or None,
                physical_location=(row.get("physical_location") or "").strip() or None,
                specs=specs,
                demo_data=_parse_bool(row.get("demo_data") or "") is True,
            )
            catalog[component.component_id] = component
    return catalog


def find_component(
    identifier: str,
    catalog_path: str = DEFAULT_CATALOG_PATH,
    *,
    match_refdes: bool = True,
) -> Optional[ComponentSpec]:
    """Finds a component by component_id or part number.

    Refdes matching is opt-in for the demo catalog. Industry sessions must never
    resolve a board reference such as U2 through this catalog.
    """
    ident = identifier.strip().lower()
    for component in load_component_catalog(catalog_path).values():
        aliases = {component.component_id.lower(), component.part_number.lower()}
        if match_refdes and component.refdes:
            aliases.add(component.refdes.lower())
        if ident in aliases:
            return component
    return None


def candidates_for(original: ComponentSpec, catalog_path: str = DEFAULT_CATALOG_PATH) -> List[ComponentSpec]:
    """Retrieves catalog candidates in the same category, excluding the original part."""
    return [
        c
        for c in load_component_catalog(catalog_path).values()
        if c.category == original.category and c.component_id != original.component_id
    ]


def build_risk_profile(component: ComponentSpec, data_dir: str = "data") -> PartRiskProfile:
    """
    Converts a component catalog item into Person 1's risk profile and reuses
    the existing merger/scoring rules when supply-chain fields are missing.
    """
    profile = PartRiskProfile(
        part_number=component.part_number,
        references=[component.refdes] if component.refdes else [],
        raw_reference_str=component.refdes or "",
        qty=1,
        lifecycle_status=component.lifecycle_status,
        lead_time_weeks=component.lead_time_weeks,
        stock=component.stock,
        has_second_source=component.has_second_source,
        criticality=component.criticality,
    )

    # Real distributor/lifecycle evidence is an overlay, not a synthetic
    # replacement.  Apply it before the legacy fallback so live enrichment can
    # affect scoring whenever the catalog does not already provide a value.
    from src.industry_data.catalog_adapter import apply_industry_to_profile

    profile = apply_industry_to_profile(profile)

    if any(
        value is None
        for value in [
            profile.lifecycle_status,
            profile.lead_time_weeks,
            profile.stock,
            profile.has_second_source,
            profile.criticality,
        ]
    ):
        profile = merge_risk_data([profile], data_dir)[0]

    return compute_risk(profile)
