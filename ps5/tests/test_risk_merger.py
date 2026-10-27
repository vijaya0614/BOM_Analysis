from src.models import PartRiskProfile
from src.risk_merger import merge_risk_data, derive_criticality

def test_derive_criticality():
    p1 = PartRiskProfile(part_number="P1", lifecycle_status="Obsolete", has_second_source=False)
    assert derive_criticality(p1) == "High"
    
    p2 = PartRiskProfile(part_number="P2", lifecycle_status="NRND", has_second_source=False)
    assert derive_criticality(p2) == "High"
    
    p3 = PartRiskProfile(part_number="P3", lifecycle_status="Active", has_second_source=False)
    assert derive_criticality(p3) == "Medium"
    
    p4 = PartRiskProfile(part_number="P4", lifecycle_status="Active", has_second_source=True)
    assert derive_criticality(p4) == "Low"

def test_merge_risk_data(tmp_path):
    # Setup temporary CSV data files
    (tmp_path / "lifecycle.csv").write_text("Part Number,Lifecycle Status\nP1,Obsolete\nP2,Active\n", encoding="utf-8")
    (tmp_path / "lead_times.csv").write_text("Part Number,Lead Time Weeks\nP1,52\nP2,4\n", encoding="utf-8")
    (tmp_path / "stock.csv").write_text("Part Number,Stock\nP1,0\nP2,50000\n", encoding="utf-8")
    (tmp_path / "second_source.csv").write_text("Part Number,Has Second Source\nP1,False\nP2,True\n", encoding="utf-8")
    (tmp_path / "criticality.csv").write_text("Part Number,Criticality\nP2,Low\n", encoding="utf-8")  # P1 omitted to test derivation
    
    profiles = [
        PartRiskProfile(part_number="P1", qty=1),
        PartRiskProfile(part_number="P2", qty=10),
        PartRiskProfile(part_number="P3_UNKNOWN", qty=1)
    ]
    
    merged = merge_risk_data(profiles, str(tmp_path))
    
    # P1 audit
    p1 = merged[0]
    assert p1.lifecycle_status == "Obsolete"
    assert p1.lead_time_weeks == 52
    assert p1.stock == 0
    assert p1.has_second_source is False
    assert p1.criticality == "High"
    assert p1.criticality_derived is True
    assert p1.confidence_score >= 0.8  # 4/5 explicit + dynamic taxonomy confidence
    
    # P2 audit
    p2 = merged[1]
    assert p2.lifecycle_status == "Active"
    assert p2.confidence_score == 1.0
    assert p2.criticality_derived is False
    
    # P3_UNKNOWN audit
    p3 = merged[2]
    assert len(p3.missing_fields) == 5
    assert round(p3.confidence_score, 2) == 0.70
