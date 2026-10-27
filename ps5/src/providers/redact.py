"""Redact secrets from logs and exception text."""

from __future__ import annotations

import re
from typing import Any, Mapping

SECRET_KEYS = {
    "authorization",
    "client_secret",
    "access_token",
    "refresh_token",
    "nexar_client_secret",
    "digikey_client_secret",
    "nexar_access_token",
    "mouser_api_key",
    "apikey",
    "api_key",
}

_BEARER = re.compile(r"(Bearer\s+)([A-Za-z0-9._~\-+/=]+)", re.IGNORECASE)


def redact_text(value: str) -> str:
    return _BEARER.sub(r"\1[REDACTED]", value)


def redact_mapping(data: Mapping[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not data:
        return out
    for key, val in data.items():
        lowered = str(key).lower()
        if lowered in SECRET_KEYS or "secret" in lowered or "token" in lowered:
            out[key] = "[REDACTED]"
        elif isinstance(val, str):
            out[key] = redact_text(val)
        else:
            out[key] = val
    return out
