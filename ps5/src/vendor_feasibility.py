"""Vendor feasibility. Never overrides an engineering hard failure."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.industry_data.catalog_adapter import vendor_rows_for_mpn
from src.industry_data.mpn_resolver import normalize_mpn
from src.models import ComponentSpec

FEASIBLE = "FEASIBLE"
WARNING = "WARNING"
FAIL = "FAIL"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

REGION_COUNTRIES = {
    "IN": {"IN"},
    "US": {"US"},
    "EU": {"DE", "FR", "NL", "IE", "GB", "EU"},
    "APAC": {"SG", "JP", "CN", "TW", "KR", "HK", "APAC"},
}


def _int(value: Any) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def evaluate_vendor_feasibility(
    candidate: ComponentSpec,
    target_region: str = "IN",
    minimum_stock: int = 1,
    maximum_lead_time_days: int = 84,
    approved_vendor_rules: Optional[List[str]] = None,
) -> Dict[str, Any]:
    rows = vendor_rows_for_mpn(candidate.part_number)
    reason_codes: List[str] = []
    if not rows:
        return {
            "status": INSUFFICIENT_DATA,
            "source_count": 0,
            "regional_fit": False,
            "available_stock": None,
            "best_lead_time": None,
            "lifecycle": candidate.lifecycle_status,
            "approved_source": False,
            "reason_codes": ["INSUFFICIENT_EVIDENCE", "INSUFFICIENT_DATA"],
            "data_source": "MISSING",
        }
    region = (target_region or "IN").upper()
    allowed = REGION_COUNTRIES.get(region, {region})
    regional = [
        row
        for row in rows
        if (row.get("region") or "").upper() == region or (row.get("country") or "").upper() in allowed
    ]
    pool = regional
    if not pool:
        reason_codes.append("REGION_UNAVAILABLE")
    stocks = [_int(row.get("stock_quantity")) for row in (pool or rows)]
    stocks = [s for s in stocks if s is not None]
    leads = [_int(row.get("lead_time_days")) for row in (pool or rows)]
    leads = [d for d in leads if d is not None]
    available = sum(stocks) if stocks else None
    best_lead = min(leads) if leads else None
    names = {row.get("vendor_name") for row in (pool or rows) if row.get("vendor_name")}
    approved = True
    if approved_vendor_rules:
        approved = any((name or "").lower() in {r.lower() for r in approved_vendor_rules} for name in names)
        if not approved:
            reason_codes.append("UNAPPROVED_VENDOR")
    if available is not None and available < minimum_stock:
        reason_codes.append("LOW_STOCK")
    if best_lead is not None and best_lead > maximum_lead_time_days:
        reason_codes.append("LONG_LEAD_TIME")
    if len(names) <= 1:
        reason_codes.append("SINGLE_SOURCE")
    lifecycle = (candidate.lifecycle_status or "").upper()
    if lifecycle in {"EOL", "OBSOLETE"}:
        reason_codes.append("EOL")
    if lifecycle == "NRND":
        reason_codes.append("NRND")
    if pool and available is not None and available >= minimum_stock and (best_lead is None or best_lead <= maximum_lead_time_days) and approved:
        status = FEASIBLE if not reason_codes else WARNING
        reason_codes.append("VENDOR_FEASIBLE")
    elif not pool:
        status = FAIL
    elif available is None and best_lead is None:
        status = INSUFFICIENT_DATA
        reason_codes.append("INSUFFICIENT_EVIDENCE")
    else:
        status = WARNING if "REGION_UNAVAILABLE" not in reason_codes else FAIL
    return {
        "status": status,
        "source_count": len(names),
        "regional_fit": bool(pool),
        "available_stock": available,
        "best_lead_time": best_lead,
        "lifecycle": candidate.lifecycle_status,
        "approved_source": approved,
        "reason_codes": reason_codes,
        "region": region,
        "data_source": "REAL_DISTRIBUTOR_DATA",
        "mpn": normalize_mpn(candidate.part_number),
    }
