from src.candidate_orchestrator import evaluate_candidate_decision
from src.models import ComponentSpec


def test_hard_gate_failure_is_eliminated_before_soft_ranking(monkeypatch):
    original = ComponentSpec("U2", "ORIGINAL", "microcontroller", refdes="U2")
    passing = ComponentSpec("PASSING", "PASSING", "microcontroller")
    failing = ComponentSpec("FAILING", "FAILING", "microcontroller")

    monkeypatch.setattr("src.candidate_orchestrator._risk_trigger", lambda *_: {"status": "FOUND"})
    monkeypatch.setattr("src.candidate_orchestrator.get_downstream_impact", lambda *_args, **_kwargs: {"status": "FOUND"})
    # Keep this unit test focused on hard-gate ordering.  Industry resolution
    # has separate integration coverage and must not replace these fakes.
    monkeypatch.setattr("src.candidate_orchestrator.resolve_industry_component", lambda *_: None)
    monkeypatch.setattr("src.candidate_orchestrator.is_industry_product", lambda *_: False)
    monkeypatch.setattr(
        "src.candidate_orchestrator.find_component",
        lambda identifier: {"U2": original, "PASSING": passing, "FAILING": failing}.get(identifier),
    )
    monkeypatch.setattr(
        "src.candidate_orchestrator.recommend_substitutes",
        lambda *_: {"candidates": [{"component": passing.to_dict()}, {"component": failing.to_dict()}]},
    )

    def fake_evaluate(_product, _target, _original, candidate):
        hard_failure = candidate.component_id == "FAILING"
        return {
            "candidate_id": candidate.component_id,
            "candidate_part_number": candidate.part_number,
            "classification": "DROP_IN_CANDIDATE",
            "vendor_status": "FEASIBLE" if not hard_failure else "FAIL",
            "reason_codes": ["DROP_IN_CANDIDATE"],
            "hard_gate_failures": ["VENDOR_FAIL"] if hard_failure else [],
            "overall_status": "FAIL" if hard_failure else "PASS",
        }

    monkeypatch.setattr("src.candidate_orchestrator._evaluate_one", fake_evaluate)

    result = evaluate_candidate_decision("demo", "U2")

    assert [item["candidate_id"] for item in result["candidates"]] == ["PASSING", "FAILING"]
    assert result["candidates"][0]["rank"] == 1
    assert result["candidates"][1]["rank"] is None
    assert result["candidates"][1]["ranking_rule"].startswith("eliminated")
