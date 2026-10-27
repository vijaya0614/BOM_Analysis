"""Nexar GraphQL client (current identity + graphql endpoints)."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from src.providers.http import HttpTransport
from src.providers.settings import ProviderSettings, get_settings

logger = logging.getLogger("sentinel.providers.nexar")

TOKEN_URL = "https://identity.nexar.com/connect/token"
GRAPHQL_URL = "https://api.nexar.com/graphql/"


class NexarClient:
    def __init__(self, settings: Optional[ProviderSettings] = None, transport: Optional[HttpTransport] = None) -> None:
        self.settings = settings or get_settings()
        self.transport = transport or HttpTransport(self.settings)
        self._access_token = self.settings.nexar_access_token
        self._expires_at = time.time() + 23 * 3600 if self._access_token else 0.0
        self.last_error = ""
        self.last_success = ""

    def configured(self) -> bool:
        return self.settings.nexar_configured

    def authenticate(self) -> str:
        return self.get_access_token()

    def get_access_token(self) -> str:
        if self._access_token and time.time() < (self._expires_at - 60):
            return self._access_token
        if self.settings.nexar_access_token and not (self.settings.nexar_client_id and self.settings.nexar_client_secret):
            self._access_token = self.settings.nexar_access_token
            self._expires_at = time.time() + 23 * 3600
            return self._access_token
        if not (self.settings.nexar_client_id and self.settings.nexar_client_secret):
            raise RuntimeError("Nexar credentials are not configured")
        response = self.transport.request(
            "POST",
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": self.settings.nexar_client_id,
                "client_secret": self.settings.nexar_client_secret,
                "scope": self.settings.nexar_scope,
            },
            provider="nexar",
            mpn="oauth",
        )
        if response.status_code >= 400:
            self.last_error = f"HTTP {response.status_code}"
            raise RuntimeError(f"Nexar token request failed: HTTP {response.status_code}")
        payload = response.json()
        token = payload.get("access_token") or ""
        if not token:
            self.last_error = "missing_access_token"
            raise RuntimeError("Nexar token response did not include access_token")
        self._access_token = token
        expires_in = int(payload.get("expires_in") or 24 * 3600)
        self._expires_at = time.time() + expires_in
        self.last_success = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.last_error = ""
        return token

    def query_graphql(self, query: str, variables: Optional[Dict[str, Any]] = None, mpn: str = "") -> Dict[str, Any]:
        def execute(token: str):
            return self.transport.request(
                "POST",
                GRAPHQL_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"query": query, "variables": variables or {}},
                provider="nexar",
                mpn=mpn,
            )

        response = execute(self.get_access_token())
        # Retry once only after a 401 when client credentials can obtain a
        # replacement token. Static user-supplied access tokens cannot be
        # refreshed, so returning their 401 keeps the failure explicit.
        if response.status_code == 401 and self.settings.nexar_client_id and self.settings.nexar_client_secret:
            self._access_token = ""
            self._expires_at = 0
            response = execute(self.get_access_token())
        body: Dict[str, Any]
        try:
            body = response.json()
        except Exception:
            body = {"error": "invalid_json", "text": response.text[:2000]}
        if response.status_code == 401:
            self._access_token = ""
            self._expires_at = 0
        if response.status_code >= 400:
            self.last_error = f"HTTP {response.status_code}"
        elif body.get("errors"):
            self.last_error = "graphql_error"
        else:
            self.last_error = ""
            self.last_success = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        body["_http_status"] = response.status_code
        return body
