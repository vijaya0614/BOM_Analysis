"""Map industry vendor/lifecycle rows onto existing ComponentSpec / PartRiskProfile fields."""

from __future__ import annotations

from datetime import datetime, timezone
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

LIFECYCLE_REVIEW_DAYS = 180


def _parse_time(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _vendor_freshness(row: Dict[str, str]) -> str:
    if (row.get("data_provenance") or "").upper() != "REAL_DISTRIBUTOR_DATA":
        return "UNTRUSTED_SOURCE"
    expiry = _parse_time(row.get("expires_at") or "")
    if expiry is None:
        return "UNKNOWN"
    if expiry <= datetime.now(timezone.utc) or (row.get("retrieval_state") or "").upper() == "STALE":
        return "STALE"
    if (row.get("retrieval_state") or "").upper() not in {"LIVE", "CACHED"}:
        return "UNKNOWN"
    return "CURRENT"


def _unresolved_conflicts(model_id: str, fields: Optional[set[str]] = None) -> List[Dict[str, str]]:
    return [
        row for row in read_csv("data_conflicts.csv")
        if row.get("component_model_id") == model_id
        and (row.get("resolution_status") or "UNRESOLVED").upper() != "RESOLVED"
        and (fields is None or row.get("field_name") in fields)
    ]


def conflicts_for_mpn(mpn: str) -> List[Dict[str, str]]:
    model = find_model_by_mpn(normalize_mpn(mpn))
    return _unresolved_conflicts(model["component_model_id"]) if model else []


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
    """Return only current, provenance-backed supply; surface excluded records."""
    model = find_model_by_mpn(normalize_mpn(mpn))
    vendors = vendor_rows_for_mpn(mpn)
    if not model:
        return {"freshness": "INSUFFICIENT_DATA", "fresh_records": 0, "excluded_records": 0, "conflicts": []}
    states = [_vendor_freshness(row) for row in vendors]
    conflicts = _unresolved_conflicts(
        model["component_model_id"], {"stock_quantity", "stock_status", "lead_time_days", "unit_price", "currency"}
    )
    active = [row for row, state in zip(vendors, states) if state == "CURRENT"]
    status = (
        "CONFLICT" if conflicts else
        "CURRENT" if active and len(active) == len(vendors) else
        "INCOMPLETE" if active else
        "STALE" if "STALE" in states else
        "UNKNOWN" if vendors else
        "INSUFFICIENT_DATA"
    )
    if not active or conflicts:
        return {
            "stock": None, "lead_time_weeks": None, "unit_price": None, "currency": "",
            "has_second_source": None, "freshness": status, "fresh_records": len(active),
            "excluded_records": len(vendors) - len(active), "conflicts": conflicts,
        }
    vendors = active
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
        "freshness": status,
        "fresh_records": len(active),
        "excluded_records": len(states) - len(active),
        "conflicts": conflicts,
    }


def lifecycle_for_mpn(mpn: str) -> Optional[str]:
    model = find_model_by_mpn(normalize_mpn(mpn))
    if not model:
        return None
    rows = [row for row in read_csv("lifecycle_records.csv") if row.get("component_model_id") == model["component_model_id"]]
    if not rows:
        return None
    if _unresolved_conflicts(model["component_model_id"], {"lifecycle_status", "status"}):
        return None
    statuses = {row.get("status") for row in rows if row.get("status")}
    if len(statuses) != 1:
        return None
    source_ids = {row.get("source_id") for row in rows if row.get("source_id")}
    sources = {row.get("source_id"): row for row in read_csv("source_registry.csv")}
    retrieved = [_parse_time(sources[source_id].get("retrieved_at") or "") for source_id in source_ids if source_id in sources]
    observed = max((stamp for stamp in retrieved if stamp is not None), default=None)
    if observed is None or (datetime.now(timezone.utc) - observed).days > LIFECYCLE_REVIEW_DAYS:
        return None
    status = next(iter(statuses)) or ""
    return ENGINE_LIFECYCLE.get(status.upper())


def lifecycle_quality_for_mpn(mpn: str) -> str:
    model = find_model_by_mpn(normalize_mpn(mpn))
    if not model:
        return "INSUFFICIENT_DATA"
    model_id = model["component_model_id"]
    rows = [row for row in read_csv("lifecycle_records.csv") if row.get("component_model_id") == model_id]
    if not rows:
        return "UNKNOWN"
    if _unresolved_conflicts(model_id, {"lifecycle_status", "status"}) or len({row.get("status") for row in rows if row.get("status")}) > 1:
        return "CONFLICT"
    status = next((row.get("status") for row in rows if row.get("status")), "")
    if ENGINE_LIFECYCLE.get(status.upper()) is None:
        return "UNKNOWN"
    sources = {row.get("source_id"): row for row in read_csv("source_registry.csv")}
    stamps = [
        _parse_time(sources[source_id].get("retrieved_at") or "")
        for source_id in {row.get("source_id") for row in rows if row.get("source_id")}
        if source_id in sources
    ]
    observed = max((stamp for stamp in stamps if stamp is not None), default=None)
    if observed is None:
        return "UNKNOWN"
    return "STALE" if (datetime.now(timezone.utc) - observed).days > LIFECYCLE_REVIEW_DAYS else "CURRENT"


def lifecycle_label_for_mpn(mpn: str) -> Optional[str]:
    model = find_model_by_mpn(normalize_mpn(mpn))
    if not model:
        return None
    rows = [row for row in read_csv("lifecycle_records.csv") if row.get("component_model_id") == model["component_model_id"]]
    if rows:
        if lifecycle_for_mpn(mpn) is None:
            return None
        return next((row.get("status") or row.get("source_status") for row in rows if row.get("status")), None)
    return None


def apply_industry_to_profile(profile: PartRiskProfile, region: str = "") -> PartRiskProfile:
    if not profile.part_number:
        return profile
    overlay = supply_overlay(profile.part_number)
    if overlay.get("fresh_records", 0):
        if profile.stock is None and overlay.get("stock") is not None:
            profile.stock = overlay["stock"]
        if profile.lead_time_weeks is None and overlay.get("lead_time_weeks") is not None:
            profile.lead_time_weeks = overlay["lead_time_weeks"]
        if profile.has_second_source is None and overlay.get("has_second_source") is not None:
            profile.has_second_source = overlay["has_second_source"]
        profile.risk_reasons.append("Current source-backed industry vendor records applied (REAL_DISTRIBUTOR_DATA)")
    lifecycle = lifecycle_for_mpn(profile.part_number)
    if profile.lifecycle_status is None and lifecycle:
        profile.lifecycle_status = lifecycle
    return profile


def apply_industry_overlay(component: ComponentSpec, region: str = "") -> ComponentSpec:
    overlay = supply_overlay(component.part_number)
    if overlay.get("fresh_records", 0):
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
    supply_status = supply_overlay(mpn)
    lifecycle_quality = lifecycle_quality_for_mpn(mpn)
    unresolved_conflicts = conflicts_for_mpn(mpn)
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
        "vendor_records": [{**row, "freshness_status": _vendor_freshness(row)} for row in vendors],
        "technical_specs": specs,
        "documents": documents,
        "lifecycle_evidence": lifecycle,
        "provenance": provenance,
        # A BOM-backed model is useful evidence even without provider
        # enrichment; do not collapse it into MISSING just because stock or
        # lifecycle records have not been fetched.
        "data_source": "REAL_DISTRIBUTOR_DATA" if model and supply_status.get("fresh_records") else "REAL_PUBLIC_SOURCE" if model else "MISSING",
        "data_quality": {
            "vendor_supply": supply_status.get("freshness", "INSUFFICIENT_DATA"),
            "vendor_records_used": supply_status.get("fresh_records", 0),
            "vendor_records_excluded": supply_status.get("excluded_records", 0),
            "lifecycle": lifecycle_quality,
            "engineering_specs": "UNKNOWN" if specs else "INSUFFICIENT_DATA",
            "engineering_specs_count": len(specs),
            "unresolved_conflicts": unresolved_conflicts,
        },
    }
