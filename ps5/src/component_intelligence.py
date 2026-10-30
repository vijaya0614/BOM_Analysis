import csv
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from src.component_catalog import find_component
from src.dependency_graph import load_component_graph, scopes_for_component, traverse_downstream


INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
CLASS_LEVEL_EVIDENCE = "CLASS_LEVEL_EVIDENCE"

RELIABILITY_CATALOG_PATH = os.path.join("data", "component_specs_reliability.csv")
EVIDENCE_PATH = os.path.join("data", "evidence_sources.csv")
RELIABILITY_PATH = os.path.join("data", "reliability_data.csv")
DEGRADATION_PATH = os.path.join("data", "degradation_profiles.csv")


PROFILE_FIELD_MAP = {
    "nominal_value": ("Nominal value", "nominal_unit"),
    "tolerance": ("Tolerance", "tolerance_unit"),
    "operating_voltage_min": ("Operating voltage min", "voltage_unit"),
    "operating_voltage_max": ("Operating voltage max", "voltage_unit"),
    "rated_voltage": ("Rated voltage", "voltage_unit"),
    "operating_current_min": ("Operating current min", "current_unit"),
    "operating_current_max": ("Operating current max", "current_unit"),
    "rated_current": ("Rated current", "current_unit"),
    "operating_temperature_min": ("Operating temperature min", None),
    "operating_temperature_max": ("Operating temperature max", None),
    "power_rating": ("Power rating", "power_unit"),
}

OPERATING_PROFILE_FIELDS = [
    field_name for field_name in PROFILE_FIELD_MAP.keys() if field_name != "tolerance"
]

TOLERANCE_FIELDS = ["tolerance"]

COMPONENT_SPECIFIC_FIELDS = {
    "MOSFET": ["VDS", "ID", "RDS_on", "VGS", "junction_temperature"],
    "Transistor": ["VCE", "IC", "VBE"],
    "Capacitor": ["capacitance", "capacitance_tolerance", "ESR"],
    "Resistor": ["resistance", "resistance_tolerance", "temperature_coefficient"],
    "Motion sensor": ["sensing_range", "sensitivity_accuracy"],
    "Buzzer": ["frequency", "sound_output"],
}


def _unique(values: List[str]) -> List[str]:
    return list(dict.fromkeys(value for value in values if value))

def _clean(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return text


def _blank_to_status(value: Any) -> str:
    text = _clean(value)
    return text if text else INSUFFICIENT_DATA


def _status_from_confidence(confidence: str) -> str:
    text = _clean(confidence).upper()
    return text or INSUFFICIENT_DATA


def _read_csv_rows(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        return []
    with open(path, mode="r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=1)
def _profiles() -> Dict[str, Dict[str, str]]:
    return {
        _clean(row.get("mpn")).upper(): row
        for row in _read_csv_rows(RELIABILITY_CATALOG_PATH)
        if _clean(row.get("mpn"))
    }


@lru_cache(maxsize=1)
def _evidence_rows() -> List[Dict[str, str]]:
    return _read_csv_rows(EVIDENCE_PATH)


@lru_cache(maxsize=1)
def _reliability_rows() -> List[Dict[str, str]]:
    return _read_csv_rows(RELIABILITY_PATH)


@lru_cache(maxsize=1)
def _degradation_rows() -> List[Dict[str, str]]:
    return _read_csv_rows(DEGRADATION_PATH)


def resolve_exact_mpn(identifier: str, catalog_path: str = "data/component_specs.csv") -> Tuple[Optional[str], List[str]]:
    if not identifier:
        return None, ["Empty identifier."]

    ident = identifier.strip()
    key = ident.upper()
    reasons = [f"Requested identifier: {ident}"]

    from src.industry_data.identity import is_industry_mpn, is_industry_model_id

    industry_identity = is_industry_mpn(ident) or is_industry_model_id(ident)
    if key in _profiles():
        if industry_identity:
            reasons.append("Industry MPN is not joined to the demo reliability catalog.")
            return None, reasons
        reasons.append("Matched exact MPN in evidence-backed reliability catalog.")
        return key, reasons

    if industry_identity:
        reasons.append("Industry identity does not consult the demo component catalog for reliability.")
        return None, reasons

    component = find_component(ident, catalog_path, match_refdes=False)
    if component is not None:
        candidate_key = component.part_number.upper()
        reasons.append(f"Resolved via existing component catalog to MPN {component.part_number}.")
        if candidate_key in _profiles():
            reasons.append("Resolved MPN exists in evidence-backed reliability catalog.")
            return candidate_key, reasons
        reasons.append("Resolved MPN is not present in the reliability dataset.")
        return None, reasons

    reasons.append("Identifier not found in evidence-backed catalog or existing component catalog.")
    return None, reasons


def _build_profile_item(row: Dict[str, str], field_name: str, label: str, unit_field: Optional[str]) -> Dict[str, str]:
    value = _blank_to_status(row.get(field_name))
    unit = _clean(row.get(unit_field)) if unit_field else ""
    status = "AVAILABLE" if value != INSUFFICIENT_DATA else INSUFFICIENT_DATA
    return {
        "field": field_name,
        "label": label,
        "value": value,
        "unit": unit,
        "status": status,
        "confidence": _status_from_confidence(row.get("data_confidence", "")),
        "source_document": _blank_to_status(row.get("source_document")),
        "source_page": _blank_to_status(row.get("source_page")),
    }


def _build_component_specific(row: Dict[str, str]) -> List[Dict[str, str]]:
    component_type = _clean(row.get("component_type"))
    return [
        _build_profile_item(row, field_name, field_name.replace("_", " ").upper(), None)
        for field_name in COMPONENT_SPECIFIC_FIELDS.get(component_type, [])
    ]


def _rows_for_mpn(rows: List[Dict[str, str]], mpn: str) -> List[Dict[str, str]]:
    key = mpn.upper()
    return [row for row in rows if _clean(row.get("mpn")).upper() == key]


def get_component_profile(identifier: str, catalog_path: str = "data/component_specs.csv") -> Dict[str, Any]:
    mpn, resolution = resolve_exact_mpn(identifier, catalog_path)
    if mpn is None:
        return {
            "status": "NOT_FOUND",
            "confidence": INSUFFICIENT_DATA,
            "data": None,
            "evidence": [],
            "limitations": ["Evidence unavailable for this MPN."],
            "resolution": resolution,
        }

    row = _profiles()[mpn]
    profile = {
        "identity": {
            "mpn": row["mpn"],
            "manufacturer": _blank_to_status(row.get("manufacturer")),
            "component_type": _blank_to_status(row.get("component_type")),
            "description": _blank_to_status(row.get("description")),
            "package": _blank_to_status(row.get("package")),
        },
        "electrical_profile": [
            _build_profile_item(row, field_name, label, unit_field)
            for field_name, (label, unit_field) in PROFILE_FIELD_MAP.items()
        ],
        "operating_profile": [
            _build_profile_item(row, field_name, PROFILE_FIELD_MAP[field_name][0], PROFILE_FIELD_MAP[field_name][1])
            for field_name in OPERATING_PROFILE_FIELDS
        ],
        "tolerance_profile": [
            _build_profile_item(row, field_name, PROFILE_FIELD_MAP[field_name][0], PROFILE_FIELD_MAP[field_name][1])
            for field_name in TOLERANCE_FIELDS
        ],
        "component_specific_parameters": _build_component_specific(row),
        "relevant_parameter": _blank_to_status(row.get("relevant_parameter")),
        "datasheet_source": _blank_to_status(row.get("datasheet_source")),
        "source_document": _blank_to_status(row.get("source_document")),
        "source_page": _blank_to_status(row.get("source_page")),
    }
    return {
        "status": "FOUND",
        "confidence": _status_from_confidence(row.get("data_confidence", "")),
        "data": profile,
        "evidence": get_component_evidence(identifier, catalog_path)["data"],
        "limitations": [],
        "resolution": resolution,
    }


def get_component_evidence(identifier: str, catalog_path: str = "data/component_specs.csv") -> Dict[str, Any]:
    mpn, resolution = resolve_exact_mpn(identifier, catalog_path)
    if mpn is None:
        return {
            "status": "NOT_FOUND",
            "confidence": INSUFFICIENT_DATA,
            "data": [],
            "limitations": ["Evidence unavailable for this MPN."],
            "resolution": resolution,
        }

    records = []
    confidences = []
    for row in _rows_for_mpn(_evidence_rows(), mpn):
        confidence = _status_from_confidence(row.get("confidence", ""))
        confidences.append(confidence)
        records.append(
            {
                "source_id": _blank_to_status(row.get("source_id")),
                "source_title": _blank_to_status(row.get("source_title")),
                "source_type": _blank_to_status(row.get("source_type")),
                "manufacturer": _blank_to_status(row.get("manufacturer")),
                "source_url": _blank_to_status(row.get("source_url")),
                "source_page": _blank_to_status(row.get("source_page")),
                "parameter_supported": _blank_to_status(row.get("parameter_supported")),
                "evidence_summary": _blank_to_status(row.get("evidence_summary")),
                "evidence_quality": _blank_to_status(row.get("evidence_quality")),
                "confidence": confidence,
                "notes": _blank_to_status(row.get("notes")),
            }
        )
    return {
        "status": "FOUND" if records else "NOT_FOUND",
        "confidence": confidences[0] if confidences else INSUFFICIENT_DATA,
        "data": records,
        "limitations": [] if records else ["No evidence rows found for exact MPN."],
        "resolution": resolution,
    }


def get_component_reliability(identifier: str, catalog_path: str = "data/component_specs.csv") -> Dict[str, Any]:
    mpn, resolution = resolve_exact_mpn(identifier, catalog_path)
    if mpn is None:
        return {
            "status": "NOT_FOUND",
            "confidence": INSUFFICIENT_DATA,
            "data": [],
            "summary": "Exact-MPN quantitative reliability data unavailable",
            "limitations": ["Evidence unavailable for this MPN."],
            "resolution": resolution,
        }

    rows = _rows_for_mpn(_reliability_rows(), mpn)
    records = []
    has_quantitative = False
    highest_confidence = INSUFFICIENT_DATA
    for row in rows:
        fit = _blank_to_status(row.get("fit"))
        mtbf = _blank_to_status(row.get("mtbf"))
        mttf = _blank_to_status(row.get("mttf"))
        if any(value != INSUFFICIENT_DATA for value in [fit, mtbf, mttf]):
            has_quantitative = True
        confidence = _status_from_confidence(row.get("data_confidence", ""))
        if highest_confidence == INSUFFICIENT_DATA and confidence != INSUFFICIENT_DATA:
            highest_confidence = confidence
        records.append(
            {
                "fit": fit,
                "mtbf": mtbf,
                "mttf": mttf,
                "reliability_metric_type": _blank_to_status(row.get("reliability_metric_type")),
                "test_temperature": _blank_to_status(row.get("test_temperature")),
                "usage_temperature": _blank_to_status(row.get("usage_temperature")),
                "test_duration_hours": _blank_to_status(row.get("test_duration_hours")),
                "sample_size": _blank_to_status(row.get("sample_size")),
                "failures": _blank_to_status(row.get("failures")),
                "confidence_level": _blank_to_status(row.get("confidence_level")),
                "reliability_test_type": _blank_to_status(row.get("reliability_test_type")),
                "qualification_standard": _blank_to_status(row.get("qualification_standard")),
                "reliability_source": _blank_to_status(row.get("reliability_source")),
                "source_document": _blank_to_status(row.get("source_document")),
                "source_page": _blank_to_status(row.get("source_page")),
                "data_confidence": confidence,
            }
        )
    return {
        "status": "FOUND" if rows else "NOT_FOUND",
        "confidence": highest_confidence,
        "data": records,
        "summary": "Quantitative reliability evidence available" if has_quantitative else "Exact-MPN quantitative reliability data unavailable",
        "limitations": [] if rows else ["No reliability rows found for exact MPN."],
        "resolution": resolution,
    }


def get_component_degradation(identifier: str, catalog_path: str = "data/component_specs.csv") -> Dict[str, Any]:
    mpn, resolution = resolve_exact_mpn(identifier, catalog_path)
    if mpn is None:
        return {
            "status": "NOT_FOUND",
            "confidence": INSUFFICIENT_DATA,
            "data": [],
            "summary": "Exact-MPN degradation model unavailable",
            "limitations": ["Evidence unavailable for this MPN."],
            "resolution": resolution,
        }

    rows = _rows_for_mpn(_degradation_rows(), mpn)
    records = []
    exact_model_available = False
    has_class_level = False
    highest_confidence = INSUFFICIENT_DATA
    for row in rows:
        model = _blank_to_status(row.get("degradation_model"))
        parameter = _blank_to_status(row.get("degradation_parameter"))
        evidence_type = _blank_to_status(row.get("evidence_type"))
        confidence = _status_from_confidence(row.get("data_confidence", ""))
        if highest_confidence == INSUFFICIENT_DATA and confidence != INSUFFICIENT_DATA:
            highest_confidence = confidence
        if model != INSUFFICIENT_DATA and parameter != INSUFFICIENT_DATA:
            exact_model_available = True
        if model == INSUFFICIENT_DATA and parameter != INSUFFICIENT_DATA and "class" in evidence_type.lower():
            has_class_level = True
        if model == INSUFFICIENT_DATA and parameter != INSUFFICIENT_DATA and "faq" in _clean(row.get("source_page")).lower():
            has_class_level = True
        records.append(
            {
                "degradation_parameter": parameter,
                "initial_value": _blank_to_status(row.get("initial_value")),
                "initial_unit": _blank_to_status(row.get("initial_unit")),
                "degradation_direction": _blank_to_status(row.get("degradation_direction")),
                "degradation_model": model,
                "degradation_rate": _blank_to_status(row.get("degradation_rate")),
                "rate_unit": _blank_to_status(row.get("rate_unit")),
                "stress_factor": _blank_to_status(row.get("stress_factor")),
                "temperature_dependency": _blank_to_status(row.get("temperature_dependency")),
                "operating_boundary": _blank_to_status(row.get("operating_boundary")),
                "boundary_unit": _blank_to_status(row.get("boundary_unit")),
                "failure_indicator": _blank_to_status(row.get("failure_indicator")),
                "evidence_type": evidence_type,
                "source_document": _blank_to_status(row.get("source_document")),
                "source_page": _blank_to_status(row.get("source_page")),
                "data_confidence": confidence,
            }
        )
    if exact_model_available:
        summary = "Exact-MPN degradation model available"
    elif has_class_level:
        summary = "Class-level degradation evidence available; no exact-MPN model"
    else:
        summary = "Exact-MPN degradation model unavailable"
    return {
        "status": "FOUND" if rows else "NOT_FOUND",
        "confidence": highest_confidence,
        "data": records,
        "summary": summary,
        "limitations": [] if rows else ["No degradation rows found for exact MPN."],
        "resolution": resolution,
    }


def get_operating_margins(identifier: str, catalog_path: str = "data/component_specs.csv") -> Dict[str, Any]:
    profile = get_component_profile(identifier, catalog_path)
    if profile["status"] != "FOUND":
        return {
            "status": profile["status"],
            "confidence": INSUFFICIENT_DATA,
            "data": [],
            "limitations": profile["limitations"],
        }

    row = _profiles()[profile["data"]["identity"]["mpn"].upper()]
    source = _blank_to_status(row.get("source_document"))
    # This dataset supplies component limits, not BOM-specific measured or assumed
    # operating conditions. A limit cannot be reused as the load in a margin formula.
    margins = [
        {
            "parameter": parameter,
            "measured_or_assumed_operating_value": INSUFFICIENT_DATA,
            "allowed_or_rated_boundary": INSUFFICIENT_DATA,
            "margin": INSUFFICIENT_DATA,
            "unit": unit,
            "source": source,
            "confidence": INSUFFICIENT_DATA,
        }
        for parameter, unit in (
            ("Voltage margin", _clean(row.get("voltage_unit")) or "V"),
            ("Current margin", _clean(row.get("current_unit")) or "A"),
            ("Temperature margin", "C"),
            ("Tolerance-related margin", _clean(row.get("tolerance_unit")) or "%"),
        )
    ]

    return {
        "status": "FOUND",
        "confidence": profile["confidence"],
        "data": margins,
        "limitations": ["BOM-specific operating conditions are not present in the dataset. Component limits are displayed in the profile but are not treated as operating loads for a margin calculation."],
    }


def _supply_chain_snapshot(identifier: str, catalog_path: str = "data/component_specs.csv") -> Dict[str, str]:
    component = find_component(identifier, catalog_path)
    if component is None:
        return {
            "lifecycle": INSUFFICIENT_DATA,
            "has_second_source": INSUFFICIENT_DATA,
            "lead_time_weeks": INSUFFICIENT_DATA,
            "stock": INSUFFICIENT_DATA,
        }
    return {
        "lifecycle": _blank_to_status(component.lifecycle_status),
        "has_second_source": str(component.has_second_source) if component.has_second_source is not None else INSUFFICIENT_DATA,
        "lead_time_weeks": str(component.lead_time_weeks) if component.lead_time_weeks is not None else INSUFFICIENT_DATA,
        "stock": str(component.stock) if component.stock is not None else INSUFFICIENT_DATA,
    }


def compare_reliability_outlook(original_identifier: str, candidate_identifier: str, catalog_path: str = "data/component_specs.csv") -> Dict[str, Any]:
    original_profile = get_component_profile(original_identifier, catalog_path)
    candidate_profile = get_component_profile(candidate_identifier, catalog_path)
    original_reliability = get_component_reliability(original_identifier, catalog_path)
    candidate_reliability = get_component_reliability(candidate_identifier, catalog_path)
    original_degradation = get_component_degradation(original_identifier, catalog_path)
    candidate_degradation = get_component_degradation(candidate_identifier, catalog_path)
    original_supply = _supply_chain_snapshot(original_identifier, catalog_path)
    candidate_supply = _supply_chain_snapshot(candidate_identifier, catalog_path)

    evidence = []
    improved_points = 0
    degraded_points = 0

    def to_number(value: Any) -> Optional[float]:
        try:
            if value in {None, "", INSUFFICIENT_DATA}:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def add_evidence(factor: str, original: Any, candidate: Any, reason: str, confidence: str = "MEDIUM", evidence_type: str = "DATASET_FACT") -> None:
        evidence.append(
            {
                "factor": factor,
                "original": original,
                "candidate": candidate,
                "reason": reason,
                "confidence": confidence,
                "evidence_type": evidence_type,
            }
        )

    if original_supply["lifecycle"] != INSUFFICIENT_DATA and candidate_supply["lifecycle"] != INSUFFICIENT_DATA:
        add_evidence("lifecycle", original_supply["lifecycle"], candidate_supply["lifecycle"], "Compared using the existing component catalog supply snapshot.")
        order = {"ACTIVE": 0, "NRND": 1, "OBSOLETE": 2, "EOL": 2}
        orig_val = order.get(original_supply["lifecycle"].upper(), 1)
        cand_val = order.get(candidate_supply["lifecycle"].upper(), 1)
        if cand_val < orig_val:
            improved_points += 1
        elif cand_val > orig_val:
            degraded_points += 1

    if original_supply["has_second_source"] != INSUFFICIENT_DATA and candidate_supply["has_second_source"] != INSUFFICIENT_DATA:
        add_evidence("second_source", original_supply["has_second_source"], candidate_supply["has_second_source"], "Compared using the existing component catalog supply snapshot.")
        if original_supply["has_second_source"] == "False" and candidate_supply["has_second_source"] == "True":
            improved_points += 1
        elif original_supply["has_second_source"] == "True" and candidate_supply["has_second_source"] == "False":
            degraded_points += 1

    original_lead = to_number(original_supply["lead_time_weeks"])
    candidate_lead = to_number(candidate_supply["lead_time_weeks"])
    if original_lead is not None and candidate_lead is not None:
        add_evidence("lead_time_weeks", original_supply["lead_time_weeks"], candidate_supply["lead_time_weeks"], "Compared catalog lead-time fields qualitatively.")
        if candidate_lead < original_lead:
            improved_points += 1
        elif candidate_lead > original_lead:
            degraded_points += 1

    original_stock = to_number(original_supply["stock"])
    candidate_stock = to_number(candidate_supply["stock"])
    if original_stock is not None and candidate_stock is not None:
        add_evidence("stock", original_supply["stock"], candidate_supply["stock"], "Compared catalog stock fields qualitatively.")
        if candidate_stock > original_stock:
            improved_points += 1
        elif candidate_stock < original_stock:
            degraded_points += 1

    original_reliable = original_reliability["summary"] != "Exact-MPN quantitative reliability data unavailable"
    candidate_reliable = candidate_reliability["summary"] != "Exact-MPN quantitative reliability data unavailable"
    if original_reliable or candidate_reliable:
        add_evidence(
            "reliability_evidence",
            original_reliability["summary"],
            candidate_reliability["summary"],
            "Compared exact-MPN reliability evidence coverage only; no service life is predicted.",
            confidence=candidate_reliability.get("confidence", INSUFFICIENT_DATA),
        )
        if not original_reliable and candidate_reliable:
            improved_points += 1
        elif original_reliable and not candidate_reliable:
            degraded_points += 1

    original_degradation_found = original_degradation["status"] == "FOUND"
    candidate_degradation_found = candidate_degradation["status"] == "FOUND"
    if original_degradation["summary"] != candidate_degradation["summary"]:
        add_evidence(
            "degradation_evidence",
            original_degradation["summary"],
            candidate_degradation["summary"],
            "Compared degradation evidence availability only; no missing curve is invented.",
            confidence=candidate_degradation.get("confidence", INSUFFICIENT_DATA),
        )
        if not original_degradation_found and candidate_degradation_found:
            improved_points += 1
        elif original_degradation_found and not candidate_degradation_found:
            degraded_points += 1

    if original_profile["status"] != "FOUND" or candidate_profile["status"] != "FOUND":
        outcome = INSUFFICIENT_DATA
        limitations = ["Exact-MPN evidence-backed comparison is unavailable for one or both components."]
    elif not evidence:
        outcome = INSUFFICIENT_DATA
        limitations = ["No comparable evidence-backed lifecycle, sourcing, reliability, degradation, margin, or tolerance data was available."]
    elif improved_points > degraded_points:
        outcome = "IMPROVED"
        limitations = []
    elif degraded_points > improved_points:
        outcome = "DEGRADED"
        limitations = []
    else:
        outcome = "UNCHANGED"
        limitations = []

    if not evidence:
        confidence = INSUFFICIENT_DATA
    elif len(evidence) >= 4 and not limitations:
        confidence = "HIGH"
    elif len(evidence) >= 2:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    reason = " ".join(item["reason"] for item in evidence) if evidence else "No evidence-backed comparison available."

    return {
        "status": "FOUND" if evidence else INSUFFICIENT_DATA,
        "outcome": outcome,
        "confidence": confidence,
        "evidence": evidence,
        "reason": reason,
        "limitations": limitations,
    }



def _confidence_value(confidence: str) -> int:
    return {INSUFFICIENT_DATA: 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}.get(_clean(confidence).upper(), 0)


def _best_confidence(values: List[str]) -> str:
    if not values:
        return INSUFFICIENT_DATA
    return max((_clean(value).upper() or INSUFFICIENT_DATA for value in values), key=_confidence_value)


def _catalog_scope(identifier: str, catalog_path: str = "data/component_specs.csv") -> str:
    component = find_component(identifier, catalog_path)
    if component is None:
        return "MISSING"
    return "SYNTHETIC_DEMO_FIXTURE" if component.demo_data else "MANUFACTURER_SPEC"


def _supply_comparison_direction(factor: str, original: Any, candidate: Any) -> str:
    if original == INSUFFICIENT_DATA or candidate == INSUFFICIENT_DATA:
        return "MISSING"
    if factor == "lifecycle":
        order = {"ACTIVE": 0, "NRND": 1, "OBSOLETE": 2, "EOL": 2}
        original_rank = order.get(str(original).upper(), 1)
        candidate_rank = order.get(str(candidate).upper(), 1)
        if candidate_rank < original_rank:
            return "IMPROVED"
        if candidate_rank > original_rank:
            return "DEGRADED"
        return "UNCHANGED"
    if factor == "second_source":
        if str(original) == "False" and str(candidate) == "True":
            return "IMPROVED"
        if str(original) == "True" and str(candidate) == "False":
            return "DEGRADED"
        return "UNCHANGED"
    try:
        original_number = float(original)
        candidate_number = float(candidate)
    except (TypeError, ValueError):
        return "MISSING"
    if factor == "lead_time_weeks":
        if candidate_number < original_number:
            return "IMPROVED"
        if candidate_number > original_number:
            return "DEGRADED"
        return "UNCHANGED"
    if factor == "stock":
        if candidate_number > original_number:
            return "IMPROVED"
        if candidate_number < original_number:
            return "DEGRADED"
    return "UNCHANGED"


def build_candidate_reliability_assessment(
    original_identifier: str,
    candidate_identifier: str,
    *,
    classification: str = "",
    engineering_gates: Optional[List[Dict[str, Any]]] = None,
    catalog_path: str = "data/component_specs.csv",
) -> Dict[str, Any]:
    """Build a qualitative, evidence-only reliability assessment for a candidate.

    This function intentionally does not call the part-stress model or generate
    lifetime/MTBF predictions. It summarizes evidence already present in the
    repository and engineering gates already computed by the orchestrator.
    """
    gates = engineering_gates or []
    base = compare_reliability_outlook(original_identifier, candidate_identifier, catalog_path)
    profile = get_component_profile(candidate_identifier, catalog_path)
    evidence_records = get_component_evidence(candidate_identifier, catalog_path)
    reliability = get_component_reliability(candidate_identifier, catalog_path)
    degradation = get_component_degradation(candidate_identifier, catalog_path)

    evidence: List[Dict[str, Any]] = []
    limitations = list(base.get("limitations", []))
    reasons: List[str] = []
    improved = 0
    degraded = 0
    confidences: List[str] = []

    for item in base.get("evidence", []):
        factor = item.get("factor", "")
        direction = _supply_comparison_direction(factor, item.get("original"), item.get("candidate"))
        if direction == "IMPROVED":
            improved += 1
        elif direction == "DEGRADED":
            degraded += 1
        confidence = item.get("confidence", "MEDIUM")
        confidences.append(confidence)
        evidence.append(
            {
                "dimension": factor,
                "scope": _catalog_scope(candidate_identifier, catalog_path),
                "source_type": "SUPPLY_CHAIN_DATA" if factor in {"lifecycle", "second_source", "lead_time_weeks", "stock"} else "RELIABILITY_DATASET",
                "parameter": factor,
                "original_value": item.get("original"),
                "candidate_value": item.get("candidate"),
                "unit": "weeks" if factor == "lead_time_weeks" else "count" if factor == "stock" else "",
                "provenance": _catalog_scope(candidate_identifier, catalog_path),
                "confidence": confidence,
                "direction": direction,
                "source": item.get("reason", "Existing repository evidence."),
            }
        )

    if profile["status"] == "FOUND":
        confidences.append(profile.get("confidence", INSUFFICIENT_DATA))
        evidence.append(
            {
                "dimension": "component_profile",
                "scope": "EXACT_MPN",
                "source_type": "MANUFACTURER_SPEC",
                "parameter": "profile_available",
                "candidate_value": profile["data"]["identity"]["mpn"],
                "unit": "",
                "provenance": "MANUFACTURER_SPEC",
                "confidence": profile.get("confidence", INSUFFICIENT_DATA),
                "direction": "UNCHANGED",
                "source": profile["data"].get("source_document", INSUFFICIENT_DATA),
            }
        )
    else:
        limitations.append("No exact-MPN manufacturer/specification profile is available for the candidate.")

    if evidence_records["status"] == "FOUND":
        confidences.append(evidence_records.get("confidence", INSUFFICIENT_DATA))
        for row in evidence_records["data"][:3]:
            evidence.append(
                {
                    "dimension": "manufacturer_evidence",
                    "scope": "EXACT_MPN",
                    "source_type": row.get("source_type", "MANUFACTURER_SPEC"),
                    "parameter": row.get("parameter_supported", INSUFFICIENT_DATA),
                    "candidate_value": row.get("evidence_summary", INSUFFICIENT_DATA),
                    "unit": "",
                    "provenance": row.get("evidence_quality", "MANUFACTURER_SPEC"),
                    "confidence": row.get("confidence", INSUFFICIENT_DATA),
                    "direction": "UNCHANGED",
                    "source": row.get("source_title", INSUFFICIENT_DATA),
                }
            )

    if reliability["status"] == "FOUND" and reliability["summary"] != "Exact-MPN quantitative reliability data unavailable":
        confidences.append(reliability.get("confidence", INSUFFICIENT_DATA))
        evidence.append(
            {
                "dimension": "component_reliability",
                "scope": "EXACT_MPN",
                "source_type": "COMPONENT_SPECIFIC_RELIABILITY_EVIDENCE",
                "parameter": "reliability_evidence_available",
                "candidate_value": reliability["summary"],
                "unit": "",
                "provenance": "EXACT_MPN",
                "confidence": reliability.get("confidence", INSUFFICIENT_DATA),
                "direction": "UNCHANGED",
                "source": reliability["data"][0].get("source_document", INSUFFICIENT_DATA) if reliability["data"] else INSUFFICIENT_DATA,
            }
        )
    else:
        limitations.append("No exact-MPN quantitative reliability evidence is available for the candidate.")

    if degradation["status"] == "FOUND" and degradation["summary"] != "Exact-MPN degradation model unavailable":
        confidence = degradation.get("confidence", INSUFFICIENT_DATA)
        confidences.append(confidence)
        first = degradation["data"][0] if degradation["data"] else {}
        scope = "EXACT_MPN" if degradation["summary"] == "Exact-MPN degradation model available" else "CATEGORY_LEVEL"
        evidence.append(
            {
                "dimension": "degradation",
                "scope": scope,
                "source_type": "DEGRADATION_PROFILE",
                "parameter": first.get("degradation_parameter", INSUFFICIENT_DATA),
                "candidate_value": degradation["summary"],
                "unit": first.get("initial_unit", ""),
                "provenance": first.get("evidence_type", scope),
                "confidence": confidence,
                "direction": "UNCHANGED",
                "source": first.get("source_document", INSUFFICIENT_DATA),
            }
        )
    else:
        limitations.append("No exact-MPN degradation model is available for the candidate.")

    for gate in gates:
        status = gate.get("status", INSUFFICIENT_DATA)
        if status in {"SAFE_MARGIN", "WARNING_MARGIN", "LIMIT_APPROACHING", "OUT_OF_LIMIT", "INSUFFICIENT_DATA", "NOT_APPLICABLE"}:
            direction = "UNCHANGED"
            if status == "OUT_OF_LIMIT":
                direction = "DEGRADED"
                degraded += 1
            confidence = gate.get("confidence", INSUFFICIENT_DATA)
            confidences.append(confidence)
            evidence.append(
                {
                    "dimension": "operating_limit" if gate.get("check_type") == "OPERATING_LIMIT" else "tolerance",
                    "scope": "SYNTHETIC_DEMO_FIXTURE" if gate.get("provenance") == "SENTINEL_ENGINEERING_LAYER_DEMO_FIXTURE" else gate.get("provenance", "MISSING"),
                    "source_type": gate.get("source_type", "ENGINEERING_CHECK"),
                    "parameter": gate.get("parameter", INSUFFICIENT_DATA),
                    "candidate_value": status,
                    "unit": gate.get("unit", ""),
                    "provenance": gate.get("provenance", gate.get("evidence_type", "MISSING")),
                    "confidence": confidence,
                    "direction": direction,
                    "source": gate.get("source", "candidate_orchestrator engineering gate"),
                    "margin": gate.get("normalized_margin"),
                }
            )
            if status == "INSUFFICIENT_DATA":
                limitations.append(f"{gate.get('parameter', 'engineering_check')}: insufficient engineering evidence.")

    if classification == "INCOMPATIBLE":
        outcome = "DEGRADED"
        reasons.append("Compatibility classification is INCOMPATIBLE; reliability cannot override this hard failure.")
    elif any(gate.get("status") == "OUT_OF_LIMIT" for gate in gates):
        outcome = "DEGRADED"
        reasons.append("At least one operating or tolerance gate is OUT_OF_LIMIT.")
    elif not evidence:
        outcome = INSUFFICIENT_DATA
        reasons.append("No reliability evidence was available.")
    elif improved > degraded:
        outcome = "IMPROVED"
        reasons.append("Candidate has stronger qualitative supply/evidence indicators than the original.")
    elif degraded > improved:
        outcome = "DEGRADED"
        reasons.append("Candidate has weaker qualitative evidence indicators than the original.")
    else:
        outcome = "UNCHANGED"
        reasons.append("Available qualitative reliability evidence does not show a material improvement or degradation.")

    exact_evidence = any(item.get("scope") == "EXACT_MPN" for item in evidence)
    engineering_evidence = any(item.get("dimension") in {"operating_limit", "tolerance"} and item.get("candidate_value") != INSUFFICIENT_DATA for item in evidence)
    if not evidence:
        confidence = INSUFFICIENT_DATA
    elif exact_evidence and engineering_evidence and _confidence_value(_best_confidence(confidences)) >= _confidence_value("MEDIUM"):
        confidence = "HIGH"
    elif exact_evidence or engineering_evidence or len(evidence) >= 2:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "status": "FOUND" if evidence else INSUFFICIENT_DATA,
        "outcome": outcome,
        "confidence": confidence,
        "evidence": evidence,
        "reasons": reasons,
        "reason": " ".join(reasons),
        "limitations": _unique(limitations),
        "legacy_outlook": base,
    }
def build_degradation_scenario(identifier: str, catalog_path: str = "data/component_specs.csv") -> Dict[str, Any]:
    degradation = get_component_degradation(identifier, catalog_path)
    if degradation["status"] != "FOUND":
        return {
            "status": INSUFFICIENT_DATA,
            "mode": INSUFFICIENT_DATA,
            "timeline": [],
            "message": "Simulation unavailable for exact MPN - insufficient degradation evidence",
            "limitations": degradation["limitations"],
        }

    first = degradation["data"][0] if degradation["data"] else {}
    model = first.get("degradation_model", INSUFFICIENT_DATA)
    parameter = first.get("degradation_parameter", INSUFFICIENT_DATA)
    if model != INSUFFICIENT_DATA and parameter != INSUFFICIENT_DATA:
        return {
            "status": "FOUND",
            "mode": "EXACT_MPN_MODEL",
            "timeline": [
                {
                    "time": "t0",
                    "parameter": parameter,
                    "condition": first.get("initial_value", INSUFFICIENT_DATA),
                    "operating_margin": "See operating margin section",
                    "risk_outlook": "Evidence-backed model available",
                    "recommended_action": "Monitor against documented failure indicator.",
                }
            ],
            "message": "Exact-MPN degradation model available",
            "limitations": ["Current visualization exposes only documented model metadata; it does not invent missing curve points."],
        }

    if parameter != INSUFFICIENT_DATA:
        return {
            "status": "FOUND",
            "mode": CLASS_LEVEL_EVIDENCE,
            "timeline": [
                {
                    "time": "qualitative",
                    "parameter": parameter,
                    "condition": first.get("degradation_direction", INSUFFICIENT_DATA),
                    "operating_margin": "Cannot be quantified from current dataset",
                    "risk_outlook": "Class-level degradation scenario",
                    "recommended_action": "Treat as qualitative evidence only; do not use as an exact-MPN lifetime curve.",
                }
            ],
            "message": "Qualitative class-level degradation scenario",
            "limitations": ["No exact-MPN degradation rate is available in the dataset."],
        }

    return {
        "status": INSUFFICIENT_DATA,
        "mode": INSUFFICIENT_DATA,
        "timeline": [],
        "message": "Simulation unavailable for exact MPN - insufficient degradation evidence",
        "limitations": ["No defensible degradation parameter or model exists for this exact MPN."],
    }


def get_downstream_impact(
    identifier: str,
    catalog_path: str = "data/component_specs.csv",
    product_id: Optional[str] = None,
) -> Dict[str, Any]:
    from src.industry_data.identity import is_industry_product

    node = str(identifier or "").strip()
    if product_id and is_industry_product(product_id):
        if not node:
            return {
                "status": INSUFFICIENT_DATA,
                "confidence": INSUFFICIENT_DATA,
                "data": [],
                "limitations": ["No reference designator is available for downstream traversal."],
            }
        graph = load_component_graph(product_id, node)
        affected = traverse_downstream(graph, node)
        if not affected:
            return {
                "status": INSUFFICIENT_DATA,
                "confidence": INSUFFICIENT_DATA,
                "data": [],
                "limitations": ["No BOM-specific logical dependency graph is present for this reference designator."],
            }
        confidence_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        known_confidences = [str(item["confidence"]).upper() for item in affected if str(item["confidence"]).upper() in confidence_rank]
        confidence = (
            INSUFFICIENT_DATA
            if any(item["status"] == INSUFFICIENT_DATA for item in affected)
            else min(known_confidences, key=confidence_rank.get) if known_confidences else INSUFFICIENT_DATA
        )
        return {
            "status": "FOUND",
            "confidence": confidence,
            "data": affected,
            "limitations": [item["limitations"][0] for item in affected if item["limitations"]],
            "product_id": product_id,
            "component_id": node,
        }

    component = find_component(identifier, catalog_path)
    if component is None:
        return {
            "status": INSUFFICIENT_DATA,
            "confidence": INSUFFICIENT_DATA,
            "data": [],
            "limitations": ["No logical design graph is available for this BOM component in the current repository."],
        }

    scopes = [product_id] if product_id else scopes_for_component(component.component_id)
    if len(scopes) != 1:
        return {
            "status": INSUFFICIENT_DATA,
            "confidence": INSUFFICIENT_DATA,
            "data": [],
            "limitations": ["No BOM-specific logical dependency graph is present in the current repository, so downstream propagation cannot be asserted without inventing relationships."],
        }

    graph = load_component_graph(scopes[0], component.component_id)
    affected = traverse_downstream(graph, component.component_id)
    if not affected:
        return {
            "status": INSUFFICIENT_DATA,
            "confidence": INSUFFICIENT_DATA,
            "data": [],
            "limitations": ["No BOM-specific logical dependency graph is present in the current repository, so downstream propagation cannot be asserted without inventing relationships."],
        }
    confidence_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    known_confidences = [str(item["confidence"]).upper() for item in affected if str(item["confidence"]).upper() in confidence_rank]
    confidence = (
        INSUFFICIENT_DATA
        if any(item["status"] == INSUFFICIENT_DATA for item in affected)
        else min(known_confidences, key=confidence_rank.get) if known_confidences else INSUFFICIENT_DATA
    )
    return {
        "status": "FOUND",
        "confidence": confidence,
        "data": affected,
        "limitations": [item["limitations"][0] for item in affected if item["limitations"]],
        "product_id": scopes[0],
        "component_id": component.component_id,
    }


def final_engineering_recommendation(original_identifier: str, candidate_identifier: str, classification: str, catalog_path: str = "data/component_specs.csv") -> Dict[str, Any]:
    outlook = compare_reliability_outlook(original_identifier, candidate_identifier, catalog_path)
    original_reliability = get_component_reliability(original_identifier, catalog_path)
    candidate_reliability = get_component_reliability(candidate_identifier, catalog_path)
    exact_reliability_complete = (
        original_reliability["summary"] == "Quantitative reliability evidence available"
        and candidate_reliability["summary"] == "Quantitative reliability evidence available"
    )
    if classification == "INCOMPATIBLE":
        result = "AVOID / INCOMPATIBLE"
    elif classification == "INSUFFICIENT_EVIDENCE":
        result = "INSUFFICIENT DATA"
    elif outlook["outcome"] == INSUFFICIENT_DATA:
        result = "INSUFFICIENT DATA"
    elif classification == "REQUIRES_REDESIGN":
        result = "CONSIDER WITH ENGINEERING REVIEW"
    elif outlook["outcome"] == "IMPROVED" and exact_reliability_complete:
        result = "SAFE TO CONSIDER"
    else:
        result = "CONSIDER WITH ENGINEERING REVIEW"

    reasons = [classification, outlook["outcome"]]
    limitations = list(outlook["limitations"])
    if not exact_reliability_complete:
        reasons.append("Exact-MPN quantitative reliability evidence is incomplete; this is recommended for engineering review, not certified safe.")
        limitations.append("Exact-MPN quantitative reliability evidence is not available for both original and candidate.")
    if outlook["reason"]:
        reasons.append(outlook["reason"])
    return {
        "status": "FOUND",
        "recommendation": result,
        "reason": " | ".join(reasons),
        "confidence": outlook["confidence"],
        "limitations": limitations,
    }


def get_component_analysis(identifier: str, catalog_path: str = "data/component_specs.csv") -> Dict[str, Any]:
    profile = get_component_profile(identifier, catalog_path)
    evidence = get_component_evidence(identifier, catalog_path)
    reliability = get_component_reliability(identifier, catalog_path)
    degradation = get_component_degradation(identifier, catalog_path)
    margins = get_operating_margins(identifier, catalog_path)
    scenario = build_degradation_scenario(identifier, catalog_path)
    downstream = get_downstream_impact(identifier, catalog_path)
    return {
        "status": profile["status"],
        "confidence": profile["confidence"],
        "data": {
            "profile": profile["data"],
            "evidence": evidence["data"],
            "reliability": reliability,
            "degradation": degradation,
            "operating_margins": margins,
            "degradation_scenario": scenario,
            "downstream_impact": downstream,
        },
        "limitations": profile["limitations"] + reliability["limitations"] + degradation["limitations"],
        "resolution": profile["resolution"],
    }
