"""Persistent JSON cache keyed by provider, query type, MPN, manufacturer, and region."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.providers.settings import ROOT, get_settings

SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def cache_key(query_type: str, mpn: str, manufacturer: str = "", region: str = "") -> str:
    parts = [query_type, mpn, manufacturer or "_", region or "_"]
    joined = "__".join(SAFE.sub("_", part.strip())[:80] for part in parts)
    return joined or "unknown"


class ApiCache:
    def __init__(self, provider: str, ttl_seconds: Optional[int] = None, root: Optional[Path] = None) -> None:
        self.provider = provider
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else get_settings().cache_ttl_seconds
        self.root = Path(root) if root else ROOT / "data" / "api_cache" / provider
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, query_type: str, mpn: str, manufacturer: str = "", region: str = "") -> Path:
        return self.root / f"{cache_key(query_type, mpn, manufacturer, region)}.json"

    def get(self, query_type: str, mpn: str, manufacturer: str = "", region: str = "") -> Optional[Dict[str, Any]]:
        path = self.path_for(query_type, mpn, manufacturer, region)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        stored_at = float(payload.get("stored_at") or 0)
        if self.ttl_seconds and stored_at and (time.time() - stored_at) > self.ttl_seconds:
            return None
        body = payload.get("body", payload)
        if isinstance(body, dict):
            # Internal metadata lets storage/UI distinguish a cache hit from
            # a fresh provider response. It contains no secrets and is not
            # sent to providers.
            body = dict(body)
            body["_sentinel_cache_stored_at"] = stored_at
            body["_sentinel_cache_ttl_seconds"] = int(payload.get("ttl_seconds") or self.ttl_seconds)
        return body

    def set(self, query_type: str, mpn: str, manufacturer: str, region: str, body: Dict[str, Any]) -> Path:
        path = self.path_for(query_type, mpn, manufacturer, region)
        envelope = {
            "provider": self.provider,
            "query_type": query_type,
            "mpn": mpn,
            "manufacturer": manufacturer,
            "region": region,
            "stored_at": time.time(),
            "ttl_seconds": self.ttl_seconds,
            "body": body,
        }
        path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
        return path

    def clear_expired(self) -> int:
        removed = 0
        now = time.time()
        for path in self.root.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            stored_at = float(payload.get("stored_at") or 0)
            ttl = int(payload.get("ttl_seconds") or self.ttl_seconds)
            if stored_at and ttl and (now - stored_at) > ttl:
                path.unlink(missing_ok=True)
                removed += 1
        return removed

    def clear_mpn(self, mpn: str) -> int:
        removed = 0
        needle = SAFE.sub("_", mpn)
        for path in self.root.glob("*.json"):
            if needle in path.name:
                path.unlink(missing_ok=True)
                removed += 1
        return removed

    def clear_all(self) -> int:
        removed = 0
        for path in self.root.glob("*.json"):
            path.unlink(missing_ok=True)
            removed += 1
        return removed


def clear_provider(provider: str) -> int:
    return ApiCache(provider).clear_all()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="SENTINEL provider cache maintenance")
    parser.add_argument("--clear-expired", action="store_true")
    parser.add_argument("--clear-provider", choices=["digikey", "nexar"])
    parser.add_argument("--clear-mpn")
    args = parser.parse_args(argv)
    total = 0
    providers = [args.clear_provider] if args.clear_provider else ["digikey", "nexar"]
    for provider in providers:
        cache = ApiCache(provider)
        if args.clear_expired:
            total += cache.clear_expired()
        if args.clear_mpn:
            total += cache.clear_mpn(args.clear_mpn)
        if args.clear_provider and not args.clear_expired and not args.clear_mpn:
            total += cache.clear_all()
    print(f"cache_entries_removed={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
