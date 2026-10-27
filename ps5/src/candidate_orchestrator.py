"""Candidate-decision orchestration with hard-gate filtering before ranking.

Ranking is deliberately a two-phase process.  Candidates with an incompatible
classification, a vendor ``FAIL``, or an engineering-gate ``FAIL`` are first
eliminated.  Survivors are ordered by: (1) fewer WARNING reason codes,
(2) vendor status (FEASIBLE, WARNING, INSUFFICIENT_DATA), (3) classification
(DROP_IN_CANDIDATE before REQUIRES_REDESIGN), then (4) stable part number.
Missing evidence is never converted into a pass.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from src.component_catalog import build_risk_profile, find_component
from src.component_intelligence import (
    build_candidate_reliability_assessment,
    compare_reliability_outlook,
    get_component_degradation,
    get_component_reliability,
    get_downstream_impact,
)
from src.engineering_checks import (
    INSUFFICIENT_DATA as ENGINEERING_INSUFFICIENT_DATA,
    LIMIT_APPROACHING,
    OUT_OF_LIMIT,
    WARNING_MARGIN,
    evaluate_operating_limit,
    evaluate_tolerance,
)
from src.industry_data.csv_store import read_csv
from src.industry_data.identity import (
    evidence_row_matches,
    is_industry_product,
    operating_value_is_synthetic,
)
from src.industry_candidate_adapter import resolve_industry_candidate, resolve_industry_component
from src.providers.settings import ROOT
from src.substitute_engine import (
    DROP_IN,
    INCOMPATIBLE_CLASSIFICATION,
    REQUIRES_REDESIGN,
    evaluate_candidate,
    recommend_industry_substitutes,
    recommend_substitutes,
)
from src.vendor_feasibility import FAIL as VENDOR_FAIL
from src.vendor_feasibility import FEASIBLE, INSUFFICIENT_DATA, WARNING, evaluate_vendor_feasibility


TOP_CANDIDATES = 3
_HIGH_RISK_BANDS = {"HIGH", "CRITICAL"}


def _unique(values: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(value for value in values if value))


def _target_in_product(product_id: str, target_component_id: str) -> bool:
    target = str(target_component_id or "").strip()
    return any(
        row.get("product_id") == product_id and row.get("reference_designator") == target
        for row in read_csv("bom_lines.csv")
    )


def _risk_trigger(product_id: str, target_component_id: str) -> Dict[str, Any]:
    """Call the existing risk-engine adapter when a catalog component exists.

    Industry BOM rows are never resolved through the demo catalog.  Missing
    vendor/lifecycle evidence is reported as insufficient data rather than a
    synthesized Active/in-stock profile.
    """
    if is_industry_product(product_id):
        if not _target_in_product(product_id, target_component_id):
            return {
                "status": INSUFFICIENT_DATA,
                "triggered": False,
                "reason_codes": ["TARGET_NOT_IN_PRODUCT"],
                "limitations": ["The target reference designator is absent from the normalized BOM scope."],
            }
        industry_component = resolve_industry_component(product_id, target_component_id)
        if industry_component is None:
            return {
                "status": INSUFFICIENT_DATA,
                "triggered": False,
                "reason_codes": ["TARGET_COMPONENT_SPEC_UNAVAILABLE"],
                "limitations": ["No normalized industry model is available for this reference designator."],
            }
        profile = build_risk_profile(industry_component)
        if str(getattr(profile, "evidence_status", "") or "").upper() == INSUFFICIENT_DATA:
            return {
                "status": INSUFFICIENT_DATA,
                "triggered": False,
                "reason_codes": ["RISK_PROFILE_UNAVAILABLE"],
                "limitations": [
                    "The normalized industry component resolves to a real MPN, but no vendor, stock, lead-time, or lifecycle evidence is persisted for it."
                ],
            }
        band = str(profile.risk_band or "").upper()
        return {
            "status": "FOUND",
            "triggered": band in _HIGH_RISK_BANDS,
            "risk_score": profile.risk_score,
            "risk_band": profile.risk_band,
            "reason_codes": list(profile.risk_reasons),
            "limitations": [],
            "evidence_status": getattr(profile, "evidence_status", ""),
        }
    component = find_component(target_component_id)
    if component is None:
        return {
            "status": INSUFFICIENT_DATA,
            "triggered": False,
            "reason_codes": ["RISK_COMPONENT_SPEC_UNAVAILABLE"],
            "limitations": ["No catalog specification is available for this identifier."],
        }
    profile = build_risk_profile(component)
    band = str(profile.risk_band or "").upper()
    return {
        "status": "FOUND",
        "triggered": band in _HIGH_RISK_BANDS,
        "risk_score": profile.risk_score,
        "risk_band": profile.risk_band,
        "reason_codes": list(profile.risk_reasons),
        "limitations": (
            ["This risk result is catalog-resolved by demo identity and is not board-MPN verified."]
            if component.demo_data
            else []
        ),
    }


def _read_limit_rows(filename: str, product_id: str) -> List[Dict[str, Any]]:
    if is_industry_product(product_id):
        return read_csv(filename)
    demo_path = ROOT / "data" / "demo" / filename
    if not demo_path.is_file():
        return []
    import csv

    with demo_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _normalized_operating_gates(component: Any, product_id: str) -> List[Dict[str, Any]]:
    gates = []
    for row in _read_limit_rows("operating_limits.csv", product_id):
        if not evidence_row_matches(component, row):
            continue
        operating_value = row.get("operating_value")
        if is_industry_product(product_id) and operating_value_is_synthetic(row):
            operating_value = None
        gate = evaluate_operating_limit(
            parameter=row.get("parameter", ""),
            operating_value=operating_value,
            limit_min=row.get("required_min"),
            limit_max=row.get("required_max"),
            unit=row.get("unit", ""),
            condition=row.get("condition", ""),
            source=row.get("source", ""),
            confidence=row.get("confidence", ""),
        )
        gate.update(
            {
                "profile_component_id": row.get("component_model_id", "") or row.get("normalized_mpn", ""),
                "source_type": row.get("source_type", ""),
                "provenance": row.get("provenance", ""),
            }
        )
        gates.append(gate)
    return gates


def _normalized_tolerance_gates(component: Any, product_id: str) -> List[Dict[str, Any]]:
    gates = []
    for row in _read_limit_rows("tolerance_records.csv", product_id):
        if not evidence_row_matches(component, row):
            continue
        if str(row.get("tolerance_type") or "").strip().lower() == "not_applicable":
            gates.append(
                {
                    "check_type": "TOLERANCE",
                    "parameter": row.get("parameter", ""),
                    "status": "NOT_APPLICABLE",
                    "legacy_status": "NOT_APPLICABLE",
                    "reason": "TOLERANCE_NOT_APPLICABLE",
                    "nominal": None,
                    "tolerance": None,
                    "lower_bound": None,
                    "upper_bound": None,
                    "actual_value": None,
                    "design_value": None,
                    "margin": None,
                    "normalized_margin": None,
                    "unit": row.get("unit", ""),
                    "condition": row.get("condition", ""),
                    "source": row.get("source", ""),
                    "source_type": row.get("source_type", ""),
                    "confidence": row.get("confidence", "") or ENGINEERING_INSUFFICIENT_DATA,
                    "evidence_type": "NOT_APPLICABLE",
                    "profile_component_id": row.get("component_model_id", "") or row.get("normalized_mpn", ""),
                    "provenance": row.get("provenance", ""),
                }
            )
            continue
        gate = evaluate_tolerance(
            parameter=row.get("parameter", ""),
            candidate_nominal=row.get("nominal"),
            candidate_tolerance=row.get("tolerance_value"),
            candidate_min=row.get("min_value"),
            candidate_max=row.get("max_value"),
            design_value=row.get("nominal"),
            unit=row.get("unit", ""),
            condition=row.get("condition", ""),
            source=row.get("source", ""),
            confidence=row.get("confidence", ""),
        )
        gate.update(
            {
                "profile_component_id": row.get("component_model_id", "") or row.get("normalized_mpn", ""),
                "source_type": row.get("source_type", ""),
                "provenance": row.get("provenance", ""),
            }
        )
        gates.append(gate)
    return gates


def _engineering_gates(original: Any, candidate: Any, product_id: str = "") -> List[Dict[str, Any]]:
    normalized_gates = _normalized_operating_gates(candidate, product_id) + _normalized_tolerance_gates(candidate, product_id)
    if normalized_gates:
        return normalized_gates

    original_specs = original.specs
    candidate_specs = candidate.specs
    spec_source = "industry_component_specs" if is_industry_product(product_id) else "component_specs.csv"
    gates = [
        evaluate_operating_limit(
            parameter="supply_voltage_v",
            required_min=original_specs.get("supply_voltage_min_v") or original_specs.get("input_voltage_min_v"),
            required_max=original_specs.get("supply_voltage_max_v") or original_specs.get("input_voltage_max_v"),
            candidate_min=candidate_specs.get("supply_voltage_min_v") or candidate_specs.get("input_voltage_min_v"),
            candidate_max=candidate_specs.get("supply_voltage_max_v") or candidate_specs.get("input_voltage_max_v"),
            unit="V",
            source=spec_source,
            confidence="CATALOG" if spec_source == "component_specs.csv" else "INDUSTRY_EAV",
        ),
        evaluate_operating_limit(
            parameter="operating_temperature_c",
            required_min=original_specs.get("operating_temperature_min_c"),
            required_max=original_specs.get("operating_temperature_max_c"),
            candidate_min=candidate_specs.get("operating_temperature_min_c"),
            candidate_max=candidate_specs.get("operating_temperature_max_c"),
            unit="C",
            source=spec_source,
            confidence="CATALOG" if spec_source == "component_specs.csv" else "INDUSTRY_EAV",
        ),
    ]

    passive_nominals = {
        "resistor": ("resistance_ohms", "ohm"),
        "capacitor": ("capacitance_uf", "uF"),
    }
    nominal_key, unit = passive_nominals.get(str(original.category or "").lower(), (None, "%"))
    if nominal_key:
        gates.append(
            evaluate_tolerance(
                parameter=nominal_key,
                required_nominal=original_specs.get(nominal_key),
                required_tolerance=original_specs.get("tolerance_pct"),
                candidate_nominal=candidate_specs.get(nominal_key),
                candidate_tolerance=candidate_specs.get("tolerance_pct"),
                design_value=original_specs.get(nominal_key),
                unit=unit,
                condition="Category-aware passive tolerance check using catalog nominal and tolerance_pct.",
                source=spec_source,
                confidence="CATALOG" if spec_source == "component_specs.csv" else "INDUSTRY_EAV",
            )
        )
    else:
        gates.append(
            evaluate_tolerance(
                parameter="tolerance_pct",
                required_nominal=original_specs.get("tolerance_pct"),
                candidate_nominal=candidate_specs.get("tolerance_pct"),
                unit="%",
                condition="Tolerance comparison is reported only when category-relevant catalog values exist.",
                source=spec_source,
                confidence="CATALOG" if spec_source == "component_specs.csv" else "INDUSTRY_EAV",
            )
        )
    return gates


def _gate_is_hard_failure(gate: Dict[str, Any]) -> bool:
    return gate.get("status") in {"FAIL", OUT_OF_LIMIT} or gate.get("legacy_status") == "FAIL"


def _gate_warning(gate: Dict[str, Any]) -> bool:
    return gate.get("status") in {"WARNING", WARNING_MARGIN, LIMIT_APPROACHING}


def _first_gate(gates: List[Dict[str, Any]], check_type: str) -> Dict[str, Any]:
    for gate in gates:
        if gate.get("check_type") == check_type:
            return gate
    return {"status": ENGINEERING_INSUFFICIENT_DATA, "reason": f"{check_type}_UNAVAILABLE"}


def _operating_margin(gates: List[Dict[str, Any]]) -> Optional[float]:
    margins = [gate.get("normalized_margin") for gate in gates if gate.get("check_type") == "OPERATING_LIMIT" and gate.get("normalized_margin") is not None]
    return min(margins) if margins else None


def _decision_confidence(gates: List[Dict[str, Any]], reliability: Dict[str, Any], downstream: Dict[str, Any]) -> str:
    supported = sum(1 for gate in gates if gate.get("status") != ENGINEERING_INSUFFICIENT_DATA)
    supported += 1 if reliability.get("outcome") != INSUFFICIENT_DATA else 0
    supported += 1 if downstream.get("status") == "FOUND" else 0
    if supported >= 4:
        return "HIGH"
    if supported >= 2:
        return "MEDIUM"
    if supported >= 1:
        return "LOW"
    return INSUFFICIENT_DATA


def _limitations(gates: List[Dict[str, Any]], reliability: Dict[str, Any], downstream: Dict[str, Any]) -> List[str]:
    limitations = []
    limitations.extend(f"{gate.get('parameter')}: {gate.get('reason')}" for gate in gates if gate.get("status") == ENGINEERING_INSUFFICIENT_DATA)
    limitations.extend(reliability.get("limitations", []))
    limitations.extend(downstream.get("limitations", []))
    return _unique(limitations)


def _overall_status(
    classification: str,
    vendor: Dict[str, Any],
    engineering_gates: List[Dict[str, Any]],
    reliability: Dict[str, Any],
    downstream: Dict[str, Any],
) -> str:
    if classification == INCOMPATIBLE_CLASSIFICATION or vendor["status"] == VENDOR_FAIL or any(_gate_is_hard_failure(gate) for gate in engineering_gates):
        return "FAIL"
    if (
        vendor["status"] == INSUFFICIENT_DATA
        or any(gate["status"] == ENGINEERING_INSUFFICIENT_DATA for gate in engineering_gates)
        or reliability.get("outcome") == INSUFFICIENT_DATA
        or downstream.get("status") == INSUFFICIENT_DATA
    ):
        return INSUFFICIENT_DATA
    if vendor["status"] == WARNING or classification == REQUIRES_REDESIGN or reliability.get("outcome") == "DEGRADED" or any(_gate_warning(gate) for gate in engineering_gates):
        return "WARN"
    return "PASS"


def _reason_codes(
    classification: str,
    vendor: Dict[str, Any],
    gates: List[Dict[str, Any]],
    reliability: Dict[str, Any],
    downstream: Dict[str, Any],
) -> List[str]:
    codes = [classification, *vendor.get("reason_codes", [])]
    codes.extend(str(gate.get("reason") or "") for gate in gates)
    codes.append(f"RELIABILITY_{reliability.get('outcome', INSUFFICIENT_DATA)}")
    codes.append("DOWNSTREAM_FOUND" if downstream.get("status") == "FOUND" else "DOWNSTREAM_INSUFFICIENT_DATA")
    return _unique(codes)


def _warning_count(result: Dict[str, Any]) -> int:
    warning_codes = {"WARNING", "LOW_STOCK", "LONG_LEAD_TIME", "SINGLE_SOURCE", "NRND", REQUIRES_REDESIGN, "RELIABILITY_DEGRADED"}
    return sum(code in warning_codes for code in result["reason_codes"])


def _rank_key(result: Dict[str, Any]) -> tuple:
    vendor_order = {FEASIBLE: 0, WARNING: 1, INSUFFICIENT_DATA: 2}
    classification_order = {DROP_IN: 0, REQUIRES_REDESIGN: 1}
    return (
        _warning_count(result),
        vendor_order.get(result["vendor_status"], 3),
        classification_order.get(result["classification"], 2),
        result["candidate_id"],
    )


def _evaluate_one(product_id: str, target_id: str, original: Any, candidate: Any) -> Dict[str, Any]:
    generated = evaluate_candidate(original, candidate)
    vendor = evaluate_vendor_feasibility(candidate)
    gates = _engineering_gates(original, candidate, product_id)
    reliability = compare_reliability_outlook(original.part_number, candidate.part_number)
    classification = generated["classification"]
    reliability_assessment = build_candidate_reliability_assessment(
        original.part_number,
        candidate.part_number,
        classification=classification,
        engineering_gates=gates,
    )
    downstream = get_downstream_impact(target_id, product_id=product_id)
    reliability_evidence = {
        "original": get_component_reliability(original.part_number),
        "candidate": get_component_reliability(candidate.part_number),
        "original_degradation": get_component_degradation(original.part_number),
        "candidate_degradation": get_component_degradation(candidate.part_number),
        "outlook": reliability,
        "assessment": reliability_assessment,
        "evidence_items": reliability_assessment.get("evidence", []),
    }
    result = {
        "candidate_id": candidate.component_id,
        "candidate_part_number": candidate.part_number,
        "classification": classification,
        "candidate_generation": generated,
        "vendor_status": vendor["status"],
        "vendor_gate": vendor,
        "engineering_gates": gates,
        "operating_limit_result": _first_gate(gates, "OPERATING_LIMIT"),
        "tolerance_result": _first_gate(gates, "TOLERANCE"),
        "operating_margin": _operating_margin(gates),
        "reliability_outlook": reliability_assessment,
        "legacy_reliability_outlook": reliability,
        "reliability_confidence": reliability_assessment.get("confidence"),
        "reliability_reasons": reliability_assessment.get("reasons", []),
        "reliability_limitations": reliability_assessment.get("limitations", []),
        "reliability_evidence": reliability_evidence,
        "downstream_impact": downstream,
    }
    result["overall_status"] = _overall_status(classification, vendor, gates, reliability, downstream)
    result["reason_codes"] = _reason_codes(classification, vendor, gates, reliability, downstream)
    result["reasons"] = result["reason_codes"]
    result["limitations"] = _limitations(gates, reliability, downstream)
    result["confidence"] = _decision_confidence(gates, reliability, downstream)
    result["hard_gate_failures"] = _unique(
        (["CLASSIFICATION_INCOMPATIBLE"] if classification == INCOMPATIBLE_CLASSIFICATION else [])
        + (["VENDOR_FAIL"] if vendor["status"] == VENDOR_FAIL else [])
        + [str(gate["reason"]) for gate in gates if _gate_is_hard_failure(gate)]
    )
    return result


def evaluate_candidate_decision(
    product_id: str,
    target_component_id: str,
    candidate_id: Optional[str] = None,
    *,
    top_n: int = TOP_CANDIDATES,
) -> Dict[str, Any]:
    """Evaluate a BOM-scoped target and rank only candidates that pass hard gates."""
    risk_trigger = _risk_trigger(product_id, target_component_id)
    downstream_impact = get_downstream_impact(target_component_id, product_id=product_id)
    if is_industry_product(product_id):
        original = resolve_industry_component(product_id, target_component_id)
    else:
        original = find_component(target_component_id)
    if original is None:
        return {
            "product_id": product_id,
            "target_component_id": target_component_id,
            "risk_trigger": risk_trigger,
            "downstream_impact": downstream_impact,
            "status": INSUFFICIENT_DATA,
            "reason_codes": ["TARGET_COMPONENT_SPEC_UNAVAILABLE"],
            "candidates": [],
        }

    generation: Dict[str, Any]
    if candidate_id:
        if is_industry_product(product_id):
            candidate = resolve_industry_candidate(product_id, target_component_id, candidate_id)
        else:
            candidate = find_component(candidate_id)
        if candidate is None:
            return {
                "product_id": product_id,
                "target_component_id": target_component_id,
                "risk_trigger": risk_trigger,
                "downstream_impact": downstream_impact,
                "status": INSUFFICIENT_DATA,
                "reason_codes": ["CANDIDATE_COMPONENT_NOT_FOUND"],
                "candidates": [],
            }
        generation = {"mode": "specific_candidate", "candidate_id": candidate_id}
        candidates = [candidate]
    else:
        industry_scope = is_industry_product(product_id)
        generation = (
            recommend_industry_substitutes(product_id, target_component_id)
            if industry_scope
            else recommend_substitutes(target_component_id)
        )
        if generation.get("error"):
            return {
                "product_id": product_id,
                "target_component_id": target_component_id,
                "risk_trigger": risk_trigger,
                "downstream_impact": downstream_impact,
                "status": INSUFFICIENT_DATA,
                "reason_codes": [generation["error"]],
                "candidate_generation": generation,
                "candidates": [],
            }
        candidates = []
        for item in generation.get("candidates", [])[:max(1, top_n)]:
            candidate_key = item["candidate_id"] if "candidate_id" in item else item["component"]["component_id"]
            candidate = (
                resolve_industry_candidate(product_id, target_component_id, candidate_key)
                if industry_scope
                else find_component(candidate_key)
            )
            if candidate is not None:
                candidates.append(candidate)

    evaluated = [_evaluate_one(product_id, target_component_id, original, candidate) for candidate in candidates]
    survivors = [item for item in evaluated if not item["hard_gate_failures"]]
    eliminated = [item for item in evaluated if item["hard_gate_failures"]]
    survivors.sort(key=_rank_key)
    for index, item in enumerate(survivors, start=1):
        item["rank"] = index
        item["ranking_rule"] = "fewer warning codes, then vendor status, then classification, then stable candidate id"
    for item in eliminated:
        item["rank"] = None
        item["ranking_rule"] = "eliminated before soft-factor ranking due to hard_gate_failures"

    return {
        "product_id": product_id,
        "target_component_id": target_component_id,
        "risk_trigger": risk_trigger,
        "candidate_generation": generation,
        "ranking_rule": "Hard-gate failures are eliminated first; survivors sort by fewer warning codes, vendor feasibility, classification, then candidate id.",
        "candidates": survivors + eliminated,
        "status": "FOUND" if evaluated else INSUFFICIENT_DATA,
    }

