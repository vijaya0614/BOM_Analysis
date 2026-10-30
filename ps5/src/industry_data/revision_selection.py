"""Select one imported BOM revision for reports; never combine revisions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Tuple

from src.industry_data.csv_store import read_csv


def _timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def select_product_bom(
    product_id: str,
    reader: Callable[[str], List[Dict[str, str]]] | None = None,
) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    reader = reader or read_csv
    all_lines = [
        row for row in reader("bom_lines.csv")
        if row.get("product_id") == product_id and row.get("original_mpn")
    ]
    revisions = [row for row in reader("product_revisions.csv") if row.get("product_id") == product_id]
    if not revisions:
        line_revisions = {row.get("revision_id") for row in all_lines if row.get("revision_id")}
        line_sources = {row.get("source_id") for row in all_lines if row.get("source_id")}
        if len(line_revisions) > 1 or len(line_sources) > 1:
            return [], {
                "status": "AMBIGUOUS_REVISION", "selected_revision": "UNKNOWN",
                "revision_verified": False, "selection_rule": "NO_REVISION_METADATA_FOR_MULTIPLE_SOURCES",
            }
        return all_lines, {
            "status": "NO_REVISION_METADATA", "selected_revision": "UNKNOWN",
            "revision_verified": False, "selection_rule": "NO_REVISION_METADATA",
        }
    sources = {row.get("source_id"): row for row in reader("source_registry.csv")}
    for revision in revisions:
        source = sources.get(revision.get("source_id") or "", {})
        revision["_observed_at"] = source.get("retrieved_at") or ""
        revision["_observed_time"] = _timestamp(revision["_observed_at"])
    observed = [revision for revision in revisions if revision["_observed_time"] is not None]
    if not observed:
        if len({row.get("revision_id") for row in revisions}) > 1:
            return [], {
                "status": "AMBIGUOUS_REVISION", "selected_revision": "UNKNOWN",
                "revision_verified": False, "selection_rule": "NO_SOURCE_OBSERVATION_TIMES",
            }
        selected = revisions[-1]
        rule = "ONLY_IMPORTED_REVISION"
        status = "REVISION_UNVERIFIED"
    else:
        latest_time = max(row["_observed_time"] for row in observed)
        latest = [row for row in observed if row["_observed_time"] == latest_time]
        if len({row.get("revision_id") for row in latest}) > 1:
            return [], {
                "status": "AMBIGUOUS_REVISION", "selected_revision": "UNKNOWN",
                "revision_verified": False, "selection_rule": "TIED_SOURCE_OBSERVATION_TIMES",
            }
        selected = latest[-1]
        rule = "LATEST_SOURCE_REGISTRY_OBSERVATION" if len(revisions) > 1 else "ONLY_IMPORTED_REVISION"
        status = "REVISION_UNVERIFIED"
    selected_lines = [row for row in all_lines if row.get("revision_id") == selected.get("revision_id")]
    source_ids = sorted({row.get("source_id") for row in selected_lines if row.get("source_id")})
    if len(source_ids) > 1:
        status = "INCOMPLETE"
    return selected_lines, {
        "status": status,
        "selected_revision": selected.get("revision") or "UNKNOWN",
        "revision_id": selected.get("revision_id") or "",
        "revision_verified": bool(selected.get("release_date")),
        "source_observed_at": selected.get("_observed_at") or "",
        "source_ids": source_ids,
        "source_document_count": len(source_ids),
        "selection_rule": rule,
    }
