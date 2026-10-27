"""DigiKey Product Information V4 provider — Nexar GraphQL provider."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.industry_data.api_cache import ApiCache
from src.industry_data.raw_response_store import RawResponseStore
from src.providers.base import ProviderPart
from src.providers.http import HttpTransport
from src.providers.nexar.client import NexarClient
from src.providers.nexar.mapper import parse_part_node, to_provider_part
from src.providers.nexar.queries import MULTI_MATCH, SEARCH_MPN
from src.providers.settings import ProviderSettings, get_settings
from src.providers.status_store import ProviderStatusStore

logger = logging.getLogger("sentinel.providers.nexar")

REGION_COUNTRY = {"US": ("US", "USD"), "IN": ("IN", "INR"), "EU": ("DE", "EUR"), "APAC": ("SG", "USD")}


def graphql_error_category(errors: Any) -> str:
    """Classify safe Nexar GraphQL failure modes without treating them as no-match."""
    text = " ".join(str((item or {}).get("message") or "") for item in (errors or [])).lower()
    if "part limit" in text or "quota" in text or "exceeded" in text:
        return "QUOTA_EXHAUSTED"
    if any(token in text for token in ("entitlement", "subscription", "not authorized", "forbidden", "access denied")):
        return "NO_SUPPLY_ENTITLEMENT"
    if any(token in text for token in ("unauthorized", "authentication", "token")):
        return "AUTHENTICATION_FAILURE"
    return "GRAPHQL_ERROR"


class NexarProvider:
    name = "nexar"

    def __init__(
        self,
        settings: Optional[ProviderSettings] = None,
        client: Optional[NexarClient] = None,
        cache: Optional[ApiCache] = None,
        raw_store: Optional[RawResponseStore] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or NexarClient(self.settings, HttpTransport(self.settings))
        self.cache = cache or ApiCache("nexar", ttl_seconds=self.settings.cache_ttl_seconds)
        self.raw_store = raw_store or RawResponseStore("nexar")

    def configured(self) -> bool:
        return self.client.configured()

    def _locale(self, region: str) -> tuple[str, str]:
        country, default_currency = REGION_COUNTRY.get(region.upper(), ("US", "USD"))
        currency = self.settings.target_currency if region.upper() == self.settings.target_region else default_currency
        return country, currency

    def health(self) -> Dict[str, Any]:
        observed = ProviderStatusStore(self.name).read()
        status = "unconfigured"
        if self.configured():
            status = "configured"
            if self.client._access_token:
                status = "authenticated"
        observed_error = observed.get("last_error", "")
        quota_status = "QUOTA_EXHAUSTED" if observed_error == "QUOTA_EXHAUSTED" or "quota" in self.client.last_error.lower() or "part limit" in self.client.last_error.lower() else "UNKNOWN"
        return {
            "provider": self.name,
            "configured": self.configured(),
            "authentication_status": status,
            "scope": self.settings.nexar_scope,
            "quota_status": quota_status,
            "last_error_category": observed_error or self.client.last_error,
            "last_success": self.client.last_success or observed.get("last_success"),
            "last_error": self.client.last_error or observed.get("last_error", ""),
            "last_request_time": self.client.transport.last_request_time or observed.get("last_request"),
            "last_http_status": self.client.transport.last_status or observed.get("last_http_status"),
        }

    def authenticate(self) -> str:
        return self.client.authenticate()

    def get_access_token(self) -> str:
        return self.client.get_access_token()

    def query_graphql(self, query: str, variables: Optional[Dict[str, Any]] = None, mpn: str = "") -> Dict[str, Any]:
        return self.client.query_graphql(query, variables, mpn=mpn)

    def search_part(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart:
        return self._lookup(mpn, manufacturer, region, "search")

    def get_part_details(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart:
        return self._lookup(mpn, manufacturer, region, "details")

    def get_specifications(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart:
        return self._lookup(mpn, manufacturer, region, "specifications")

    def get_pricing(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart:
        return self._lookup(mpn, manufacturer, region, "pricing")

    def get_supply(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart:
        return self._lookup(mpn, manufacturer, region, "supply")

    def get_lifecycle(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart:
        return self._lookup(mpn, manufacturer, region, "lifecycle")

    def get_substitutions(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart:
        return self._lookup(mpn, manufacturer, region, "substitutions")

    def get_documents(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart:
        return self._lookup(mpn, manufacturer, region, "documents")

    def get_alternatives(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart:
        return self.get_substitutions(mpn, manufacturer, region)

    def search_many(self, mpns: List[str], region: str = "US") -> List[ProviderPart]:
        unique = list(dict.fromkeys(mpns))
        batch = unique[: self.settings.batch_size]
        country, currency = self._locale(region)
        queries = [{"mpn": mpn, "limit": 1} for mpn in batch]
        try:
            body = self.query_graphql(MULTI_MATCH, {"queries": queries, "country": country, "currency": currency}, mpn="batch")
        except Exception as exc:
            logger.warning("nexar batch failed: %s", type(exc).__name__)
            return [self.search_part(mpn, region=region) for mpn in batch]
        blocks = ((body.get("data") or {}).get("supMultiMatch") or [])
        if not isinstance(blocks, list):
            blocks = [blocks]
        results: List[ProviderPart] = []
        for mpn, block in zip(batch, blocks):
            parts = (block or {}).get("parts") or []
            node = parts[0] if parts else {}
            parsed = parse_part_node(node)
            part = to_provider_part(parsed, query_type="batch_supply", region=region, raw=body)
            part.mpn = part.mpn or mpn
            results.append(part)
        leftover = unique[self.settings.batch_size :]
        results.extend(self.search_part(mpn, region=region) for mpn in leftover)
        return results

    def _lookup(self, mpn: str, manufacturer: str, region: str, query_type: str) -> ProviderPart:
        cached = self.cache.get(query_type, mpn, manufacturer, region)
        if cached is not None:
            part = self._from_body(cached, mpn, query_type, region)
            part.cache_hit = True
            return part
        if not self.configured():
            return ProviderPart(
                provider=self.name,
                mpn=mpn,
                query_type=query_type,
                success=False,
                error_code="UNCONFIGURED",
                error_message="Nexar credentials are not configured",
            )
        country, currency = self._locale(region)
        q = mpn if not manufacturer else f"{mpn} {manufacturer}"
        try:
            body = self.query_graphql(
                SEARCH_MPN,
                {"q": q, "limit": 3, "country": country, "currency": currency},
                mpn=mpn,
            )
        except Exception as exc:
            logger.warning("nexar lookup failed mpn=%s error=%s", mpn, type(exc).__name__)
            return ProviderPart(
                provider=self.name,
                mpn=mpn,
                query_type=query_type,
                success=False,
                error_code=type(exc).__name__,
                error_message=str(type(exc).__name__),
            )
        http_status = body.get("_http_status")
        errors = body.get("errors")
        success = http_status in (None, 200) and not errors
        error_category = graphql_error_category(errors) if errors else ""
        if errors:
            ProviderStatusStore(self.name).record(
                operation="graphql",
                mpn=mpn,
                http_status=http_status,
                success=False,
                error_category=error_category,
            )
        self.raw_store.save(
            query_type,
            mpn,
            body,
            http_status=http_status,
            success=success,
            error_code=error_category,
            error_message="" if success else "graphql_or_http_error",
        )
        if success:
            self.cache.set(query_type, mpn, manufacturer, region, body)
        return self._from_body(body, mpn, query_type, region)

    def _from_body(self, body: Dict[str, Any], mpn: str, query_type: str, region: str) -> ProviderPart:
        data = body.get("data") or body
        search = data.get("supSearchMpn") or {}
        results = search.get("results") or []
        node = {}
        if results:
            node = results[0].get("part") or {}
            if not node.get("shortDescription"):
                node["shortDescription"] = results[0].get("description") or ""
        parsed = parse_part_node(node)
        part = to_provider_part(parsed, query_type=query_type, region=region, raw=body)
        part.mpn = part.mpn or mpn
        if body.get("errors") or not node:
            part.success = False
            part.error_code = "NO_RESULT" if not body.get("errors") else graphql_error_category(body.get("errors"))
            part.error_message = "No Nexar match" if not body.get("errors") else "Nexar request rejected"
        part.http_status = body.get("_http_status")
        return part
