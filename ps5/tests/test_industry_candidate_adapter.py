from src.candidate_orchestrator import evaluate_candidate_decision
from src.industry_candidate_adapter import industry_candidates_for, resolve_industry_component, resolve_industry_model
from src.substitute_engine import recommend_industry_substitutes, recommend_substitutes


def test_beaglebone_u2_uses_real_same_package_pmic_candidate():
    original = resolve_industry_component("beaglebone-black", "U2")

    assert original is not None
    assert original.part_number == "TPS65217C"
    assert original.lifecycle_status in {"UNKNOWN", "UNCONFIRMED"}
    assert resolve_industry_model(original.component_id).part_number == "TPS65217C"
    assert [candidate.part_number for candidate in industry_candidates_for(original)] == ["TPS65218D0RSLR"]

    result = recommend_industry_substitutes("beaglebone-black", "U2")
    candidate = result["candidates"][0]
    assert candidate["part_number"] == "TPS65218D0RSLR"
    assert candidate["compatibility_score"] == 70
    assert candidate["confidence_score"] == 70
    assert candidate["evidence_summary"]["unknown_count"] == 2


def test_industry_catch_all_category_requires_shared_function_identity():
    original = resolve_industry_component("beaglebone-black", "U11")

    assert original is not None
    assert original.part_number == "IT66122FN/CX"
    # U11 is stored under the broad ETC category.  Only a real HDMI model is
    # returned, not unrelated ETC rows.
    assert [candidate.part_number for candidate in industry_candidates_for(original)] == ["TDA19988BHN/C1"]


def test_candidate_orchestrator_uses_industry_pool_and_demo_pool_remains_unchanged():
    industry = evaluate_candidate_decision("beaglebone-black", "U2")
    assert industry["candidate_generation"]["explanation_source"] == "normalized_industry_models"
    assert [candidate["candidate_part_number"] for candidate in industry["candidates"]][:1] == ["TPS65218D0RSLR"]

    demo = recommend_substitutes("U1")
    assert demo["explanation_source"] == "deterministic_rules"
    assert any(candidate["component"]["component_id"] == "REG_DROPIN_5V_3A" for candidate in demo["candidates"])
