"""Field-level provenance. Never claim simulated data is real."""

from __future__ import annotations

import csv
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from src.providers.settings import ROOT

ALLOWED = {
    "REAL_PUBLIC_SOURCE",
    "REAL_MANUFACTURER_DATA",
    "REAL_DISTRIBUTOR_DATA",
    "DERIVED",
    "NORMALIZED",
    "SIMULATED",
    "MISSING",
}

FIELDS = [
    "provenance_id",
    "source_id",
    "entity_type",
    "entity_id",
    "field_name",
    "source_type",
    "source_document",
    "source_url",
    "source_page",
    "retrieved_at",
    "confidence",
    "data_provenance",
]


class ProvenanceStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or (ROOT / "data" / "industry" / "normalized" / "field_provenance.csv")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        source_id: str,
        entity_type: str,
        entity_id: str,
        field_name: str,
        source_type: str,
        data_provenance: str,
        source_document: str = "",
        source_url: str = "",
        source_page: str = "",
        confidence: str = "",
    ) -> str:
        if data_provenance not in ALLOWED:
            raise ValueError(f"Invalid data_provenance: {data_provenance}")
        pid = f"prv_{uuid.uuid4().hex[:12]}"
        row = {
            "provenance_id": pid,
            "source_id": source_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "field_name": field_name,
            "source_type": source_type,
            "source_document": source_document,
            "source_url": source_url,
            "source_page": source_page,
            "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "confidence": confidence,
            "data_provenance": data_provenance,
        }
        write_header = not self.path.is_file()
        with self.path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
        return pid

    def for_entity(self, entity_id: str) -> List[Dict[str, str]]:
        if not self.path.is_file():
            return []
        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [row for row in csv.DictReader(handle) if row.get("entity_id") == entity_id]
