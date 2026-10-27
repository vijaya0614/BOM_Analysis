"""Unit tests for industry BOM ingestion, MPN resolver, provenance, and vendor feasibility."""

from src.industry_data.data_quality import run_quality
from src.industry_data.mpn_resolver import normalize_mpn, resolve_mpn
from src.component_catalog import build_risk_profile
from src.models import ComponentSpec
from src.vendor_feasibility import INSUFFICIENT_DATA, evaluate_vendor_feasibility


def test_normalize_mpn():
    assert normalize_mpn(" TPS65217C ") == "TPS65217C"
    assert normalize_mpn("AM3358BZCZ100/A") == "AM3358BZCZ100/A"


def test_resolve_mpn():
    res = resolve_mpn("TPS65217C", "Texas Instruments")
    assert res.normalized_mpn == "TPS65217C"
    assert res.normalized_manufacturer == "Texas Instruments"


def test_data_quality_report():
    issues = run_quality()
    assert isinstance(issues, list)


def test_vendor_feasibility_insufficient_data():
    spec = ComponentSpec(component_id="UNK_PART_123", part_number="UNK_PART_123", category="generic")
    res = evaluate_vendor_feasibility(spec, target_region="IN")
    assert res["status"] in {INSUFFICIENT_DATA, "FAIL"}
    assert "reason_codes" in res


def test_industry_overlay_is_applied_before_legacy_fallback(monkeypatch):
    from src.industry_data import catalog_adapter

    def overlay(profile, region=""):
        profile.lifecycle_status = "Obsolete"
        profile.stock = 0
        profile.lead_time_weeks = 52
        profile.has_second_source = False
        profile.risk_reasons.append("Industry vendor records applied (REAL_DISTRIBUTOR_DATA)")
        return profile

    monkeypatch.setattr(catalog_adapter, "apply_industry_to_profile", overlay)
    profile = build_risk_profile(ComponentSpec(component_id="X", part_number="X", category="generic"))
    assert profile.risk_score >= 0.9
    assert any("REAL_DISTRIBUTOR_DATA" in reason for reason in profile.risk_reasons)
