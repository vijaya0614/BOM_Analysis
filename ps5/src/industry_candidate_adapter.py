"""Adapt normalized industry components into :class:`ComponentSpec` objects.

This module deliberately exposes only fields present in the normalized CSVs.
Absent technical parameters are not represented as guessed values; the empty
industry ``component_specs.csv`` therefore remains visible to compatibility
checks as unknown evidence.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.industry_data.csv_store import read_csv
from src.industry_data.identity import apply_parameter_aliases, eav_range, scalar_from_eav
from src.models import ComponentSpec

INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


def _clean(value: object) -> str:
    return str(value or "").strip()


def _specs_by_model() -> Dict[str, Dict[str, Any]]:
    specs: Dict[str, Dict[str, Any]] = {}
    ranges: Dict[str, Dict[str, Dict[str, str]]] = {}
    for row in read_csv("component_specs.csv"):
        model_id = _clean(row.get("component_model_id"))
        parameter = _clean(row.get("parameter_name"))
        if not model_id or not parameter:
            continue
        scalar = scalar_from_eav(row)
        if scalar:
            specs.setdefault(model_id, {})[parameter] = scalar
        ranges.setdefault(model_id, {})[parameter] = eav_range(row)
    for model_id, payload in specs.items():
        payload["_ranges"] = ranges.get(model_id, {})
        specs[model_id] = apply_parameter_aliases(payload)
    return specs


def component_from_model_row(
    row: Dict[str, str],
    *,
    category: Optional[str] = None,
    refdes: Optional[str] = None,
) -> ComponentSpec:
    """Convert a normalized model row using the evidence-adapter missing-data convention."""
    model_id = _clean(row.get("component_model_id"))
    mpn = _clean(row.get("normalized_mpn")) or _clean(row.get("mpn"))
    if not model_id or not mpn:
        raise ValueError("Industry candidate adapter requires component_model_id and exact MPN.")
    return ComponentSpec(
        component_id=model_id,
        part_number=mpn,
        manufacturer=_clean(row.get("manufacturer")) or INSUFFICIENT_DATA,
        refdes=refdes,
        category=(category or _clean(row.get("component_category")) or "generic").lower(),
        package=_clean(row.get("package")) or INSUFFICIENT_DATA,
        # ``UNKNOWN`` is the lifecycle value actually present in the
        # normalized model; a blank remains explicitly insufficient rather
        # than being promoted to an Active/NRND/EOL conclusion.
        lifecycle_status=_clean(row.get("lifecycle_status")) or INSUFFICIENT_DATA,
        lead_time_weeks=None,
        stock=None,
        has_second_source=None,
        criticality=None,
        specs=_specs_by_model().get(model_id, {}),
    )


def _model_rows() -> Dict[str, Dict[str, str]]:
    return {row["component_model_id"]: row for row in read_csv("component_models.csv") if _clean(row.get("component_model_id"))}


def resolve_industry_model(component_model_id: str) -> Optional[ComponentSpec]:
    """Resolve a normalized model id when a BOM reference is not available."""
    model = _model_rows().get(_clean(component_model_id))
    return component_from_model_row(model) if model is not None else None


def _component_category(component_type_id: str, model_row: Dict[str, str]) -> str:
    types = {row["component_type_id"]: row for row in read_csv("component_types.csv")}
    return (_clean(types.get(component_type_id, {}).get("component_class")) or _clean(model_row.get("component_category")) or "generic").lower()


def _select_bom_row(product_id: str, reference_designator: str) -> Optional[Dict[str, str]]:
    rows = [
        row for row in read_csv("bom_lines.csv")
        if _clean(row.get("product_id")) == product_id and _clean(row.get("reference_designator")) == reference_designator
    ]
    if not rows:
        return None
    models = _model_rows()
    # Prefer an explicit regulator BOM type for a PMIC when duplicate importer
    # rows exist; it keeps the documented component type aligned with the
    # real-alternate pool rather than treating a PMIC as a processor.
    rows.sort(
        key=lambda row: (
            "PMIC" not in _clean(models.get(_clean(row.get("component_model_id")), {}).get("description")).upper(),
            not _clean(models.get(_clean(row.get("component_model_id")), {}).get("package")),
            _clean(row.get("component_type_id")) != "type_regulator",
            _clean(row.get("bom_line_id")),
        )
    )
    return rows[0]


def resolve_industry_component(product_id: str, reference_designator: str) -> Optional[ComponentSpec]:
    """Resolve a BOM-local reference designator to its normalized model."""
    bom_row = _select_bom_row(product_id, reference_designator)
    if bom_row is None:
        return None
    model = _model_rows().get(_clean(bom_row.get("component_model_id")))
    if model is None:
        return None
    category = _component_category(_clean(bom_row.get("component_type_id")), model)
    # Some imported revisions contain a package-bearing PMIC model plus a
    # regulator-typed ordering variant under the same reference.  Both facts
    # are present in bom_lines.csv; prefer the explicit regulator type for
    # compatibility-rule selection without generating any missing spec value.
    duplicate_rows = [
        row for row in read_csv("bom_lines.csv")
        if _clean(row.get("product_id")) == product_id and _clean(row.get("reference_designator")) == reference_designator
    ]
    if "PMIC" in _clean(model.get("description")).upper():
        regulator_row = next((row for row in duplicate_rows if _clean(row.get("component_type_id")) == "type_regulator"), None)
        if regulator_row is not None:
            category = _component_category("type_regulator", model)
    return component_from_model_row(
        model,
        category=category,
        refdes=reference_designator,
    )


def _tokens(row: Dict[str, str]) -> set[str]:
    # Category is intentionally excluded: broad categories such as
    # ``TRANSCEIVER`` must not make an Ethernet transformer look like a PHY.
    text = " ".join(_clean(row.get(name)).upper() for name in ("description", "mpn"))
    tokens = set()
    if "PMIC" in text:
        tokens.add("PMIC")
    if "AM335" in text:
        tokens.add("AM335")
    if "HDMI" in text and "TRANSMITTER" in text:
        tokens.add("HDMI_TRANSMITTER")
    if "DDR" in text:
        tokens.add("DDR")
    if "EMMC" in text:
        tokens.add("EMMC")
    if "ETHERNET" in text and ("TRANSCEIVER" in text or "PHY" in text):
        tokens.add("ETHERNET_PHY")
    return tokens


def industry_candidates_for(original: ComponentSpec) -> List[ComponentSpec]:
    """Return real normalized alternates with conservative category/package evidence.

    A same-category model is the initial pool.  A shared explicit function
    token (for example PMIC, HDMI, DDR, eMMC, or Ethernet PHY) is required
    when the source model exposes one, so importer catch-all categories such
    as ``ETC`` never become a catalogue-wide candidate set.  If package data
    is available on both sides, same-package candidates are preferred without
    making package a hard requirement when it would leave no candidates.
    No electrical compatibility is inferred here.
    """
    rows = list(_model_rows().values())
    original_row = next((row for row in rows if (_clean(row.get("normalized_mpn")) or _clean(row.get("mpn"))) == original.part_number), None)
    original_tokens = _tokens(original_row or {})
    eligible = []
    for row in rows:
        candidate_mpn = _clean(row.get("normalized_mpn")) or _clean(row.get("mpn"))
        if not candidate_mpn or candidate_mpn == original.part_number:
            continue
        same_category = _clean(row.get("component_category")).lower() == original.category
        related_function = bool(original_tokens & _tokens(row))
        if not same_category:
            continue
        eligible.append((row, related_function))

    # A function-qualified pool is necessary whenever the source calls out a
    # function.  Falling back to the entire category would turn "ETC" or
    # "MEMORY" into an unsupported claim of interchangeability.
    if original_tokens:
        eligible = [(row, related) for row, related in eligible if related]

    if original.package != INSUFFICIENT_DATA:
        package_matches = [
            (row, related)
            for row, related in eligible
            if _clean(row.get("package")) == original.package
        ]
        if package_matches:
            eligible = package_matches

    # Give compatibility_rules a like-for-like comparison category only after
    # this explicit normalized-data eligibility check.
    candidates = [component_from_model_row(row, category=original.category) for row, _ in eligible]
    candidates.sort(key=lambda item: (item.package != original.package, item.part_number))
    return candidates


def resolve_industry_candidate(product_id: str, reference_designator: str, candidate_id: str) -> Optional[ComponentSpec]:
    original = resolve_industry_component(product_id, reference_designator)
    if original is None:
        return None
    requested = _clean(candidate_id).lower()
    return next(
        (candidate for candidate in industry_candidates_for(original) if requested in {candidate.component_id.lower(), candidate.part_number.lower()}),
        None,
    )
