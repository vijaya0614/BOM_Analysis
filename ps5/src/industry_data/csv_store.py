"""CSV store for industry-normalized entities. Does not touch data/*.csv synthetic sets."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from src.providers.settings import ROOT

NORMALIZED = ROOT / "data" / "industry" / "normalized"

SCHEMAS: Dict[str, List[str]] = {
    "products.csv": ["product_id", "product_name", "manufacturer", "product_family", "description", "source_id"],
    "product_revisions.csv": [
        "revision_id", "product_id", "revision", "version", "release_date", "lifecycle_status", "source_id",
    ],
    "product_subsystems.csv": [
        "subsystem_id", "product_id", "parent_subsystem_id", "subsystem_name", "hierarchy_level", "description",
    ],
    "bom_lines.csv": [
        "bom_line_id", "product_id", "revision_id", "subsystem_id", "reference_designator",
        "component_type_id", "component_model_id", "quantity", "unit", "position", "parent_assembly",
        "original_manufacturer", "original_mpn", "original_description", "source_id",
    ],
    "component_types.csv": ["component_type_id", "component_class", "subcategory", "description"],
    "component_models.csv": [
        "component_model_id", "manufacturer", "mpn", "normalized_mpn", "description", "package",
        "mounting_type", "component_category", "datasheet_url", "lifecycle_status",
    ],
    "component_specs.csv": [
        "spec_id", "component_model_id", "parameter_name", "nominal_value", "min_value", "max_value",
        "unit", "condition", "source_document", "source_page", "confidence", "provenance",
    ],
    "documents.csv": [
        "document_id", "component_model_id", "product_id", "document_type", "title", "url",
        "revision", "publication_date", "source_id", "filename", "file_hash", "source_path",
        "imported_at", "extraction_status", "confidence", "source_page",
    ],
    "lifecycle_records.csv": [
        "lifecycle_id", "component_model_id", "status", "source_status", "status_date",
        "announcement_date", "last_order_date", "last_ship_date", "replacement_mpn", "pcn_number",
        "support_status", "source_id", "confidence",
    ],
    "vendors.csv": ["vendor_id", "vendor_name", "region", "country", "vendor_type"],
    "vendor_supply_records.csv": [
        "vendor_record_id", "component_model_id", "vendor_id", "vendor_part_number", "region", "country",
        "stock_quantity", "stock_status", "lead_time_days", "moq", "unit_price", "currency",
        "authorized", "last_updated", "retrieved_at", "expires_at", "retrieval_state", "provider", "source_id", "data_provenance", "confidence",
    ],
    "vendor_stock_snapshots.csv": [
        "snapshot_id", "component_model_id", "vendor_id", "timestamp", "stock_quantity", "stock_status",
        "lead_time_days", "unit_price", "currency", "region", "source", "data_provenance",
    ],
    "operating_limits.csv": [
        "limit_id", "component_model_id", "normalized_mpn", "parameter", "operating_value",
        "required_min", "required_max", "unit", "condition", "source", "source_type",
        "confidence", "provenance",
    ],
    "tolerance_records.csv": [
        "tolerance_id", "component_model_id", "normalized_mpn", "parameter", "nominal",
        "min_value", "max_value", "tolerance_value", "tolerance_type", "unit", "condition",
        "source", "source_type", "confidence", "provenance",
    ],
    "dependency_graph.csv": [
        "edge_id", "product_id", "source_node", "target_node", "relationship_type", "function", "confidence", "source",
    ],
    "redesign_constraints.csv": [
        "constraint_id", "component_model_id", "constraint_type", "constraint_value", "unit", "source",
    ],
    "unresolved_mpns.csv": [
        "original_mpn", "original_manufacturer", "product_id", "source_file", "reason", "resolution_status",
    ],
    "data_conflicts.csv": [
        "component_model_id", "field_name", "provider_a", "value_a", "provider_b", "value_b",
        "detected_at", "resolution_status",
    ],
}


def _merged_fields(schema: Sequence[str], existing: Sequence[str]) -> List[str]:
    merged = list(schema)
    for field in existing:
        if field and field not in merged:
            merged.append(field)
    return merged


def ensure_headers() -> None:
    NORMALIZED.mkdir(parents=True, exist_ok=True)
    for name, fields in SCHEMAS.items():
        path = NORMALIZED / name
        if path.is_file():
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                existing_fields = reader.fieldnames or []
                merged = _merged_fields(fields, existing_fields)
                if list(existing_fields) == merged:
                    continue
                rows = list(reader)
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=merged, extrasaction="ignore")
                writer.writeheader()
                for row in rows:
                    writer.writerow({key: row.get(key, "") for key in merged})
            continue
        with path.open("w", encoding="utf-8", newline="") as handle:
            csv.DictWriter(handle, fieldnames=fields).writeheader()


def read_csv(name: str) -> List[Dict[str, str]]:
    path = NORMALIZED / name
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def append_rows(name: str, rows: Iterable[Dict[str, str]]) -> None:
    ensure_headers()
    fields = SCHEMAS[name]
    path = NORMALIZED / name
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})


def upsert_by_key(name: str, key: str, row: Dict[str, str]) -> None:
    ensure_headers()
    rows = read_csv(name)
    replaced = False
    out = []
    for existing in rows:
        if existing.get(key) == row.get(key) and row.get(key):
            existing.update(row)
            replaced = True
        out.append(existing)
    if not replaced:
        out.append(row)
    fields = SCHEMAS[name]
    path = NORMALIZED / name
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for item in out:
            writer.writerow({k: item.get(k, "") for k in fields})


def find_model_by_mpn(normalized_mpn: str, manufacturer: str = "") -> Optional[Dict[str, str]]:
    matches = [row for row in read_csv("component_models.csv") if row.get("normalized_mpn") == normalized_mpn]
    if manufacturer:
        exact = [row for row in matches if row.get("manufacturer", "").lower() == manufacturer.lower()]
        if exact:
            return exact[0]
        if len(matches) > 1:
            return None
    if len(matches) == 1:
        return matches[0]
    return matches[0] if matches else None


def stable_id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]}"


def write_all(name: str, rows: Iterable[Dict[str, str]]) -> None:
    ensure_headers()
    fields = SCHEMAS[name]
    path = NORMALIZED / name
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        existing_fields = csv.DictReader(handle).fieldnames or []
    merged = _merged_fields(fields, existing_fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=merged, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in merged})


def upsert_rows(name: str, key_fields: Sequence[str], rows: Iterable[Dict[str, str]]) -> int:
    """Insert or replace rows matching the composite identity in ``key_fields``.

    Re-importing the same source identity updates the existing row instead of
    appending a duplicate. Returns the number of rows written from ``rows``.
    """
    ensure_headers()
    existing = read_csv(name)
    index: Dict[tuple, int] = {}
    for position, row in enumerate(existing):
        index[tuple(str(row.get(field) or "") for field in key_fields)] = position
    written = 0
    for row in rows:
        identity = tuple(str(row.get(field) or "") for field in key_fields)
        if identity in index:
            current = existing[index[identity]]
            current.update({key: value for key, value in row.items() if value or key in key_fields})
            existing[index[identity]] = current
        else:
            index[identity] = len(existing)
            existing.append(dict(row))
        written += 1
    write_all(name, existing)
    return written


def delete_where(name: str, predicate: Callable[[Dict[str, str]], bool]) -> int:
    rows = read_csv(name)
    kept = [row for row in rows if not predicate(row)]
    removed = len(rows) - len(kept)
    if removed:
        write_all(name, kept)
    return removed
