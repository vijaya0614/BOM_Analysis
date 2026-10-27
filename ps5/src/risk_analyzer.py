from typing import List, Dict, Any
from src.models import PartRiskProfile

def prioritize_by_severity(profiles: List[PartRiskProfile]) -> List[PartRiskProfile]:
    """Sort profiles descending by risk score."""
    return sorted(profiles, key=lambda p: (p.risk_score or 0.0, p.qty), reverse=True)

def prioritize_by_exposure(profiles: List[PartRiskProfile]) -> List[PartRiskProfile]:
    """Sort profiles descending by exposure score (risk_score * qty)."""
    return sorted(profiles, key=lambda p: (p.exposure_score or 0.0, p.risk_score or 0.0), reverse=True)

def prioritize_by_financial_exposure(profiles: List[PartRiskProfile]) -> List[PartRiskProfile]:
    """Sort profiles descending by financial cost-at-risk ($ exposure)."""
    return sorted(profiles, key=lambda p: (p.financial_exposure_usd or 0.0, p.risk_score or 0.0), reverse=True)

def group_by_band(profiles: List[PartRiskProfile]) -> Dict[str, List[PartRiskProfile]]:
    """Group profiles by risk band."""
    groups: Dict[str, List[PartRiskProfile]] = {
        "Critical": [],
        "High": [],
        "Medium": [],
        "Low": []
    }
    for p in profiles:
        band = p.risk_band or "Low"
        if band in groups:
            groups[band].append(p)
        else:
            groups.setdefault(band, []).append(p)
    return groups

def compute_summary_metrics(profiles: List[PartRiskProfile]) -> Dict[str, Any]:
    """Computes overall BOM supply chain risk metrics, aggregate financial exposure, and health summary."""
    if not profiles:
        return {
            "total_parts": 0,
            "total_component_count": 0,
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "average_risk_score": 0.0,
            "overall_bom_risk_band": "Low",
            "average_confidence_score": 1.0,
            "total_bom_unit_cost_usd": 0.0,
            "total_financial_exposure_usd": 0.0
        }
    
    total_parts = len(profiles)
    total_component_count = sum(p.qty for p in profiles)
    
    bands = [p.risk_band for p in profiles]
    critical_count = bands.count("Critical")
    high_count = bands.count("High")
    medium_count = bands.count("Medium")
    low_count = bands.count("Low")
    
    scored = [p.risk_score for p in profiles if p.risk_score is not None]
    avg_confidence = sum(p.confidence_score for p in profiles) / total_parts
    insufficient_count = sum(1 for p in profiles if str(p.risk_band or "").upper() == "INSUFFICIENT_DATA")

    total_bom_cost = sum((p.unit_cost_usd or 0.0) * p.qty for p in profiles)
    total_financial_exposure = sum(p.financial_exposure_usd or 0.0 for p in profiles)

    if not scored:
        avg_score = None
        overall_band = "INSUFFICIENT_DATA"
    else:
        avg_score = sum(scored) / len(scored)
        max_score = max(scored)
        if max_score >= 0.85:
            overall_band = "Critical"
        elif max_score >= 0.60:
            overall_band = "High"
        elif max_score >= 0.30:
            overall_band = "Medium"
        else:
            overall_band = "Low"
        
    return {
        "total_parts": total_parts,
        "total_component_count": total_component_count,
        "critical_count": critical_count,
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": low_count,
        "insufficient_data_count": insufficient_count,
        "average_risk_score": None if avg_score is None else round(avg_score, 3),
        "overall_bom_risk_band": overall_band,
        "average_confidence_score": round(avg_confidence, 2),
        "total_bom_unit_cost_usd": round(total_bom_cost, 2),
        "total_financial_exposure_usd": round(total_financial_exposure, 2)
    }

def analyze_bom_risk(profiles: List[PartRiskProfile]) -> Dict[str, Any]:
    """
    Performs full analysis on processed BOM profiles, returning prioritized views
    and aggregate BOM health metrics.
    """
    by_severity = prioritize_by_severity(profiles)
    by_exposure = prioritize_by_exposure(profiles)
    by_financial = prioritize_by_financial_exposure(profiles)
    grouped = group_by_band(profiles)
    metrics = compute_summary_metrics(profiles)
    
    return {
        "metrics": metrics,
        "by_severity": [p.to_dict() for p in by_severity],
        "by_exposure": [p.to_dict() for p in by_exposure],
        "by_financial_exposure": [p.to_dict() for p in by_financial],
        "grouped_by_band": {band: [p.to_dict() for p in item_list] for band, item_list in grouped.items()}
    }
