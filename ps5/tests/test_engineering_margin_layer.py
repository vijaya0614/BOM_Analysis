from src.candidate_orchestrator import evaluate_candidate_decision
from src.component_intelligence import INSUFFICIENT_DATA, compare_reliability_outlook
from src.engineering_checks import (
    LIMIT_APPROACHING,
    OUT_OF_LIMIT,
    SAFE_MARGIN,
    WARNING_MARGIN,
    evaluate_operating_limit,
    evaluate_tolerance,
)


def test_operating_limit_statuses_cover_safe_warning_approaching_out_and_missing():
    assert evaluate_operating_limit(parameter="v", operating_value=5, limit_max=10)["status"] == SAFE_MARGIN
    assert evaluate_operating_limit(parameter="v", operating_value=8.5, limit_max=10)["status"] == WARNING_MARGIN
    assert evaluate_operating_limit(parameter="v", operating_value=9.7, limit_max=10)["status"] == LIMIT_APPROACHING
    assert evaluate_operating_limit(parameter="v", operating_value=11, limit_max=10)["status"] == OUT_OF_LIMIT
    assert evaluate_operating_limit(parameter="v", operating_value=None, limit_max=10)["status"] == INSUFFICIENT_DATA
    assert evaluate_operating_limit(parameter="v", operating_value=5, limit_max=None)["status"] == INSUFFICIENT_DATA


def test_operating_limit_does_not_infer_operating_value_from_rating():
    result = evaluate_operating_limit(parameter="current", limit_max=2, candidate_max=3)
    assert result["status"] == INSUFFICIENT_DATA
    assert result["reason"] == "OPERATING_VALUE_MISSING"


def test_legacy_required_range_path_reports_candidate_limit_margin():
    result = evaluate_operating_limit(parameter="v", required_min=3, required_max=3.6, candidate_min=3, candidate_max=3.6)
    assert result["status"] in {SAFE_MARGIN, LIMIT_APPROACHING}
    failing = evaluate_operating_limit(parameter="v", required_min=3, required_max=3.6, candidate_min=4, candidate_max=5)
    assert failing["status"] == OUT_OF_LIMIT
    assert failing["legacy_status"] == "FAIL"


def test_tolerance_bounds_inside_outside_and_missing():
    inside = evaluate_tolerance(parameter="resistance", candidate_nominal=1000, candidate_tolerance=5, design_value=1020, unit="ohm")
    assert inside["lower_bound"] == 950
    assert inside["upper_bound"] == 1050
    assert inside["status"] == SAFE_MARGIN

    outside = evaluate_tolerance(parameter="resistance", candidate_nominal=1000, candidate_tolerance=5, design_value=1100, unit="ohm")
    assert outside["status"] == OUT_OF_LIMIT
    assert outside["reason"] == "TOLERANCE_FAIL"

    missing = evaluate_tolerance(parameter="resistance", candidate_nominal=1000, design_value=1000, unit="ohm")
    assert missing["status"] == INSUFFICIENT_DATA


def test_reliability_outlook_is_qualitative_for_improved_unchanged_degraded_and_insufficient():
    improved = compare_reliability_outlook("IRFZ44N", "IRLZ44N")
    assert improved["outcome"] == "IMPROVED"
    assert all("last" not in item["reason"].lower() for item in improved["evidence"])

    unchanged = compare_reliability_outlook("IRLZ44N", "IRLZ44N")
    assert unchanged["outcome"] == "UNCHANGED"

    degraded = compare_reliability_outlook("IRLZ44N", "IRFZ44N")
    assert degraded["outcome"] == "DEGRADED"

    insufficient = compare_reliability_outlook("NOT-A-REAL-MPN", "IRLZ44N")
    assert insufficient["outcome"] == INSUFFICIENT_DATA


def test_candidate_orchestrator_keeps_hard_gate_authoritative_and_adds_margin_fields():
    result = evaluate_candidate_decision("demo", "U1", candidate_id="REG_BAD_3V3_1A")
    assert result["status"] == "FOUND"
    candidate = result["candidates"][0]
    assert candidate["classification"] == "INCOMPATIBLE"
    assert "CLASSIFICATION_INCOMPATIBLE" in candidate["hard_gate_failures"]
    assert candidate["rank"] is None
    assert "operating_limit_result" in candidate
    assert "tolerance_result" in candidate
    assert "operating_margin" in candidate
    assert "reliability_outlook" in candidate
    assert "confidence" in candidate
    assert "reasons" in candidate
    assert "limitations" in candidate


def test_candidate_orchestrator_decision_api_remains_backward_compatible():
    result = evaluate_candidate_decision("demo", "U1", top_n=3)
    assert "product_id" in result
    assert "target_component_id" in result
    assert "candidate_generation" in result
    assert "candidates" in result
    assert result["candidates"]
    assert "candidate_generation" in result["candidates"][0]
    assert "vendor_gate" in result["candidates"][0]
    assert "engineering_gates" in result["candidates"][0]




def test_candidate_reliability_evidence_is_additive_and_traceable():
    result = evaluate_candidate_decision("demo", "U1", candidate_id="REG_DROPIN_5V_3A")
    candidate = result["candidates"][0]
    assert candidate["classification"] == "INSUFFICIENT_EVIDENCE"
    assert candidate["overall_status"] == "INSUFFICIENT_DATA"
    assert candidate["drop_in_evidence"]["status"] == "INSUFFICIENT_DATA"
    assert candidate["rank"] == 1
    assert candidate["reliability_outlook"]["outcome"] == "IMPROVED"
    assert candidate["reliability_confidence"] == "MEDIUM"
    evidence = candidate["reliability_evidence"]["evidence_items"]
    assert any(item["source_type"] == "SUPPLY_CHAIN_DATA" for item in evidence)
    assert any(item["source_type"] == "SYNTHETIC_CATALOG_LIMIT_PLUS_SYNTHETIC_DEMO_OPERATING_VALUE" for item in evidence)
    assert all("predicted_lifetime" not in item for item in evidence)


def test_reliability_does_not_override_incompatible_hard_gate():
    result = evaluate_candidate_decision("demo", "U1", candidate_id="REG_BAD_3V3_1A")
    candidate = result["candidates"][0]
    assert candidate["classification"] == "INCOMPATIBLE"
    assert candidate["overall_status"] == "FAIL"
    assert candidate["rank"] is None
    assert "CLASSIFICATION_INCOMPATIBLE" in candidate["hard_gate_failures"]
    assert candidate["reliability_outlook"]["outcome"] == "DEGRADED"
if __name__ == "__main__":
    for name, func in sorted(globals().items()):
        if name.startswith("test_"):
            func()
    print("focused engineering margin tests passed")
