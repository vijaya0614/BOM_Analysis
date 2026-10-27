"""Store original provider responses for audit. Never overwrite historical snapshots."""

from __future__ import annotations

import csv
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from src.providers.settings import ROOT

INDEX_FIELDS = [
    "response_id",
    "provider",
    "query_type",
    "mpn",
    "request_timestamp",
    "response_timestamp",
    "http_status",
    "raw_response_path",
    "success",
    "error_code",
    "error_message",
]


class RawResponseStore:
    def __init__(self, provider: str, root: Optional[Path] = None) -> None:
        self.provider = provider
        self.root = Path(root) if root else ROOT / "data" / "api_raw" / provider
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = ROOT / "data" / "industry" / "normalized" / "api_raw_responses.csv"

    def save(
        self,
        query_type: str,
        mpn: str,
        body: Dict[str, Any],
        *,
        http_status: Optional[int] = None,
        success: bool = True,
        error_code: str = "",
        error_message: str = "",
    ) -> Path:
        response_id = uuid.uuid4().hex
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        filename = f"{stamp}_{query_type}_{mpn}_{response_id[:8]}.json"
        safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in filename)
        path = self.root / safe_name
        path.write_text(json.dumps(body, indent=2), encoding="utf-8")
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._append_index(
            {
                "response_id": response_id,
                "provider": self.provider,
                "query_type": query_type,
                "mpn": mpn,
                "request_timestamp": now,
                "response_timestamp": now,
                "http_status": "" if http_status is None else str(http_status),
                "raw_response_path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "success": "true" if success else "false",
                "error_code": error_code,
                "error_message": error_message,
            }
        )
        return path

    def _append_index(self, row: Dict[str, str]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self.index_path.is_file()
        with self.index_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=INDEX_FIELDS)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
