from src.component_catalog import find_component
from src.compatibility_rules import run_compatibility_checks
from src.models import ComponentSpec
from src.risk_report_bridge import substitutes_for_risk_report
from src.substitute_api import get_component, search_substitutes
from src.substitute_engine import (
    DROP_IN,
    INCOMPATIBLE_CLASSIFICATION,
    REQUIRES_REDESIGN,
    compare_components,
    evaluate_candidate,
    recommend_substitutes,
)


def test_regulator_drop_in_classification():
    result = compare_components("U1", "REG_DROPIN_5V_3A")
    candidate = result["candidate"]
    assert candidate["classification"] == DROP_IN
    assert candidate["compatibility_score"] >= 95
    assert candidate["confidence_score"] == 100
    assert candidate["insufficient_evidence"] is False
    assert "output_voltage_v" in candidate["matched_parameters"]
    assert not candidate["mismatched_parameters"]


def test_regulator_package_mismatch_requires_redesign():
    result = compare_components("U1", "REG_REDESIGN_5V_3A")
    candidate = result["candidate"]
    assert candidate["classification"] == REQUIRES_REDESIGN
    assert "package" in candidate["mismatched_parameters"]
    assert any(check["impact"] == "REDESIGN_REQUIRED" for check in candidate["checks"])


def test_regulator_voltage_and_current_mismatch_incompatible():
    result = compare_components("U1", "REG_BAD_3V3_1A")
    candidate = result["candidate"]
    assert candidate["classification"] == INCOMPATIBLE_CLASSIFICATION
    assert "output_voltage_v" in candidate["mismatched_parameters"]
    assert "output_current_a" in candidate["mismatched_parameters"]


def test_resistor_tolerance_and_package_checks():
    original = find_component("R1")
    drop_in = find_component("RES_DROPIN_10K")
    redesign = find_component("RES_REDESIGN_10K")

    drop_result = evaluate_candidate(original, drop_in)
    redesign_result = evaluate_candidate(original, redesign)

    assert drop_result["classification"] == DROP_IN
    assert "tolerance_pct" in drop_result["matched_parameters"]
    assert redesign_result["classification"] == REQUIRES_REDESIGN
    assert "package" in redesign_result["mismatched_parameters"]


def test_mosfet_gate_drive_and_current_incompatible():
    result = compare_components("Q1", "FET_BAD_LOGIC")
    candidate = result["candidate"]
    assert candidate["classification"] == INCOMPATIBLE_CLASSIFICATION
    assert "gate_drive_voltage_v" in candidate["mismatched_parameters"]
    assert "id_a" in candidate["mismatched_parameters"]


def test_single_source_and_eol_candidate_rank_below_healthy_drop_in():
    response = recommend_substitutes("U1")
    candidates = response["candidates"]
    drop_in = next(c for c in candidates if c["component"]["component_id"] == "REG_DROPIN_5V_3A")
    eol = next(c for c in candidates if c["component"]["component_id"] == "REG_EOL_COMPAT")
    assert drop_in["rank"] < eol["rank"]
    assert eol["supply_chain_score"] < drop_in["supply_chain_score"]


def test_incompatible_candidates_can_be_filtered_out():
    response = recommend_substitutes("U1", include_incompatible=False)
    assert all(c["classification"] != INCOMPATIBLE_CLASSIFICATION for c in response["candidates"])


def test_incompatible_candidate_is_never_the_leading_recommendation():
    response = recommend_substitutes("U1")
    assert response["candidates"][0]["classification"] != INCOMPATIBLE_CLASSIFICATION
    assert response["recommendation_summary"]["recommended"] == response["candidates"][0]["part_number"]


def test_insufficient_data_requires_review_not_drop_in():
    original = ComponentSpec(
        component_id="ORIG_TEMP",
        part_number="TEMP-ORIG",
        category="temperature_sensor",
        package="SOT-23",
        specs={"interface": "analog"},
    )
    candidate = ComponentSpec(
        component_id="CAND_TEMP",
        part_number="TEMP-CAND",
        category="temperature_sensor",
        package="SOT-23",
        specs={"interface": "analog"},
    )

    checks = run_compatibility_checks(original, candidate)
    result = evaluate_candidate(original, candidate)

    assert any(check["status"] == "UNKNOWN" for check in checks)
    assert result["classification"] == REQUIRES_REDESIGN
    assert result["confidence_score"] < 100
    assert result["insufficient_evidence"] is True
    assert result["evidence_summary"]["unknown_count"] > 0
    assert result["unknown_parameters"]


def test_api_facade_component_and_search():
    component = get_component("U1")
    assert component["component"]["physical_location"] == "REGULATOR_1"

    response = search_substitutes({"component_id": "U1"})
    assert response["original"]["component_id"] == "U1"
    assert response["candidates"][0]["rank"] == 1
    assert "confidence_score" in response["candidates"][0]
    assert "evidence_summary" in response["candidates"][0]
    assert response["llm_used"] is False
    assert response["vector_search_used"] is False


def test_substitute_ranking_explanation_uses_existing_scores():
    response = recommend_substitutes("U1")
    top = response["candidates"][0]

    assert "score_breakdown" in top
    assert top["score_breakdown"]["formula"] == "compatibility_score * 0.70 + supply_chain_score * 0.30 - classification_penalty"
    expected = round(
        top["compatibility_score"] * 0.70
        + top["supply_chain_score"] * 0.30
        - top["score_breakdown"]["classification_penalty"],
        2,
    )
    assert top["ranking_score"] == expected
    assert top["ranking_reason"]
    assert top["why_ranked_here"]
    assert top["why_not_ranked_higher"] == "Already highest-ranked candidate."
    assert response["recommendation_summary"]["recommended"] == top["part_number"]


def test_lower_rank_explains_why_not_ranked_higher():
    response = recommend_substitutes("U1")
    second = response["candidates"][1]

    assert second["rank"] == 2
    assert "why_not_ranked_higher" in second
    assert response["candidates"][0]["part_number"] in second["why_not_ranked_higher"]


def test_missing_data_is_exposed_in_ranking_factors():
    original = ComponentSpec(
        component_id="ORIG_TEMP",
        part_number="TEMP-ORIG",
        category="temperature_sensor",
        package="SOT-23",
        specs={"interface": "analog"},
    )
    candidate = ComponentSpec(
        component_id="CAND_TEMP",
        part_number="TEMP-CAND",
        category="temperature_sensor",
        package="SOT-23",
        specs={"interface": "analog"},
    )

    result = evaluate_candidate(original, candidate)

    assert result["unknown_factors"]
    assert any(factor["factor"] == "lead_time_weeks" for factor in result["unknown_factors"])
    assert result["insufficient_evidence"] is True


def test_catalog_contains_named_mcu_parts():
    assert find_component("STM32F401RCT6") is not None
    assert find_component("ESP32-S3-WROOM-1") is not None


def test_mini_fan_controller_catalog_coverage():
    for part_number in [
        "NE555P",
        "L298N-DRIVER",
        "RES-10K-0201",
        "CAP-100NF-0603",
        "TBD-FET-OPTIONAL",
        "DHT11-TEMP-HUM",
        "SW-PUSH-6MM",
    ]:
        assert find_component(part_number) is not None


def test_smart_cooling_support_catalog_coverage():
    for part_number in [
        "LED-5MM-RED",
        "LED-5MM-BLUE",
        "FAN-12V-40MM",
        "TERM-BLOCK-5MM-2P",
    ]:
        assert find_component(part_number) is not None


def test_added_component_categories_have_substitutes():
    assert recommend_substitutes("NE555P")["candidates"]
    assert recommend_substitutes("L298N-DRIVER")["candidates"]
    assert recommend_substitutes("LED-5MM-RED")["candidates"]
    assert recommend_substitutes("FAN-12V-40MM")["candidates"]
    assert recommend_substitutes("TERM-BLOCK-5MM-2P")["candidates"]


def test_person1_risk_report_bridge_maps_catalog_parts():
    response = substitutes_for_risk_report("outputs/risk_analysis_mini_smart_cooling_controller.json")
    assert "error" not in response
    assert response["mapped_count"] >= 6
    mapped_part_numbers = {item["resolved_part_number"] for item in response["mapped"]}
    assert "REG-5V-BUCK-01" in mapped_part_numbers
    assert "ESP32-WROOM-32U" in mapped_part_numbers
    assert "NMOS-FAN-01" in mapped_part_numbers
