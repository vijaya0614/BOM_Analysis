"""HTTP helper with retries, backoff, and redacted logging."""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, Optional

import httpx

from src.providers.redact import redact_mapping, redact_text
from src.providers.settings import ProviderSettings, get_settings
from src.providers.status_store import ProviderStatusStore

logger = logging.getLogger("sentinel.providers")

RETRY_STATUSES = {408, 409, 429, 500, 502, 503, 504}


class HttpTransport:
    def __init__(self, settings: Optional[ProviderSettings] = None) -> None:
        self.settings = settings or get_settings()
        self.last_request_time: Optional[str] = None
        self.last_status: Optional[int] = None
        self.last_error: str = ""
        self.last_success: str = ""
        self._last_call_monotonic = 0.0

    def _delay(self) -> None:
        wait_s = self.settings.request_delay_ms / 1000.0
        elapsed = time.monotonic() - self._last_call_monotonic
        if wait_s and elapsed < wait_s:
            time.sleep(wait_s - elapsed)

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        json: Any = None,
        data: Any = None,
        params: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
        provider: str = "",
        mpn: str = "",
    ) -> httpx.Response:
        last_exc: Optional[Exception] = None
        response: Optional[httpx.Response] = None
        logged_url = re.sub(r"(apiKey=)[^&]+", r"\1[REDACTED]", url, flags=re.IGNORECASE)
        for attempt in range(self.settings.max_retries + 1):
            self._delay()
            try:
                logger.info(
                    "provider=%s method=%s url=%s mpn=%s attempt=%s",
                    provider,
                    method,
                    logged_url,
                    mpn,
                    attempt,
                )
                logger.debug("request_headers=%s", redact_mapping(headers or {}))
                started = time.monotonic()
                with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                    response = client.request(method, url, headers=headers, json=json, data=data, params=params)
                latency_ms = int((time.monotonic() - started) * 1000)
                self._last_call_monotonic = time.monotonic()
                self.last_request_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self.last_status = response.status_code
                logger.info(
                    "provider=%s mpn=%s status=%s latency_ms=%s retry=%s",
                    provider,
                    mpn,
                    response.status_code,
                    latency_ms,
                    attempt,
                )
                if response.status_code in RETRY_STATUSES and attempt < self.settings.max_retries:
                    sleep_for = (self.settings.backoff_factor ** attempt)
                    logger.warning(
                        "provider=%s mpn=%s backing off seconds=%s status=%s",
                        provider,
                        mpn,
                        sleep_for,
                        response.status_code,
                    )
                    time.sleep(sleep_for)
                    continue
                if response.status_code >= 400:
                    self.last_error = f"HTTP {response.status_code}"
                else:
                    self.last_error = ""
                    self.last_success = self.last_request_time
                if provider:
                    ProviderStatusStore(provider).record(
                        operation=url.rsplit("/", 1)[-1], mpn=mpn, http_status=response.status_code,
                        success=response.status_code < 400, error_category=self.last_error,
                        duration_ms=latency_ms,
                    )
                return response
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                self.last_error = redact_text(type(exc).__name__)
                if provider:
                    ProviderStatusStore(provider).record(
                        operation=url.rsplit("/", 1)[-1], mpn=mpn, success=False,
                        error_category=type(exc).__name__,
                    )
                logger.warning("provider=%s mpn=%s transport_error=%s retry=%s", provider, mpn, type(exc).__name__, attempt)
                if attempt < self.settings.max_retries:
                    time.sleep(self.settings.backoff_factor ** attempt)
                    continue
                raise
        if response is not None:
            return response
        raise last_exc or RuntimeError("HTTP request failed")
