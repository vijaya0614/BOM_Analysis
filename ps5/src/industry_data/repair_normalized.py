"""One-time / idempotent repair of normalized industry evidence.

Does not invent manufacturer ratings, vendor data, reliability, or refdes values.
Preserves existing mdl_* identities (including TPS65217C) and PMIC EAV specs.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Dict, List

from src.industry_data.bom_normalizer import normalize_rows
from src.industry_data.csv_store import delete_where, ensure_headers, read_csv, write_all
from src.industry_data.identity import demo_fixture_id, is_industry_model_id, operating_value_is_synthetic
from src.industry_data.importer import parse_tabular
from src.providers.settings import ROOT

NORMALIZED = ROOT / "data" / "industry" / "normalized"
DEMO = ROOT / "data" / "demo"
RAW = ROOT / "data" / "industry" / "raw"

WIRELESS_BOM = (
    RAW
    / "beaglebone_black_wireless"
    / "extracted"
    / "5b6b89fd51d0a2b5"
    / "beaglebone-black-wireless-master"
    / "BeagleBone_Black_Wireless_BOM.csv"
)
AI_BOM = (
    RAW
    / "beaglebone_ai"
    / "extracted"
    / "81080925bbb23e0b"
    / "beaglebone-ai-master"
    / "BeagleBone-AI_bom.csv"
)


def _copy_demo_engineering_fixtures() -> None:
    """Move REG_* / synthetic operating fixtures into the demo namespace."""
    DEMO.mkdir(parents=True, exist_ok=True)
    for name in ("operating_limits.csv", "tolerance_records.csv"):
        dest = DEMO / name
        if dest.is_file():
            continue
        source = NORMALIZED / name
        if source.is_file():
            shutil.copy2(source, dest)


def _rewrite_operating_limits() -> int:
    rows = read_csv("operating_limits.csv")
    kept: List[Dict[str, str]] = []
    for row in rows:
        mid = (row.get("component_model_id") or "").strip()
        if demo_fixture_id(mid) or demo_fixture_id(row.get("limit_id") or ""):
            continue
        mpn = (row.get("normalized_mpn") or "").strip() or mid
        valid_mid = mid if is_industry_model_id(mid) else ""
        operating_value = ""
        provenance = "MISSING_OPERATING_VALUE"
        source_type = "MANUFACTURER_LIMIT_ONLY"
        if not operating_value_is_synthetic(row) and (row.get("operating_value") or "").strip():
            operating_value = row.get("operating_value") or ""
            provenance = row.get("provenance") or provenance
            source_type = row.get("source_type") or source_type
        kept.append(
            {
                **row,
                "component_model_id": valid_mid,
                "normalized_mpn": mpn,
                "operating_value": operating_value,
                "source_type": source_type,
                "provenance": provenance,
                "condition": (row.get("condition") or "").replace(
                    "actual operating value is fixture data",
                    "board operating_value is unavailable",
                ),
            }
        )
    write_all("operating_limits.csv", kept)
    return len(kept)


def _rewrite_tolerance() -> int:
    rows = read_csv("tolerance_records.csv")
    kept: List[Dict[str, str]] = []
    for row in rows:
        mid = (row.get("component_model_id") or "").strip()
        if demo_fixture_id(mid) or demo_fixture_id(row.get("tolerance_id") or ""):
            continue
        mpn = (row.get("normalized_mpn") or "").strip() or mid
        valid_mid = mid if is_industry_model_id(mid) else ""
        kept.append({**row, "component_model_id": valid_mid, "normalized_mpn": mpn})
    write_all("tolerance_records.csv", kept)
    return len(kept)


def _replace_product_bom(product_key: str, product_id: str, path: Path, source_id: str) -> int:
    rows = parse_tabular(path, str(path.relative_to(ROOT)).replace("\\", "/"))
    delete_where("bom_lines.csv", lambda row: row.get("product_id") == product_id)
    counts = normalize_rows(product_key, rows, source_id)
    return int(counts.get("bom_lines") or 0)


def _dedupe_bom(product_id: str, key_fields: List[str]) -> int:
    rows = read_csv("bom_lines.csv")
    kept: List[Dict[str, str]] = []
    seen = set()
    removed = 0
    for row in rows:
        if row.get("product_id") != product_id:
            kept.append(row)
            continue
        identity = tuple(str(row.get(field) or "") for field in key_fields)
        if identity in seen:
            removed += 1
            continue
        seen.add(identity)
        kept.append(row)
    write_all("bom_lines.csv", kept)
    return removed


def _source_id_for(product_id: str, fallback: str) -> str:
    for row in read_csv("products.csv"):
        if row.get("product_id") == product_id and row.get("source_id"):
            return row["source_id"]
    for row in read_csv("documents.csv"):
        if row.get("product_id") == product_id and row.get("source_id"):
            return row["source_id"]
    return fallback


def run_repair() -> Dict[str, int]:
    ensure_headers()
    before = {
        "bom_lines": len(read_csv("bom_lines.csv")),
        "operating_limits": len(read_csv("operating_limits.csv")),
        "tolerance_records": len(read_csv("tolerance_records.csv")),
        "component_models": len(read_csv("component_models.csv")),
        "component_specs": len(read_csv("component_specs.csv")),
    }
    _copy_demo_engineering_fixtures()
    limits = _rewrite_operating_limits()
    tolerances = _rewrite_tolerance()
    wireless = 0
    if WIRELESS_BOM.is_file():
        wireless = _replace_product_bom(
            "beaglebone_black_wireless",
            "beaglebone-black-wireless",
            WIRELESS_BOM,
            _source_id_for("beaglebone-black-wireless", "src_repair_wireless"),
        )
    ai = 0
    if AI_BOM.is_file():
        ai = _replace_product_bom(
            "beaglebone_ai",
            "beaglebone-ai",
            AI_BOM,
            _source_id_for("beaglebone-ai", "src_repair_ai"),
        )
    bbb_removed = _dedupe_bom(
        "beaglebone-black",
        ["product_id", "revision_id", "original_mpn", "reference_designator"],
    )
    tidep_removed = _dedupe_bom(
        "ti-tidep-0050",
        ["product_id", "revision_id", "original_mpn", "reference_designator"],
    )
    after = {
        "bom_lines": len(read_csv("bom_lines.csv")),
        "operating_limits": limits,
        "tolerance_records": tolerances,
        "component_models": len(read_csv("component_models.csv")),
        "component_specs": len(read_csv("component_specs.csv")),
        "wireless_bom_lines": wireless,
        "ai_bom_lines": ai,
        "beaglebone_black_dupes_removed": bbb_removed,
        "tidep_dupes_removed": tidep_removed,
        "bom_lines_before": before["bom_lines"],
        "operating_limits_before": before["operating_limits"],
        "tolerance_records_before": before["tolerance_records"],
        "component_specs_before": before["component_specs"],
    }
    return after


def main() -> int:
    result = run_repair()
    for key, value in sorted(result.items()):
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
