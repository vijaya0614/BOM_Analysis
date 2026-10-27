from src.models import PartRiskProfile
from src.risk_analyzer import (
    prioritize_by_severity,
    prioritize_by_exposure,
    group_by_band,
    compute_summary_metrics
)

def test_prioritization_severity_vs_exposure():
    # Part A: High risk (0.90), Qty 1 -> Exposure 0.90
    p1 = PartRiskProfile(part_number="PART_A", qty=1, risk_score=0.90, exposure_score=0.90, risk_band="Critical")
    # Part B: Moderate risk (0.60), Qty 500 -> Exposure 300.0
    p2 = PartRiskProfile(part_number="PART_B", qty=500, risk_score=0.60, exposure_score=300.0, risk_band="High")
    
    profiles = [p1, p2]
    
    by_sev = prioritize_by_severity(profiles)
    assert by_sev[0].part_number == "PART_A"
    
    by_exp = prioritize_by_exposure(profiles)
    assert by_exp[0].part_number == "PART_B"

def test_group_by_band():
    p1 = PartRiskProfile(part_number="P1", risk_band="Critical")
    p2 = PartRiskProfile(part_number="P2", risk_band="Low")
    p3 = PartRiskProfile(part_number="P3", risk_band="Low")
    
    groups = group_by_band([p1, p2, p3])
    assert len(groups["Critical"]) == 1
    assert len(groups["Low"]) == 2
    assert len(groups["High"]) == 0

def test_compute_summary_metrics():
    profiles = [
        PartRiskProfile(part_number="P1", qty=2, risk_score=0.90, risk_band="Critical", confidence_score=1.0),
        PartRiskProfile(part_number="P2", qty=5, risk_score=0.20, risk_band="Low", confidence_score=0.8)
    ]
    
    metrics = compute_summary_metrics(profiles)
    assert metrics["total_parts"] == 2
    assert metrics["total_component_count"] == 7
    assert metrics["critical_count"] == 1
    assert metrics["low_count"] == 1
    assert metrics["overall_bom_risk_band"] == "Critical"
    assert metrics["average_confidence_score"] == 0.9
