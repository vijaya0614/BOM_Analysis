"""Regression tests for the SENTINEL industry pipeline repair."""

from __future__ import annotations

from pathlib import Path

from src.candidate_orchestrator import evaluate_candidate_decision
from src.component_catalog import find_component
from src.component_intelligence import get_component_reliability, resolve_exact_mpn
from src.engineering_checks import INSUFFICIENT_DATA, SAFE_MARGIN, evaluate_operating_limit
from src.industry_candidate_adapter import industry_candidates_for, resolve_industry_component
from src.industry_data.bom_normalizer import normalize_rows
from src.industry_data.csv_store import read_csv, write_all
from src.industry_data.enrichment_service import persist_part
from src.industry_data.identity import demo_fixture_id, is_industry_model_id, is_industry_product
from src.industry_data.importer import parse_tabular
from src.industry_data.provenance import ProvenanceStore
from src.models import PartRiskProfile
from src.providers.base import ProviderOffer, ProviderPart
from src.risk_engine import compute_risk
from src.risk_merger import merge_risk_data
from src.substitute_engine import recommend_industry_substitutes
from src.vendor_feasibility import evaluate_vendor_feasibility

ROOT = Path(__file__).resolve().parents[1]
WIRELESS_BOM = (
    ROOT
    / "data"
    / "industry"
    / "raw"
    / "beaglebone_black_wireless"
    / "extracted"
    / "5b6b89fd51d0a2b5"
    / "beaglebone-black-wireless-master"
    / "BeagleBone_Black_Wireless_BOM.csv"
)
AI_BOM = (
    ROOT
    / "data"
    / "industry"
    / "raw"
    / "beaglebone_ai"
    / "extracted"
    / "81080925bbb23e0b"
    / "beaglebone-ai-master"
    / "BeagleBone-AI_bom.csv"
)


def test_operating_limits_model_fk_resolves_or_uses_documented_mpn_join():
    models = {row["component_model_id"] for row in read_csv("component_models.csv")}
    for row in read_csv("operating_limits.csv"):
        mid = (row.get("component_model_id") or "").strip()
        if mid:
            assert is_industry_model_id(mid)
            assert mid in models
        else:
            assert (row.get("normalized_mpn") or "").strip()


def test_tolerance_model_fk_resolves_or_uses_documented_mpn_join():
    models = {row["component_model_id"] for row in read_csv("component_models.csv")}
    for row in read_csv("tolerance_records.csv"):
        mid = (row.get("component_model_id") or "").strip()
        if mid:
            assert is_industry_model_id(mid)
            assert mid in models
        else:
            assert (row.get("normalized_mpn") or "").strip()


def test_no_reg_demo_fixture_in_industry_normalized():
    for name in ("operating_limits.csv", "tolerance_records.csv", "component_models.csv", "bom_lines.csv"):
        for row in read_csv(name):
            blob = " ".join(str(value or "") for value in row.values())
            assert "REG_DROPIN" not in blob.upper()
            assert not demo_fixture_id(row.get("component_model_id") or "")


def test_beaglebone_u2_is_not_demo_esp32():
    industry = resolve_industry_component("beaglebone-black", "U2")
    demo = find_component("U2")
    assert industry is not None
    assert industry.part_number == "TPS65217C"
    assert industry.component_id.startswith("mdl_")
    assert demo is None or demo.part_number != industry.part_number
    assert (demo.part_number if demo else "") != "TPS65217C" or demo.demo_data


def test_industry_candidate_generation_uses_industry_models():
    original = resolve_industry_component("beaglebone-black", "U2")
    candidates = industry_candidates_for(original)
    assert candidates
    assert all(candidate.component_id.startswith("mdl_") for candidate in candidates)
    result = recommend_industry_substitutes("beaglebone-black", "U2")
    assert result["explanation_source"] == "normalized_industry_models"
    assert all(item["component"]["component_id"].startswith("mdl_") for item in result["candidates"])


def test_component_specs_exclude_bom_identity_columns():
    from src.industry_data.bom_normalizer import BOM_IDENTITY_ATTRIBUTES

    rows = read_csv("component_specs.csv")
    names = {(row.get("parameter_name") or "").strip() for row in rows}
    identity = {name for name in names if name.lower() in BOM_IDENTITY_ATTRIBUTES}
    assert not identity
    assert "input_voltage_min_v" in names
    assert "input_voltage_max_v" in names


def test_tps65217c_min_max_specs_survive():
    original = resolve_industry_component("beaglebone-black", "U2")
    ranges = original.specs.get("_ranges") or {}
    vin_min = ranges.get("input_voltage_min_v") or {}
    vin_max = ranges.get("input_voltage_max_v") or {}
    assert vin_min.get("min") or original.specs.get("input_voltage_min_v")
    assert vin_max.get("max") or original.specs.get("input_voltage_max_v")
    assert original.specs.get("supply_voltage_min_v") == original.specs.get("input_voltage_min_v")
    assert original.specs.get("supply_voltage_max_v") == original.specs.get("input_voltage_max_v")


def test_empty_vendor_table_is_insufficient_data():
    original = resolve_industry_component("beaglebone-black", "U1")
    gate = evaluate_vendor_feasibility(original)
    assert gate["status"] == "INSUFFICIENT_DATA"


def test_empty_lifecycle_does_not_become_active():
    original = resolve_industry_component("beaglebone-black", "U2")
    assert original.lifecycle_status not in {"Active", "ACTIVE"}
    profiles = merge_risk_data([PartRiskProfile(part_number="TPS65217C")], "data")
    assert profiles[0].lifecycle_status not in {"Active", "ACTIVE"}
    assert profiles[0].is_dynamically_inferred is False
    scored = compute_risk(profiles[0])
    if profiles[0].stock is None and profiles[0].lead_time_weeks is None:
        assert profiles[0].evidence_status == "INSUFFICIENT_DATA"
        assert scored.risk_band == "INSUFFICIENT_DATA"
    else:
        assert profiles[0].evidence_status in {"MIXED", "REAL_DATA"}
        assert scored.risk_band != "INSUFFICIENT_DATA"


def test_missing_operating_value_is_not_safe_margin():
    result = evaluate_operating_limit(parameter="vin", operating_value=None, limit_max=28)
    assert result["status"] == INSUFFICIENT_DATA
    assert result["status"] != SAFE_MARGIN
    decision = evaluate_candidate_decision("beaglebone-black", "U2")
    for candidate in decision.get("candidates", []):
        for gate in candidate.get("engineering_gates") or []:
            if gate.get("check_type") == "OPERATING_LIMIT" and gate.get("operating_value") in (None, "", INSUFFICIENT_DATA):
                assert gate.get("status") != SAFE_MARGIN


def test_industry_mpn_does_not_receive_demo_reliability():
    mpn, reasons = resolve_exact_mpn("TPS65217C")
    assert mpn is None
    assert any("industry" in item.lower() or "demo" in item.lower() for item in reasons)
    reliability = get_component_reliability("TPS65217C")
    assert reliability["status"] in {"NOT_FOUND", INSUFFICIENT_DATA}
    u2 = get_component_reliability("U2")
    assert u2["status"] in {"NOT_FOUND", INSUFFICIENT_DATA} or (
        u2.get("resolution") and "TPS65217C" not in str(u2)
    )


def test_reimporting_wireless_bom_does_not_duplicate():
    assert WIRELESS_BOM.is_file()
    rows = parse_tabular(WIRELESS_BOM)
    product_id = "beaglebone-black-wireless"
    before = len([row for row in read_csv("bom_lines.csv") if row.get("product_id") == product_id])
    normalize_rows("beaglebone_black_wireless", rows, "src_pipeline_repair_idempotent")
    after = len([row for row in read_csv("bom_lines.csv") if row.get("product_id") == product_id])
    assert after == before
    assert after == len(rows) or after >= 1


def test_wireless_bom_recognizes_combined_mpn_column():
    rows = parse_tabular(WIRELESS_BOM)
    assert len(rows) >= 20
    assert any(row.get("reference_designator") for row in rows)
    assert any(row.get("mpn") for row in rows)
    assert any(row.get("manufacturer") for row in rows)


def test_tidep_missing_designators_are_not_invented():
    rows = [row for row in read_csv("bom_lines.csv") if row.get("product_id") == "ti-tidep-0050"]
    assert rows
    empty = [row for row in rows if not (row.get("reference_designator") or "").strip()]
    assert empty, "TIDEP archive lines without a designator column must stay unresolved"
    invented = [row for row in empty if (row.get("reference_designator") or "").startswith("UNK")]
    assert not invented


def test_industry_decision_uses_actual_product_id():
    result = evaluate_candidate_decision("beaglebone-black", "U2")
    assert result["product_id"] == "beaglebone-black"
    assert result["target_component_id"] == "U2"
    other = evaluate_candidate_decision("beaglebone-ai", "U4")
    assert other["product_id"] == "beaglebone-ai"


def test_industry_substitute_routing_and_namespace_isolation():
    industry = evaluate_candidate_decision("beaglebone-black", "U2")
    assert industry["candidate_generation"]["explanation_source"] == "normalized_industry_models"
    assert industry["candidates"]
    assert all("ESP32" not in str(candidate.get("candidate_part_number") or "") for candidate in industry["candidates"])
    original = resolve_industry_component("beaglebone-black", "U2")
    assert original.part_number == "TPS65217C"
    assert not is_industry_product("demo")
    demo = find_component("U2")
    if demo is not None:
        assert demo.component_id != original.component_id


def test_successful_mocked_vendor_provider_populates_feasibility():
    original = resolve_industry_component("beaglebone-black", "U2")
    vendors = read_csv("vendor_supply_records.csv")
    vendor_master = read_csv("vendors.csv")
    snapshots = read_csv("vendor_stock_snapshots.csv")
    lifecycle = read_csv("lifecycle_records.csv")
    models = read_csv("component_models.csv")
    try:
        part = ProviderPart(
            provider="nexar",
            mpn=original.part_number,
            success=True,
            offers=[
                ProviderOffer(
                    vendor_name="Test Distributor",
                    region="IN",
                    country="IN",
                    stock_quantity=12,
                    lead_time_days=14,
                    authorized=True,
                )
            ],
        )
        stats = persist_part(part, original.component_id, "IN", "src_test_vendor", ProvenanceStore())
        assert stats["vendor_records"] >= 1
        gate = evaluate_vendor_feasibility(original, target_region="IN")
        assert gate["status"] != "INSUFFICIENT_DATA"
        assert gate["available_stock"] == 12
    finally:
        write_all("vendor_supply_records.csv", vendors)
        write_all("vendors.csv", vendor_master)
        write_all("vendor_stock_snapshots.csv", snapshots)
        write_all("lifecycle_records.csv", lifecycle)
        write_all("component_models.csv", models)
        provenance_path = ROOT / "data" / "industry" / "normalized" / "field_provenance.csv"
        if provenance_path.is_file():
            lines = provenance_path.read_text(encoding="utf-8").splitlines()
            kept = [line for line in lines if "src_test_vendor" not in line]
            provenance_path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def test_failed_provider_response_does_not_fabricate_commercial_data():
    original = resolve_industry_component("beaglebone-black", "U2")
    before = read_csv("vendor_supply_records.csv")
    part = ProviderPart(
        provider="digikey",
        mpn=original.part_number,
        success=False,
        error_code="HTTP_401",
        error_message="unauthorized",
        http_status=401,
    )
    stats = persist_part(part, original.component_id, "US", "src_test_failed_vendor", ProvenanceStore())
    assert stats["vendor_records"] == 0
    assert stats["lifecycle"] == 0
    assert read_csv("vendor_supply_records.csv") == before
    gate = evaluate_vendor_feasibility(original)
    if before:
        assert gate["status"] != "INSUFFICIENT_DATA"
    else:
        assert gate["status"] == "INSUFFICIENT_DATA"
