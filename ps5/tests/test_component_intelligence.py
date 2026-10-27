from src.component_intelligence import (
    CLASS_LEVEL_EVIDENCE,
    INSUFFICIENT_DATA,
    build_degradation_scenario,
    compare_reliability_outlook,
    get_component_analysis,
    get_component_degradation,
    get_component_evidence,
    get_component_profile,
    get_component_reliability,
    get_operating_margins,
    final_engineering_recommendation,
    resolve_exact_mpn,
)
from src.substitute_engine import compare_components


def test_exact_mpn_lookup_for_all_supported_categories():
    supported_mpns = [
        "IRLZ44N",            # MOSFET
        "2N3904",             # Transistor
        "C1608X7R1H104K080AA",# Capacitor
        "ERJ3EKF1002V",       # Resistor
        "AMN31111",           # Motion sensor
        "PS1240P02BT",        # Buzzer
    ]
    for mpn in supported_mpns:
        resolved, _ = resolve_exact_mpn(mpn)
        assert resolved == mpn


def test_missing_mpn_returns_not_found():
    profile = get_component_profile("NOT-A-REAL-MPN")
    assert profile["status"] == "NOT_FOUND"
    assert "Evidence unavailable" in profile["limitations"][0]


def test_missing_tolerance_is_not_fabricated():
    profile = get_component_profile("BSS138")
    fields = {item["field"]: item for item in profile["data"]["electrical_profile"]}
    assert fields["tolerance"]["value"] == INSUFFICIENT_DATA


def test_tolerance_is_exposed_as_distinct_profile_section():
    profile = get_component_profile("ERJ3EKF1002V")
    tolerance_fields = profile["data"]["tolerance_profile"]
    operating_fields = profile["data"]["operating_profile"]
    assert tolerance_fields[0]["field"] == "tolerance"
    assert tolerance_fields[0]["value"] != INSUFFICIENT_DATA
    assert all(item["field"] != "tolerance" for item in operating_fields)


def test_missing_reliability_data_is_explicit():
    reliability = get_component_reliability("BSS138")
    assert reliability["summary"] == "Exact-MPN quantitative reliability data unavailable"
    assert reliability["data"][0]["fit"] == INSUFFICIENT_DATA


def test_high_confidence_evidence_is_exposed():
    evidence = get_component_evidence("IRLZ44N")
    assert evidence["status"] == "FOUND"
    assert any(row["confidence"] == "HIGH" for row in evidence["data"])


def test_missing_degradation_data_is_explicit():
    degradation = get_component_degradation("BSS138")
    assert degradation["summary"] == "Exact-MPN degradation model unavailable"
    assert degradation["data"][0]["degradation_model"] == INSUFFICIENT_DATA


def test_class_level_degradation_scenario_is_labeled():
    scenario = build_degradation_scenario("C1608X7R1H103K080AA")
    assert scenario["mode"] == CLASS_LEVEL_EVIDENCE
    assert "qualitative" in scenario["timeline"][0]["time"]


def test_reliability_outlook_uses_available_evidence_only():
    outlook = compare_reliability_outlook("IRFZ44N", "IRLZ44N")
    assert outlook["outcome"] == "IMPROVED"
    assert any(item["factor"] == "reliability_evidence" for item in outlook["evidence"])


def test_substitute_integration_keeps_existing_logic_and_adds_reliability_layer():
    result = compare_components("U1", "REG_DROPIN_5V_3A")
    candidate = result["candidate"]
    assert candidate["classification"] == "DROP_IN_CANDIDATE"
    assert "reliability_outlook" in candidate
    assert candidate["reliability_outlook"]["outcome"] == INSUFFICIENT_DATA
    assert "final_engineering_recommendation" in candidate


def test_bom_specific_identifier_without_dataset_evidence_stays_unavailable():
    analysis = get_component_analysis("U1")
    assert analysis["status"] == "NOT_FOUND"
    assert "Evidence unavailable for this MPN." in analysis["limitations"]


def test_no_fabricated_exact_mpn_rate_is_returned():
    degradation = get_component_degradation("C1608X7R1H103K080AA")
    row = degradation["data"][0]
    assert row["degradation_parameter"] == "Capacitance"
    assert row["degradation_rate"] == INSUFFICIENT_DATA


def test_operating_margin_requires_bom_specific_operating_conditions():
    margins = get_operating_margins("IRLZ44N")
    assert all(row["margin"] == INSUFFICIENT_DATA for row in margins["data"])
    assert "not treated as operating loads" in margins["limitations"][0]


def test_safe_recommendation_requires_reliability_evidence_for_both_parts():
    recommendation = final_engineering_recommendation("IRFZ44N", "IRLZ44N", "DROP_IN_CANDIDATE")
    assert recommendation["recommendation"] == "CONSIDER WITH ENGINEERING REVIEW"
    assert "not certified safe" in recommendation["reason"]
