from src.drop_in_evidence import assess_payload_drop_in_evidence
from src.models import ComponentSpec
from src.substitute_engine import DROP_IN, INSUFFICIENT_EVIDENCE_CLASSIFICATION, evaluate_candidate
from src.substitute_hard_gate import evaluate_candidate_substitutes


def _citation(value):
    return {
        "source_id": f"SRC-{value}",
        "source_title": "Manufacturer datasheet",
        "source_url": "https://manufacturer.example/datasheet.pdf",
        "source_page": "4",
        "confidence": "HIGH",
        "source_type": "MANUFACTURER_DATASHEET",
        "evidence_summary": str(value),
    }


def _payload_spec(part_number, evidence=True):
    result = {
        "part_number": part_number,
        "category": "generic",
        "package": "SOIC-8",
        "pinout": "1=IN,2=GND",
        "voltage_rating_v": 12,
    }
    if evidence:
        result["evidence"] = {
            "package": _citation("SOIC-8"),
            "pinout": _citation("1=IN,2=GND"),
            "ratings": {"voltage_rating": _citation(12)},
        }
    return result


def test_drop_in_evidence_requires_source_for_package_pinout_and_rating():
    original = _payload_spec("ORIGINAL", evidence=False)
    candidate = _payload_spec("CANDIDATE", evidence=False)

    result = assess_payload_drop_in_evidence(original, candidate, ["voltage_rating"])

    assert result["status"] == "INSUFFICIENT_DATA"
    assert set(result["unknown_parameters"]) == {"package", "pinout", "voltage_rating"}
    assert result["requirements"][0]["original"]["value"] == "SOIC-8"


def test_traceable_matching_evidence_supports_drop_in_gate():
    result = assess_payload_drop_in_evidence(
        _payload_spec("ORIGINAL"),
        _payload_spec("CANDIDATE"),
        ["voltage_rating"],
    )

    assert result["status"] == "SUPPORTED"
    assert result["unknown_parameters"] == []
    assert result["requirements"][1]["candidate"]["source"]["source_url"].endswith("datasheet.pdf")


def test_hard_gate_engine_does_not_promote_uncited_values_to_drop_in():
    original = _payload_spec("ORIGINAL", evidence=False)
    candidate = _payload_spec("CANDIDATE", evidence=False)

    evaluated = evaluate_candidate_substitutes(original, [candidate])[0]

    assert evaluated.classification == INSUFFICIENT_EVIDENCE_CLASSIFICATION
    assert evaluated.is_drop_in_eligible is False
    assert evaluated.ranking is None
    assert evaluated.drop_in_evidence["unknown_parameters"]


def test_hard_gate_engine_accepts_source_cited_matching_values():
    original = _payload_spec("ORIGINAL")
    candidate = _payload_spec("CANDIDATE")
    for spec in (original, candidate):
        spec.update({"category": "generic", "operating_voltage_max": 12, "operating_current_max": 1, "operating_temperature_max": 85})
        spec["evidence"]["ratings"] = {
            "voltage_rating": _citation(12),
            "current_rating": _citation(1),
            "temperature_rating": _citation(85),
        }

    evaluated = evaluate_candidate_substitutes(original, [candidate])[0]

    assert evaluated.classification == DROP_IN
    assert evaluated.is_drop_in_eligible is True
    assert evaluated.drop_in_evidence["status"] == "SUPPORTED"


def test_demo_catalog_value_match_is_not_traceable_evidence():
    original = ComponentSpec(
        component_id="ORIG", part_number="ORIG-MPN", category="resistor", package="0805",
        specs={"resistance_ohms": 10000, "tolerance_pct": 1, "power_w": 0.125, "pinout": "2-terminal"}, demo_data=True,
    )
    candidate = ComponentSpec(
        component_id="CAND", part_number="CAND-MPN", category="resistor", package="0805",
        specs={"resistance_ohms": 10000, "tolerance_pct": 1, "power_w": 0.25, "pinout": "2-terminal"}, demo_data=True,
    )

    result = evaluate_candidate(original, candidate)

    assert result["classification"] == INSUFFICIENT_EVIDENCE_CLASSIFICATION
    assert result["drop_in_evidence"]["status"] == "INSUFFICIENT_DATA"
    assert {"package", "pinout"}.issubset(result["drop_in_evidence"]["unknown_parameters"])
    assert result["drop_in_evidence"]["requirements"][0]["original"]["value"] == "0805"


def test_exact_mpn_sources_that_cite_values_support_drop_in(monkeypatch):
    original = ComponentSpec(
        component_id="ORIG", part_number="ORIG-MPN", category="resistor", package="0805",
        specs={"resistance_ohms": 10000, "tolerance_pct": 1, "power_w": 0.125, "pinout": "2-terminal"},
    )
    candidate = ComponentSpec(
        component_id="CAND", part_number="CAND-MPN", category="resistor", package="0805",
        specs={"resistance_ohms": 10000, "tolerance_pct": 1, "power_w": 0.25, "pinout": "2-terminal"},
    )
    records = []
    for mpn, package, pinout, power in (
        ("ORIG-MPN", "0805", "2-terminal resistor", "0.125 W"),
        ("CAND-MPN", "0805", "2-terminal resistor", "0.25 W"),
    ):
        for field, value in (("package", package), ("pinout", pinout), ("resistance", "10000 ohm"), ("power rating", power)):
            records.append({
                "mpn": mpn,
                "source_id": f"SRC-{mpn}-{field}",
                "source_title": "Manufacturer datasheet",
                "source_url": "https://manufacturer.example/datasheet.pdf",
                "source_page": "4",
                "source_type": "MANUFACTURER_DATASHEET",
                "parameter_supported": field,
                "evidence_summary": value,
                "confidence": "HIGH",
            })
    monkeypatch.setattr("src.drop_in_evidence._read_exact_mpn_evidence", lambda mpn: [row for row in records if row["mpn"] == mpn])

    result = evaluate_candidate(original, candidate)

    assert result["classification"] == DROP_IN
    assert result["drop_in_evidence"]["status"] == "SUPPORTED"
