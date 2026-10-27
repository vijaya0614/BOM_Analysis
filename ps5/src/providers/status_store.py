"""Credential-safe, persistent provider observability metadata."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

from src.providers.settings import ROOT


class ProviderStatusStore:
    """Stores only operational facts; credentials and headers never enter it."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.path = ROOT / "data" / "api_status" / f"{provider}.json"

    def read(self) -> Dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def record(
        self,
        *,
        operation: str,
        mpn: str,
        http_status: int | None = None,
        success: bool,
        error_category: str = "",
        cache_state: str = "MISS",
        duration_ms: int | None = None,
    ) -> Dict[str, Any]:
        previous = self.read()
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        payload = {
            "provider": self.provider,
            "last_request": now,
            "last_operation": operation,
            "last_mpn": mpn,
            "last_http_status": http_status,
            "last_cache_state": cache_state,
            "last_duration_ms": duration_ms,
            "last_error": error_category if not success else "",
            "last_success": now if success else previous.get("last_success"),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload
