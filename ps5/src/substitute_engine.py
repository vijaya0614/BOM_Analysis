from typing import Any, Dict, List, Optional

from src.compatibility_rules import (
    INCOMPATIBLE,
    MATCH,
    MISMATCH,
    REDESIGN_REQUIRED,
    REVIEW_REQUIRED,
    UNKNOWN,
    run_compatibility_checks,
)
from src.component_intelligence import compare_reliability_outlook, final_engineering_recommendation
from src.component_catalog import build_risk_profile, candidates_for, find_component
from src.models import ComponentSpec

DROP_IN = "DROP_IN_CANDIDATE"
REQUIRES_REDESIGN = "REQUIRES_REDESIGN"
INCOMPATIBLE_CLASSIFICATION = "INCOMPATIBLE"

ADVISORY_WARNING = (
    "Substitute recommendations are rule-based advisory outputs from available data. "
    "Engineering validation, datasheet review, and prototype testing are required before production approval."
)

CLASSIFICATION_PENALTIES = {
    DROP_IN: 0,
    REQUIRES_REDESIGN: 8,
    INCOMPATIBLE_CLASSIFICATION: 35,
}


def compatibility_score(checks: List[Dict[str, Any]]) -> int:
    total = sum(check["weight"] for check in checks) or 1
    earned = 0.0
    for check in checks:
        if check["status"] == MATCH:
            earned += check["weight"]
        elif check["status"] == UNKNOWN:
            earned += check["weight"] * 0.35
        elif check["impact"] in (REDESIGN_REQUIRED, REVIEW_REQUIRED):
            earned += check["weight"] * 0.50
    return int(round((earned / total) * 100))


def evidence_confidence_score(checks: List[Dict[str, Any]]) -> int:
    """Scores how complete the evidence is, independent from compatibility."""
    total = sum(check["weight"] for check in checks) or 1
    known = sum(check["weight"] for check in checks if check["status"] != UNKNOWN)
    return int(round((known / total) * 100))


def evidence_summary(checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    matched = [check["parameter"] for check in checks if check["status"] == MATCH]
    mismatched = [check["parameter"] for check in checks if check["status"] == MISMATCH]
    unknown = [check["parameter"] for check in checks if check["status"] == UNKNOWN]
    return {
        "matched_count": len(matched),
        "mismatched_count": len(mismatched),
        "unknown_count": len(unknown),
        "matched_parameters": matched,
        "mismatched_parameters": mismatched,
        "unknown_parameters": unknown,
        "insufficient_evidence": bool(unknown),
    }


def classify_candidate(checks: List[Dict[str, Any]]) -> str:
    if any(check["impact"] == INCOMPATIBLE and check["status"] == MISMATCH for check in checks):
        return INCOMPATIBLE_CLASSIFICATION
    if any(check["impact"] in (REDESIGN_REQUIRED, REVIEW_REQUIRED) and check["status"] in (MISMATCH, UNKNOWN) for check in checks):
        return REQUIRES_REDESIGN
    return DROP_IN


def supply_chain_score(component: ComponentSpec, data_dir: str = "data") -> int:
    risk = build_risk_profile(component, data_dir)
    score = 100 - int(round((risk.risk_score or 0.5) * 100))
    return max(0, min(100, score))


def ranking_score(compat_score: int, supply_score: int, classification: str) -> float:
    penalty = CLASSIFICATION_PENALTIES.get(classification, 0)
    return round((compat_score * 0.70) + (supply_score * 0.30) - penalty, 2)


def score_breakdown(compat_score: int, supply_score: int, classification: str) -> Dict[str, Any]:
    penalty = CLASSIFICATION_PENALTIES.get(classification, 0)
    return {
        "compatibility_score": compat_score,
        "compatibility_weight": 0.70,
        "compatibility_contribution": round(compat_score * 0.70, 2),
        "supply_chain_score": supply_score,
        "supply_chain_weight": 0.30,
        "supply_chain_contribution": round(supply_score * 0.30, 2),
        "classification": classification,
        "classification_penalty": penalty,
        "final_ranking_score": ranking_score(compat_score, supply_score, classification),
        "formula": "compatibility_score * 0.70 + supply_chain_score * 0.30 - classification_penalty",
        "lifecycle_score": None,
        "lifecycle_score_note": "Lifecycle is included inside the existing supply_chain_score; no separate lifecycle-only score is exposed.",
    }


def _factor(label: str, detail: str, source: str) -> Dict[str, str]:
    return {"factor": label, "detail": detail, "source": source}


def ranking_factors(candidate: ComponentSpec, checks: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, str]]]:
    matched = [
        _factor(check["parameter"], f"{check['candidate']} satisfies required value {check['original']}", "compatibility_check")
        for check in checks
        if check["status"] == MATCH
    ]
    failed = [
        _factor(check["parameter"], f"{check['candidate']} does not satisfy required value {check['original']}", "compatibility_check")
        for check in checks
        if check["status"] == MISMATCH
    ]
    unknown = [
        _factor(check["parameter"], "Required comparison data is unavailable.", "compatibility_check")
        for check in checks
        if check["status"] == UNKNOWN
    ]

    if candidate.lifecycle_status:
        target = matched if candidate.lifecycle_status == "Active" else failed
        target.append(_factor("lifecycle_status", candidate.lifecycle_status, "component_catalog"))
    else:
        unknown.append(_factor("lifecycle_status", "Data unavailable.", "component_catalog"))

    if candidate.lead_time_weeks is None:
        unknown.append(_factor("lead_time_weeks", "Data unavailable.", "component_catalog"))
    elif candidate.lead_time_weeks >= 26:
        failed.append(_factor("lead_time_weeks", f"{candidate.lead_time_weeks} weeks", "component_catalog"))
    else:
        matched.append(_factor("lead_time_weeks", f"{candidate.lead_time_weeks} weeks", "component_catalog"))

    if candidate.stock is None:
        unknown.append(_factor("stock", "Data unavailable.", "component_catalog"))
    elif candidate.stock == 0:
        failed.append(_factor("stock", "Zero stock available.", "component_catalog"))
    elif candidate.stock < 100:
        failed.append(_factor("stock", f"Low stock: {candidate.stock}", "component_catalog"))
    else:
        matched.append(_factor("stock", f"{candidate.stock} units", "component_catalog"))

    if candidate.has_second_source is None:
        unknown.append(_factor("has_second_source", "Data unavailable.", "component_catalog"))
    elif candidate.has_second_source:
        matched.append(_factor("has_second_source", "Second source available.", "component_catalog"))
    else:
        failed.append(_factor("has_second_source", "Single-sourced.", "component_catalog"))

    return {
        "matched_factors": matched,
        "failed_factors": failed,
        "unknown_factors": unknown,
    }


def ranking_reason(result: Dict[str, Any]) -> str:
    matched = result["matched_parameters"]
    mismatched = result["mismatched_parameters"]
    unknown = result["unknown_parameters"]
    breakdown = result["score_breakdown"]
    pieces = [
        f"Ranking score {result['ranking_score']} uses {breakdown['formula']}.",
        f"Compatibility contributes {breakdown['compatibility_contribution']} from score {result['compatibility_score']}.",
        f"Supply chain contributes {breakdown['supply_chain_contribution']} from score {result['supply_chain_score']}.",
    ]
    if breakdown["classification_penalty"]:
        pieces.append(f"Classification penalty subtracts {breakdown['classification_penalty']} for {result['classification']}.")
    if matched:
        pieces.append(f"Matched: {', '.join(matched)}.")
    if mismatched:
        pieces.append(f"Mismatched: {', '.join(mismatched)}.")
    if unknown:
        pieces.append(f"Unknown: {', '.join(unknown)}.")
    return " ".join(pieces)


def add_rank_explanations(results: List[Dict[str, Any]]) -> None:
    for idx, result in enumerate(results):
        result["rank"] = idx + 1
        if idx == 0:
            result["why_ranked_here"] = (
                f"Ranked #1 because it has the highest existing ranking_score ({result['ranking_score']}) "
                "after compatibility, supply-chain score, and classification penalty are applied."
            )
            result["why_not_ranked_higher"] = "Already highest-ranked candidate."
            continue

        previous = results[idx - 1]
        reasons = []
        if result["ranking_score"] < previous["ranking_score"]:
            reasons.append(f"lower ranking score ({result['ranking_score']} vs {previous['ranking_score']})")
        if result["compatibility_score"] < previous["compatibility_score"]:
            reasons.append(f"lower compatibility score ({result['compatibility_score']} vs {previous['compatibility_score']})")
        if result["supply_chain_score"] < previous["supply_chain_score"]:
            reasons.append(f"lower supply-chain score ({result['supply_chain_score']} vs {previous['supply_chain_score']})")
        if result["score_breakdown"]["classification_penalty"] > previous["score_breakdown"]["classification_penalty"]:
            reasons.append(
                f"larger classification penalty ({result['score_breakdown']['classification_penalty']} vs "
                f"{previous['score_breakdown']['classification_penalty']})"
            )
        if not reasons:
            reasons.append("deterministic tie-breaker order after equal ranking factors")

        result["why_ranked_here"] = f"Ranked #{idx + 1} after {previous['part_number']} using the existing ranking sort."
        result["why_not_ranked_higher"] = f"Not ranked above {previous['part_number']} due to " + "; ".join(reasons) + "."


def recommendation_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not results:
        return {
            "recommended": None,
            "why_recommended": "No verified substitute found.",
            "why_next_not_selected": None,
        }

    top = results[0]
    next_candidate = results[1] if len(results) > 1 else None
    summary = {
        "recommended": top["part_number"],
        "why_recommended": top["why_ranked_here"],
        "why_next_not_selected": None,
    }
    if next_candidate:
        summary["next_candidate"] = next_candidate["part_number"]
        summary["why_next_not_selected"] = next_candidate["why_not_ranked_higher"]
    return summary


def generate_explanation(original: ComponentSpec, candidate: ComponentSpec, result: Dict[str, Any]) -> str:
    matched = result["matched_parameters"]
    mismatched = result["mismatched_parameters"]
    unknown = result["unknown_parameters"]
    classification = result["classification"]

    if classification == DROP_IN:
        opening = f"{candidate.part_number} is ranked as a drop-in candidate for {original.part_number}"
    elif classification == REQUIRES_REDESIGN:
        opening = f"{candidate.part_number} may replace {original.part_number}, but redesign or review is required"
    else:
        opening = f"{candidate.part_number} is not a suitable substitute for {original.part_number}"

    details = []
    if matched:
        details.append(f"matched {', '.join(matched)}")
    if mismatched:
        details.append(f"mismatched {', '.join(mismatched)}")
    if unknown:
        details.append(f"has insufficient data for {', '.join(unknown)}")

    supply = (
        f"Supply-chain status: lifecycle={candidate.lifecycle_status or 'unknown'}, "
        f"lead_time_weeks={candidate.lead_time_weeks if candidate.lead_time_weeks is not None else 'unknown'}, "
        f"stock={candidate.stock if candidate.stock is not None else 'unknown'}, "
        f"second_source={candidate.has_second_source if candidate.has_second_source is not None else 'unknown'}."
    )
    confidence = f"Evidence confidence is {result['confidence_score']}/100."
    return f"{opening} because it {('; '.join(details) if details else 'has no comparable specification data')}. {confidence} {supply}"


def evaluate_candidate(original: ComponentSpec, candidate: ComponentSpec, data_dir: str = "data") -> Dict[str, Any]:
    checks = run_compatibility_checks(original, candidate)
    compat = compatibility_score(checks)
    confidence = evidence_confidence_score(checks)
    evidence = evidence_summary(checks)
    classification = classify_candidate(checks)
    supply = supply_chain_score(candidate, data_dir)
    breakdown = score_breakdown(compat, supply, classification)
    factors = ranking_factors(candidate, checks)

    result = {
        "component": candidate.to_dict(),
        "part_number": candidate.part_number,
        "compatibility_score": compat,
        "confidence_score": confidence,
        "supply_chain_score": supply,
        "ranking_score": breakdown["final_ranking_score"],
        "score_breakdown": breakdown,
        "classification": classification,
        "checks": checks,
        "evidence_summary": evidence,
        "insufficient_evidence": evidence["insufficient_evidence"],
        "matched_parameters": evidence["matched_parameters"],
        "mismatched_parameters": evidence["mismatched_parameters"],
        "unknown_parameters": evidence["unknown_parameters"],
        "lifecycle": candidate.lifecycle_status,
        "lead_time_weeks": candidate.lead_time_weeks,
        "stock": candidate.stock,
        "has_second_source": candidate.has_second_source,
        "matched_factors": factors["matched_factors"],
        "failed_factors": factors["failed_factors"],
        "unknown_factors": factors["unknown_factors"],
    }
    reliability_outlook = compare_reliability_outlook(original.part_number, candidate.part_number)
    final_recommendation = final_engineering_recommendation(original.part_number, candidate.part_number, classification)
    result["reliability_outlook"] = reliability_outlook
    result["final_engineering_recommendation"] = final_recommendation
    result["explanation"] = generate_explanation(original, candidate, result)
    result["ranking_reason"] = ranking_reason(result)
    return result


def recommend_substitutes(
    component_id: str,
    catalog_path: str = "data/component_specs.csv",
    data_dir: str = "data",
    include_incompatible: bool = True,
) -> Dict[str, Any]:
    original = find_component(component_id, catalog_path)
    if original is None:
        return {
            "error": "COMPONENT_NOT_FOUND",
            "message": f"No component found for identifier '{component_id}'.",
        }

    results = [
        evaluate_candidate(original, candidate, data_dir)
        for candidate in candidates_for(original, catalog_path)
    ]
    if not include_incompatible:
        results = [r for r in results if r["classification"] != INCOMPATIBLE_CLASSIFICATION]

    results.sort(key=lambda r: (r["ranking_score"], r["compatibility_score"], r["supply_chain_score"]), reverse=True)
    # Electrical/package incompatibility is a hard constraint.  Keep such
    # candidates available for audit when requested, but never let stock or
    # price-driven supply scoring make one the leading recommendation.
    compatible = [item for item in results if item["classification"] != INCOMPATIBLE_CLASSIFICATION]
    incompatible = [item for item in results if item["classification"] == INCOMPATIBLE_CLASSIFICATION]
    results = compatible + incompatible
    add_rank_explanations(results)

    return {
        "original": original.to_dict(),
        "candidates": results,
        "recommendation_summary": recommendation_summary(results),
        "advisory_warning": ADVISORY_WARNING,
        "explanation_source": "deterministic_rules",
        "llm_used": False,
        "vector_search_used": False,
    }


def recommend_industry_substitutes(product_id: str, reference_designator: str, data_dir: str = "data") -> Dict[str, Any]:
    """Generate candidates from normalized industry models, never the demo catalog."""
    from src.industry_candidate_adapter import industry_candidates_for, resolve_industry_component

    original = resolve_industry_component(product_id, reference_designator)
    if original is None:
        return {
            "error": "COMPONENT_NOT_FOUND",
            "message": f"No normalized component is available for {product_id}/{reference_designator}.",
        }
    candidates = industry_candidates_for(original)
    results = [evaluate_candidate(original, candidate, data_dir) for candidate in candidates]
    results.sort(key=lambda result: (result["ranking_score"], result["compatibility_score"], result["supply_chain_score"]), reverse=True)
    compatible = [item for item in results if item["classification"] != INCOMPATIBLE_CLASSIFICATION]
    incompatible = [item for item in results if item["classification"] == INCOMPATIBLE_CLASSIFICATION]
    results = compatible + incompatible
    add_rank_explanations(results)
    return {
        "original": original.to_dict(),
        "candidates": results,
        "recommendation_summary": recommendation_summary(results),
        "advisory_warning": ADVISORY_WARNING,
        "explanation_source": "normalized_industry_models",
        "llm_used": False,
        "vector_search_used": False,
    }


def compare_components(original_id: str, candidate_id: str, catalog_path: str = "data/component_specs.csv", data_dir: str = "data") -> Dict[str, Any]:
    original = find_component(original_id, catalog_path)
    candidate = find_component(candidate_id, catalog_path)
    if original is None or candidate is None:
        return {
            "error": "COMPONENT_NOT_FOUND",
            "message": "Original or candidate component identifier was not found.",
        }
    return {
        "original": original.to_dict(),
        "candidate": evaluate_candidate(original, candidate, data_dir),
        "advisory_warning": ADVISORY_WARNING,
    }
