"""DigiKey OAuth2 token manager (Product Information V4)."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

from src.providers.http import HttpTransport
from src.providers.redact import redact_text
from src.providers.settings import ProviderSettings, get_settings

logger = logging.getLogger("sentinel.providers.digikey")

AUTHORIZE_URL = "https://api.digikey.com/v1/oauth2/authorize"
TOKEN_PATH = "/v1/oauth2/token"


class DigiKeyAuthManager:
    def __init__(self, settings: Optional[ProviderSettings] = None, transport: Optional[HttpTransport] = None) -> None:
        self.settings = settings or get_settings()
        self.transport = transport or HttpTransport(self.settings)
        self._access_token: str = ""
        self._refresh_token: str = self.settings.digikey_refresh_token
        self._expires_at: float = 0.0
        self.last_error: str = ""
        self.last_success: str = ""

    def configured(self) -> bool:
        return self.settings.digikey_configured

    def invalidate_token(self) -> None:
        self._access_token = ""
        self._expires_at = 0.0

    def get_valid_access_token(self) -> str:
        if self._access_token and time.time() < (self._expires_at - 30):
            return self._access_token
        if self._refresh_token:
            try:
                return self.refresh_access_token()
            except Exception as exc:
                logger.warning("digikey refresh failed; falling back to client credentials: %s", type(exc).__name__)
        return self.get_access_token()

    def get_access_token(self) -> str:
        if not self.configured():
            raise RuntimeError("DigiKey credentials are not configured")
        return self._token_request(
            {
                "client_id": self.settings.digikey_client_id,
                "client_secret": self.settings.digikey_client_secret,
                "grant_type": "client_credentials",
            }
        )

    def refresh_access_token(self) -> str:
        if not self._refresh_token:
            return self.get_access_token()
        return self._token_request(
            {
                "client_id": self.settings.digikey_client_id,
                "client_secret": self.settings.digikey_client_secret,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
            }
        )

    def _token_request(self, data: dict) -> str:
        url = self.settings.digikey_api_base.rstrip("/") + TOKEN_PATH
        response = self.transport.request(
            "POST",
            url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=data,
            provider="digikey",
            mpn="oauth",
        )
        if response.status_code >= 400:
            self.last_error = f"HTTP {response.status_code}"
            raise RuntimeError(f"DigiKey token request failed: HTTP {response.status_code}")
        payload = response.json()
        token = payload.get("access_token") or ""
        if not token:
            self.last_error = "missing_access_token"
            raise RuntimeError("DigiKey token response did not include access_token")
        self._access_token = token
        self._refresh_token = payload.get("refresh_token") or self._refresh_token
        expires_in = int(payload.get("expires_in") or 1800)
        self._expires_at = time.time() + expires_in
        self.last_success = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.last_error = ""
        logger.info("digikey oauth token acquired expires_in=%s", expires_in)
        return token

    def persist_debug_state(self, path: Path) -> None:
        """Write non-secret token metadata only (never the token)."""
        path.write_text(
            json.dumps({"expires_at": self._expires_at, "has_token": bool(self._access_token)}, indent=2),
            encoding="utf-8",
        )

    def redact(self, value: str) -> str:
        return redact_text(value)
