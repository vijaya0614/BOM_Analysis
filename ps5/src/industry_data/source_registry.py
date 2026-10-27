"""Immutable source registry for industry files and provider pulls."""

from __future__ import annotations

import csv
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

from src.providers.settings import ROOT

FIELDS = [
    "source_id",
    "source_type",
    "title",
    "url",
    "local_path",
    "retrieved_at",
    "notes",
]


class SourceRegistry:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or (ROOT / "data" / "industry" / "normalized" / "source_registry.csv")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def register(
        self,
        source_type: str,
        title: str,
        url: str = "",
        local_path: str = "",
        notes: str = "",
    ) -> str:
        source_id = f"src_{uuid.uuid4().hex[:12]}"
        row = {
            "source_id": source_id,
            "source_type": source_type,
            "title": title,
            "url": url,
            "local_path": local_path,
            "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "notes": notes,
        }
        write_header = not self.path.is_file()
        with self.path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
        return source_id

    def rows(self) -> list[Dict[str, str]]:
        if not self.path.is_file():
            return []
        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
