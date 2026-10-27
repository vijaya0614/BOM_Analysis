"""Map industry vendor/lifecycle rows onto existing ComponentSpec / PartRiskProfile fields."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.industry_data.csv_store import find_model_by_mpn, read_csv
from src.industry_data.mpn_resolver import normalize_mpn
from src.models import ComponentSpec, PartRiskProfile

ENGINE_LIFECYCLE = {
    "ACTIVE": "Active",
    "NRND": "NRND",
    "LTB": "NRND",
    "EOL": "Obsolete",
    "OBSOLETE": "Obsolete",
    "UNCONFIRMED": None,
    "UNKNOWN": None,
}


def _int(value: str) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def vendor_rows_for_mpn(mpn: str) -> List[Dict[str, str]]:
    model = find_model_by_mpn(normalize_mpn(mpn))
    if not model:
        return []
    mid = model["component_model_id"]
    vendors = {row["vendor_id"]: row for row in read_csv("vendors.csv")}
    out = []
    for rec in read_csv("vendor_supply_records.csv"):
        if rec.get("component_model_id") != mid:
            continue
        vendor = vendors.get(rec.get("vendor_id") or "", {})
        out.append({**rec, "vendor_name": vendor.get("vendor_name", rec.get("vendor_id", ""))})
    return out


def supply_overlay(mpn: str) -> Dict[str, Any]:
    """Return persisted distributor stock/lead/price, including stock 0."""
    vendors = vendor_rows_for_mpn(mpn)
    if not vendors:
        return {}
    stocks = [_int(row.get("stock_quantity") or "") for row in vendors]
    stocks = [value for value in stocks if value is not None]
    leads = [_int(row.get("lead_time_days") or "") for row in vendors]
    leads = [value for value in leads if value is not None]
    unit_price = None
    currency = ""
    for row in vendors:
        try:
            parsed = float(str(row.get("unit_price") or "").replace(",", ""))
        except (TypeError, ValueError):
            parsed = None
        if parsed is not None:
            unit_price = parsed
            currency = row.get("currency") or ""
            break
    return {
        "stock": sum(stocks) if stocks else None,
        "lead_time_weeks": max(1, min(leads) // 7) if leads else None,
        "unit_price": unit_price,
        "currency": currency,
        "has_second_source": len({row.get("vendor_name") for row in vendors}) > 1,
    }


def lifecycle_for_mpn(mpn: str) -> Optional[str]:
    model = find_model_by_mpn(normalize_mpn(mpn))
    if not model:
        return None
    rows = [row for row in read_csv("lifecycle_records.csv") if row.get("component_model_id") == model["component_model_id"]]
    if not rows:
        mapped = ENGINE_LIFECYCLE.get((model.get("lifecycle_status") or "").upper())
        return mapped
    status = rows[-1].get("status") or ""
    return ENGINE_LIFECYCLE.get(status.upper())


def lifecycle_label_for_mpn(mpn: str) -> Optional[str]:
    model = find_model_by_mpn(normalize_mpn(mpn))
    if not model:
        return None
    rows = [row for row in read_csv("lifecycle_records.csv") if row.get("component_model_id") == model["component_model_id"]]
    if rows:
        return rows[-1].get("status") or rows[-1].get("source_status") or None
    status = (model.get("lifecycle_status") or "").strip()
    return status or None


def apply_industry_to_profile(profile: PartRiskProfile, region: str = "") -> PartRiskProfile:
    if not profile.part_number:
        return profile
    overlay = supply_overlay(profile.part_number)
    if overlay:
        if profile.stock is None and overlay.get("stock") is not None:
            profile.stock = overlay["stock"]
        if profile.lead_time_weeks is None and overlay.get("lead_time_weeks") is not None:
            profile.lead_time_weeks = overlay["lead_time_weeks"]
        if profile.has_second_source is None and overlay.get("has_second_source") is not None:
            profile.has_second_source = overlay["has_second_source"]
        profile.risk_reasons.append("Industry vendor records applied (REAL_DISTRIBUTOR_DATA)")
    lifecycle = lifecycle_for_mpn(profile.part_number)
    if profile.lifecycle_status is None and lifecycle:
        profile.lifecycle_status = lifecycle
    return profile


def apply_industry_overlay(component: ComponentSpec, region: str = "") -> ComponentSpec:
    overlay = supply_overlay(component.part_number)
    if overlay:
        if component.stock is None and overlay.get("stock") is not None:
            component.stock = overlay["stock"]
        if component.lead_time_weeks is None and overlay.get("lead_time_weeks") is not None:
            component.lead_time_weeks = overlay["lead_time_weeks"]
        if component.has_second_source is None and overlay.get("has_second_source") is not None:
            component.has_second_source = overlay["has_second_source"]
    lifecycle = lifecycle_for_mpn(component.part_number)
    if component.lifecycle_status is None and lifecycle:
        component.lifecycle_status = lifecycle
    return component


def component_enrichment_payload(mpn: str) -> Dict[str, Any]:
    model = find_model_by_mpn(normalize_mpn(mpn))
    vendors = vendor_rows_for_mpn(mpn)
    specs = []
    lifecycle = []
    provenance = []
    documents = []
    if model:
        mid = model["component_model_id"]
        from src.industry_data.bom_normalizer import BOM_IDENTITY_ATTRIBUTES

        specs = [
            row
            for row in read_csv("component_specs.csv")
            if row.get("component_model_id") == mid
            and str(row.get("parameter_name") or "").strip().lower() not in BOM_IDENTITY_ATTRIBUTES
        ]
        lifecycle = [row for row in read_csv("lifecycle_records.csv") if row.get("component_model_id") == mid]
        documents = [
            row for row in read_csv("documents.csv")
            if row.get("component_model_id") == mid and row.get("url")
        ]
        from src.industry_data.provenance import ProvenanceStore

        provenance = ProvenanceStore().for_entity(mid)
    return {
        "mpn": mpn,
        "model": model,
        "vendor_records": vendors,
        "technical_specs": specs,
        "documents": documents,
        "lifecycle_evidence": lifecycle,
        "provenance": provenance,
        # A BOM-backed model is useful evidence even without provider
        # enrichment; do not collapse it into MISSING just because stock or
        # lifecycle records have not been fetched.
        "data_source": "REAL_DISTRIBUTOR_DATA" if vendors else "REAL_PUBLIC_SOURCE" if model else "MISSING",
    }
