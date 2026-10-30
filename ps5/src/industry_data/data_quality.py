"""Industry dataset quality checks. Does not mutate raw files."""

from __future__ import annotations

import argparse
import csv
from typing import Dict, List, Optional

from src.industry_data.csv_store import NORMALIZED, read_csv
from src.industry_data.identity import demo_fixture_id, is_industry_model_id, operating_value_is_synthetic
from src.providers.settings import ROOT


def _issue(check: str, entity_id: str, detail: str) -> Dict[str, str]:
    return {"check": check, "entity_id": entity_id or "", "detail": detail or ""}


def run_quality() -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    models = read_csv("component_models.csv")
    lines = read_csv("bom_lines.csv")
    specs = read_csv("component_specs.csv")
    lifecycle = read_csv("lifecycle_records.csv")
    vendors = read_csv("vendor_supply_records.csv")
    stock = read_csv("vendor_stock_snapshots.csv")
    limits = read_csv("operating_limits.csv")
    tolerances = read_csv("tolerance_records.csv")
    unresolved = read_csv("unresolved_mpns.csv")
    provenance = []
    prov_path = NORMALIZED / "field_provenance.csv"
    if prov_path.is_file():
        with prov_path.open("r", encoding="utf-8-sig", newline="") as handle:
            provenance = list(csv.DictReader(handle))

    model_ids = {row.get("component_model_id") for row in models if row.get("component_model_id")}
    model_mpns = {row.get("normalized_mpn") for row in models if row.get("normalized_mpn")}

    seen_mpn: Dict[str, str] = {}
    for model in models:
        mpn = model.get("normalized_mpn") or ""
        mfr = (model.get("manufacturer") or "").lower()
        mid = model.get("component_model_id", "")
        if mid and not is_industry_model_id(mid):
            issues.append(_issue("invalid_component_model_id", mid, mpn))
        if demo_fixture_id(mid) or demo_fixture_id(mpn):
            issues.append(_issue("demo_fixture_in_industry_normalized", mid, mpn))
        if not model.get("manufacturer"):
            issues.append(_issue("missing_manufacturer", mid, mpn))
        if not mpn:
            issues.append(_issue("missing_mpn", mid, ""))
        key = f"{mfr}|{mpn}"
        if mpn and key in seen_mpn:
            issues.append(_issue("duplicate_mpn", mid, mpn))
        seen_mpn[key] = mid or ""

    seen_bom: Dict[tuple, str] = {}
    for line in lines:
        line_id = line.get("bom_line_id", "")
        product_id = line.get("product_id", "")
        identity = (
            product_id,
            line.get("revision_id", ""),
            line.get("original_mpn", ""),
            line.get("reference_designator", ""),
        )
        if identity in seen_bom:
            issues.append(_issue("duplicate_bom_identity", line_id, "|".join(identity)))
        seen_bom[identity] = line_id
        mid = line.get("component_model_id") or ""
        if mid and mid not in model_ids:
            issues.append(_issue("broken_component_model_id_fk", line_id, mid))
        if not line.get("original_mpn"):
            issues.append(_issue("unresolved_mpn", line_id, product_id))
        if not line.get("original_manufacturer"):
            issues.append(_issue("missing_manufacturer", line_id, line.get("original_mpn", "")))
        if not (line.get("reference_designator") or "").strip():
            issues.append(_issue("missing_refdes", line_id, line.get("original_mpn", "") or product_id))

    spec_models = {row.get("component_model_id") for row in specs if row.get("component_model_id")}
    for spec in specs:
        spec_id = spec.get("spec_id", "")
        mid = spec.get("component_model_id") or ""
        if mid and mid not in model_ids:
            issues.append(_issue("broken_component_model_id_fk", spec_id, mid))
        try:
            lo = float(spec["min_value"]) if spec.get("min_value") else None
            hi = float(spec["max_value"]) if spec.get("max_value") else None
        except ValueError:
            issues.append(_issue("invalid_numeric_values", spec_id, spec.get("parameter_name", "")))
            continue
        if lo is not None and hi is not None and lo > hi:
            issues.append(_issue("min_gt_max", spec_id, spec.get("parameter_name", "")))
        if not spec.get("provenance"):
            issues.append(_issue("missing_provenance", spec_id, spec.get("parameter_name", "")))

    models_without_specs = [mid for mid in model_ids if mid not in spec_models]
    if models_without_specs:
        issues.append(
            _issue(
                "missing_engineering_specs",
                "",
                f"{len(models_without_specs)} models have no component_specs rows",
            )
        )

    if not vendors:
        issues.append(_issue("empty_vendor_tables", "vendor_supply_records.csv", "0 rows; vendor status is INSUFFICIENT_DATA"))
    if not stock:
        issues.append(_issue("empty_vendor_tables", "vendor_stock_snapshots.csv", "0 rows"))
    if not lifecycle:
        issues.append(_issue("empty_lifecycle_table", "lifecycle_records.csv", "0 rows; lifecycle remains UNKNOWN/INSUFFICIENT_DATA"))

    for row in lifecycle:
        mid = row.get("component_model_id") or ""
        if mid and mid not in model_ids:
            issues.append(_issue("broken_component_model_id_fk", row.get("lifecycle_id", ""), mid))
        if not row.get("source_id"):
            issues.append(_issue("missing_lifecycle_source", row.get("lifecycle_id", ""), mid))

    for row in vendors:
        mid = row.get("component_model_id") or ""
        if mid and mid not in model_ids:
            issues.append(_issue("broken_component_model_id_fk", row.get("vendor_record_id", ""), mid))
        if not row.get("source_id") and not row.get("data_provenance"):
            issues.append(_issue("missing_vendor_source", row.get("vendor_record_id", ""), mid))

    for row in limits:
        mid = row.get("component_model_id") or ""
        mpn = row.get("normalized_mpn") or ""
        limit_id = row.get("limit_id", "")
        if demo_fixture_id(mid) or demo_fixture_id(mpn) or demo_fixture_id(limit_id):
            issues.append(_issue("demo_fixture_in_industry_normalized", limit_id, mid or mpn))
        if mid and not is_industry_model_id(mid):
            issues.append(_issue("broken_component_model_id_fk", limit_id, mid))
        elif mid and mid not in model_ids:
            issues.append(_issue("orphan_operating_limits", limit_id, mid))
        if not mid and mpn and mpn not in model_mpns:
            issues.append(_issue("orphan_operating_limits", limit_id, f"normalized_mpn={mpn} (documented join; not an industry model)"))
        if operating_value_is_synthetic(row):
            issues.append(_issue("synthetic_inferred_field_on_industry_evidence", limit_id, row.get("parameter", "")))
        if (row.get("operating_value") or "").strip() and operating_value_is_synthetic(row):
            issues.append(_issue("synthetic_operating_value", limit_id, row.get("parameter", "")))

    for row in tolerances:
        mid = row.get("component_model_id") or ""
        mpn = row.get("normalized_mpn") or ""
        tol_id = row.get("tolerance_id", "")
        if demo_fixture_id(mid) or demo_fixture_id(mpn) or demo_fixture_id(tol_id):
            issues.append(_issue("demo_fixture_in_industry_normalized", tol_id, mid or mpn))
        if mid and not is_industry_model_id(mid):
            issues.append(_issue("broken_component_model_id_fk", tol_id, mid))
        elif mid and mid not in model_ids:
            issues.append(_issue("orphan_tolerance_rows", tol_id, mid))

    for row in unresolved:
        issues.append(_issue("unresolved_mpns", row.get("original_mpn", ""), row.get("reason", "") or row.get("product_id", "")))

    status_dir = ROOT / "data" / "api_status"
    if status_dir.is_dir():
        failed = 0
        for path in status_dir.glob("*.json"):
            text = path.read_text(encoding="utf-8", errors="replace").upper()
            if any(token in text for token in ("QUOTA_EXHAUSTED", "401", "FAIL", "ERROR", "UNCONFIGURED")):
                failed += 1
        if failed:
            issues.append(_issue("failed_api_enrichment", str(status_dir), f"{failed} status files report provider failure"))

    provenanced = {row.get("entity_id") for row in provenance}
    for mid in model_ids:
        if mid and mid not in provenanced:
            issues.append(_issue("missing_provenance", mid, "component_model"))
    for conflict in read_csv("data_conflicts.csv"):
        if (conflict.get("resolution_status") or "UNRESOLVED").upper() == "RESOLVED":
            continue
        issues.append(_issue("conflicting_specifications", conflict.get("component_model_id", ""), conflict.get("field_name", "")))

    out = NORMALIZED / "data_quality_report.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check", "entity_id", "detail"])
        writer.writeheader()
        writer.writerows(issues)
    return issues


def main(argv: Optional[list[str]] = None) -> int:
    issues = run_quality()
    print(f"quality_issues={len(issues)}")
    print(str(NORMALIZED / "data_quality_report.csv"))
    _ = argv
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
