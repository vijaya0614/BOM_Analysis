import csv
import os
from typing import List, Dict, Optional, Any
from src.models import PartRiskProfile
from src.dynamic_data_provider import classify_mpn_taxonomy

REQUIRED_RISK_FIELDS = [
    "lifecycle_status",
    "lead_time_weeks",
    "stock",
    "has_second_source",
    "criticality"
]

def derive_criticality(profile: PartRiskProfile) -> str:
    """
    Derives component criticality when explicit label is absent based on compounding risk signals.
    """
    if profile.lifecycle_status in ["Obsolete", "NRND"] and profile.has_second_source is False:
        return "High"
    if profile.has_second_source is False:
        return "Medium"
    return "Low"

def load_csv_as_dict(filepath: str, value_col: str, transform_fn=lambda x: x) -> Dict[str, Any]:
    """Helper to read a 2-column CSV mapping Part Number -> Value."""
    result = {}
    if not os.path.exists(filepath):
        return result
    
    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            return result
        
        header_lower = [h.strip().lower() for h in headers]
        pn_idx = next((i for i, h in enumerate(header_lower) if "part" in h or "mpn" in h), 0)
        val_idx = 1 if len(header_lower) > 1 else 0
        
        for row in reader:
            if len(row) > val_idx:
                pn = row[pn_idx].strip()
                val = row[val_idx].strip()
                if pn:
                    result[pn] = transform_fn(val)
    return result

def merge_risk_data(profiles: List[PartRiskProfile], data_dir: str) -> List[PartRiskProfile]:
    """
    Merges reference datasets into BOM part profiles. If explicit CSV data is absent,
    dynamically classifies the part using taxonomy rules to synthesize accurate signals.
    Industry MPNs never receive taxonomy or legacy demo CSV values.
    """
    # Load lookup tables
    lifecycles = load_csv_as_dict(os.path.join(data_dir, "lifecycle.csv"), "Lifecycle Status")
    lead_times = load_csv_as_dict(os.path.join(data_dir, "lead_times.csv"), "Lead Time Weeks", transform_fn=lambda x: int(x) if x.isdigit() else None)
    stocks = load_csv_as_dict(os.path.join(data_dir, "stock.csv"), "Stock", transform_fn=lambda x: int(x) if x.isdigit() else None)
    second_sources = load_csv_as_dict(os.path.join(data_dir, "second_source.csv"), "Has Second Source", transform_fn=lambda x: x.lower() in ("true", "1", "yes"))
    criticalities = load_csv_as_dict(os.path.join(data_dir, "criticality.csv"), "Criticality")
    unit_costs = load_csv_as_dict(os.path.join(data_dir, "unit_costs.csv"), "Unit Cost USD", transform_fn=lambda x: float(x) if x.replace(".", "", 1).isdigit() else 1.0)
    
    from src.industry_data.catalog_adapter import apply_industry_to_profile
    from src.industry_data.identity import is_industry_mpn

    for profile in profiles:
        apply_industry_to_profile(profile)
        pn = profile.part_number
        industry = is_industry_mpn(pn or "")

        if industry:
            missing = []
            if profile.lifecycle_status in (None, "", "UNKNOWN", "INSUFFICIENT_DATA"):
                missing.append("lifecycle_status")
            if profile.lead_time_weeks is None:
                missing.append("lead_time_weeks")
            if profile.stock is None:
                missing.append("stock")
            if profile.has_second_source is None:
                missing.append("has_second_source")
            if profile.criticality is None:
                missing.append("criticality")
            profile.missing_fields = missing
            profile.is_dynamically_inferred = False
            profile.taxonomy_category = profile.taxonomy_category or "Industry component"
            if len(missing) >= 4:
                profile.evidence_status = "INSUFFICIENT_DATA"
                profile.confidence_score = 0.0
                profile.risk_reasons.append(
                    "INSUFFICIENT_DATA: industry MPN has no persisted vendor, stock, lead-time, or lifecycle evidence"
                )
            else:
                profile.evidence_status = "MIXED" if missing else "REAL_DATA"
                profile.confidence_score = (len(REQUIRED_RISK_FIELDS) - len(missing)) / len(REQUIRED_RISK_FIELDS)
            continue

        taxonomy = classify_mpn_taxonomy(pn or "")
        
        profile.taxonomy_category = taxonomy["category"]
        
        if not pn:
            # Entire part number is unknown
            profile.missing_fields.extend(REQUIRED_RISK_FIELDS)
            profile.confidence_score = 0.20
            profile.lifecycle_status = taxonomy["lifecycle_status"]
            profile.lead_time_weeks = taxonomy["lead_time_weeks"]
            profile.stock = taxonomy["stock"]
            profile.has_second_source = taxonomy["has_second_source"]
            profile.criticality = taxonomy["criticality"]
            profile.criticality_derived = True
            profile.unit_cost_usd = taxonomy["unit_cost_usd"]
            profile.is_dynamically_inferred = True
            profile.evidence_status = "INFERRED"
            continue
        
        # Explicit caller/provider values take precedence.  The merger is a
        # fallback layer; overwriting a real industry overlay here would make
        # live lifecycle and supply evidence invisible to the risk engine.
        if profile.lifecycle_status is None:
            profile.lifecycle_status = lifecycles.get(pn)
        if profile.lead_time_weeks is None:
            profile.lead_time_weeks = lead_times.get(pn)
        if profile.stock is None:
            profile.stock = stocks.get(pn)
        if profile.has_second_source is None:
            profile.has_second_source = second_sources.get(pn)
        profile.unit_cost_usd = unit_costs.get(pn, taxonomy["unit_cost_usd"])

        explicit_criticality = criticalities.get(pn)
        
        missing = []
        if profile.lifecycle_status is None:
            missing.append("lifecycle_status")
            profile.lifecycle_status = taxonomy["lifecycle_status"]
            
        if profile.lead_time_weeks is None:
            missing.append("lead_time_weeks")
            profile.lead_time_weeks = taxonomy["lead_time_weeks"]
            
        if profile.stock is None:
            missing.append("stock")
            profile.stock = taxonomy["stock"]
            
        if profile.has_second_source is None:
            missing.append("has_second_source")
            profile.has_second_source = taxonomy["has_second_source"]
            
        if profile.criticality is None and explicit_criticality is None:
            missing.append("criticality")
            profile.criticality = derive_criticality(profile)
            profile.criticality_derived = True
        elif profile.criticality is None:
            profile.criticality = explicit_criticality
            profile.criticality_derived = False

        profile.missing_fields = missing
        if missing:
            profile.is_dynamically_inferred = True
            profile.evidence_status = "INFERRED"
            profile.risk_reasons.append(f"Dynamic Taxonomy Synthesis: Inferred missing signals [{', '.join(missing)}] via {taxonomy['taxonomy_reason']}")
        else:
            profile.evidence_status = profile.evidence_status or "REAL_DATA"
            
        known_count = len(REQUIRED_RISK_FIELDS) - len(missing)
        profile.confidence_score = (known_count * 1.0 + (len(missing) * taxonomy["confidence_score"])) / len(REQUIRED_RISK_FIELDS)
        
    return profiles
