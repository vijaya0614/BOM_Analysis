"""Industry BOM ingestion. Raw files under data/industry/raw are immutable."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.bom_parser import PART_NUM_HEADERS, QTY_HEADERS, REF_HEADERS
from src.industry_data.bom_normalizer import PRODUCTS, normalize_rows
from src.industry_data.csv_store import ensure_headers
from src.industry_data.source_registry import SourceRegistry
from src.providers.settings import ROOT

RAW_ROOT = ROOT / "data" / "industry" / "raw"

MANUFACTURER_HEADERS = ["manufacturer", "mfr", "mfg", "vendor", "maker"]
DESC_HEADERS = ["description", "desc", "comment", "value", "part description"]
PACKAGE_HEADERS = ["package", "footprint", "pkg", "case"]


def _index(headers: List[str], names: List[str]) -> Optional[int]:
    lower = [h.strip().lower() for h in headers]
    for name in names:
        if name in lower:
            return lower.index(name)
    return None


def _cell(row: List[str], idx: Optional[int]) -> str:
    if idx is None or idx >= len(row):
        return ""
    return (row[idx] or "").strip()


def parse_tabular(path: Path) -> List[Dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            try:
                headers = next(reader)
            except StopIteration:
                return []
            return _rows_from_table(headers, list(reader), path)
    if suffix in {".xlsx", ".xlsm"}:
        from openpyxl import load_workbook

        book = load_workbook(path, read_only=True, data_only=True)
        sheet = book.active
        rows_iter = sheet.iter_rows(values_only=True)
        try:
            headers = [str(v or "") for v in next(rows_iter)]
        except StopIteration:
            return []
        body = [[str(v or "") for v in row] for row in rows_iter]
        return _rows_from_table(headers, body, path)
    if suffix == ".xls":
        raise ValueError(f"Legacy .xls requires conversion to CSV/XLSX before ingest: {path}")
    return []


def _rows_from_table(headers: List[str], body: List[List[str]], path: Path) -> List[Dict[str, Any]]:
    pn_idx = _index(headers, PART_NUM_HEADERS + ["manufacturer part number", "mfr pn"])
    ref_idx = _index(headers, REF_HEADERS)
    qty_idx = _index(headers, QTY_HEADERS)
    mfr_idx = _index(headers, MANUFACTURER_HEADERS)
    desc_idx = _index(headers, DESC_HEADERS)
    pkg_idx = _index(headers, PACKAGE_HEADERS)
    parsed = []
    for i, row in enumerate(body, start=2):
        if not row or not any(str(c).strip() for c in row):
            continue
        parsed.append(
            {
                "mpn": _cell(row, pn_idx),
                "reference_designator": _cell(row, ref_idx),
                "quantity": _cell(row, qty_idx) or "1",
                "manufacturer": _cell(row, mfr_idx),
                "description": _cell(row, desc_idx),
                "package": _cell(row, pkg_idx),
                "source_file": str(path.as_posix()),
                "source_page": str(i),
            }
        )
    return parsed


def ingest_product(product_key: str) -> Dict[str, Any]:
    ensure_headers()
    folder = RAW_ROOT / product_key
    if not folder.is_dir():
        return {"product": product_key, "error": "RAW_DIR_MISSING"}
    registry = SourceRegistry()
    totals = {"bom_lines": 0, "models": 0, "unresolved": 0, "files": 0}
    for path in sorted(folder.iterdir()):
        if path.name.startswith(".") or path.suffix.lower() not in {".csv", ".xlsx", ".xlsm", ".xls"}:
            continue
        source_id = registry.register(
            source_type="REAL_PUBLIC_SOURCE",
            title=path.name,
            local_path=str(path.relative_to(ROOT)).replace("\\", "/"),
            notes="Industry BOM ingest; raw file not modified",
        )
        rows = parse_tabular(path)
        counts = normalize_rows(product_key, rows, source_id)
        totals["bom_lines"] += counts["bom_lines"]
        totals["models"] += counts["models"]
        totals["unresolved"] += counts["unresolved"]
        totals["files"] += 1
    totals["product"] = PRODUCTS[product_key]["product_id"]
    return totals


def ingest_all() -> List[Dict[str, Any]]:
    return [ingest_product(key) for key in PRODUCTS]


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest industry BOMs from data/industry/raw")
    parser.add_argument("--product", choices=sorted(PRODUCTS))
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    if args.product:
        print(ingest_product(args.product))
        return 0
    for result in ingest_all():
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
