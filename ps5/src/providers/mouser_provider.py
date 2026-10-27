"""Mouser Search API provider (official Search API, not website scraping)."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from src.industry_data.api_cache import ApiCache
from src.industry_data.raw_response_store import RawResponseStore
from src.providers.base import ProviderDocument, ProviderOffer, ProviderPart, ProviderSpec
from src.providers.http import HttpTransport
from src.providers.settings import ProviderSettings, get_settings
from src.providers.status_store import ProviderStatusStore

logger = logging.getLogger("sentinel.providers.mouser")


def _num(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    text = str(value).replace(",", "").replace("$", "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _int(value: Any) -> Optional[int]:
    num = _num(value)
    return int(num) if num is not None else None


def _lead_time_days(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    text = str(value).strip().lower()
    amount = _num(text)
    if amount is None:
        return None
    if "week" in text:
        return int(amount * 7)
    if "month" in text:
        return int(amount * 30)
    return int(amount)


_BLOCKED_MPN_TOKENS = ("EVM", "EVAL", "DEMO", "KIT", "BOARD", "LAUNCHPAD", "DEVTOOL")


def compatible_manufacturer_mpn(wanted: str, candidate: str) -> bool:
    """Accept exact MPNs and orderable packing suffixes, never eval/dev boards."""
    wanted_key = re.sub(r"[^A-Z0-9]", "", (wanted or "").upper())
    candidate_key = re.sub(r"[^A-Z0-9]", "", (candidate or "").upper())
    if not wanted_key or not candidate_key:
        return False
    if candidate_key == wanted_key:
        return True
    if not candidate_key.startswith(wanted_key):
        return False
    extra = candidate_key[len(wanted_key):]
    if any(token in extra for token in _BLOCKED_MPN_TOKENS):
        return False
    return extra.isalnum() and 1 <= len(extra) <= 8


class MouserProvider:
    name = "mouser"

    def __init__(
        self,
        settings: Optional[ProviderSettings] = None,
        transport: Optional[HttpTransport] = None,
        cache: Optional[ApiCache] = None,
        raw_store: Optional[RawResponseStore] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport or HttpTransport(self.settings)
        self.cache = cache or ApiCache("mouser", ttl_seconds=self.settings.cache_ttl_seconds)
        self.raw_store = raw_store or RawResponseStore("mouser")

    def configured(self) -> bool:
        return self.settings.mouser_configured

    def health(self) -> Dict[str, Any]:
        observed = ProviderStatusStore(self.name).read()
        status = "unconfigured"
        if self.configured():
            status = "configured"
            if observed.get("last_success"):
                status = "authenticated"
        return {
            "provider": self.name,
            "configured": self.configured(),
            "authentication_status": status,
            "api_base": self.settings.mouser_api_base,
            "last_error_category": observed.get("last_error", ""),
            "last_success": self.transport.last_success or observed.get("last_success"),
            "last_error": self.transport.last_error or observed.get("last_error", ""),
            "last_request_time": self.transport.last_request_time or observed.get("last_request"),
            "last_http_status": self.transport.last_status or observed.get("last_http_status"),
        }

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

    def _lookup(self, mpn: str, manufacturer: str, region: str, query_type: str) -> ProviderPart:
        cached = self.cache.get(query_type, mpn, manufacturer, region)
        if cached is not None:
            part = self._map_payload(cached, mpn, query_type, region)
            if part.success:
                part.cache_hit = True
                return part
        if not self.configured():
            return ProviderPart(
                provider=self.name,
                mpn=mpn,
                query_type=query_type,
                success=False,
                error_code="UNCONFIGURED",
                error_message="Mouser Search API key is not configured",
            )
        part_payload = self._search("partnumber", mpn, query_type)
        if not part_payload.get("_ok"):
            return self._error_part(mpn, query_type, part_payload)
        mapped = self._map_payload(part_payload, mpn, query_type, region)
        if mapped.success:
            self.cache.set(query_type, mpn, manufacturer, region, part_payload)
            return mapped
        keyword_payload = self._search("keyword", mpn, query_type)
        if not keyword_payload.get("_ok"):
            return self._error_part(mpn, query_type, keyword_payload)
        mapped = self._map_payload(keyword_payload, mpn, query_type, region)
        if mapped.success:
            self.cache.set(query_type, mpn, manufacturer, region, keyword_payload)
        return mapped

    def _search(self, mode: str, mpn: str, query_type: str) -> Dict[str, Any]:
        if mode == "keyword":
            url = self.settings.mouser_api_base.rstrip("/") + "/search/keyword"
            body: Dict[str, Any] = {
                "SearchByKeywordRequest": {
                    "keyword": mpn,
                    "records": 50,
                    "startingRecord": 0,
                }
            }
        else:
            url = self.settings.mouser_api_base.rstrip("/") + "/search/partnumber"
            body = {
                "SearchByPartRequest": {
                    "mouserPartNumber": mpn,
                    "partSearchOptions": "",
                }
            }
        try:
            response = self.transport.request(
                "POST",
                url,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json=body,
                params={"apiKey": self.settings.mouser_api_key},
                provider=self.name,
                mpn=mpn,
            )
        except Exception as exc:
            logger.warning("mouser lookup failed mpn=%s mode=%s error=%s", mpn, mode, type(exc).__name__)
            return {"_ok": False, "_error_code": type(exc).__name__, "_error_message": type(exc).__name__, "_http_status": None}
        try:
            payload = response.json()
        except Exception:
            payload = {"error": "invalid_json"}
        if not isinstance(payload, dict):
            payload = {"error": "invalid_json"}
        payload["_http_status"] = response.status_code
        if response.status_code >= 400:
            self.raw_store.save(query_type, mpn, payload, http_status=response.status_code, success=False, error_code=f"HTTP_{response.status_code}")
            payload["_ok"] = False
            payload["_error_code"] = "HTTP_401" if response.status_code in {401, 403} else f"HTTP_{response.status_code}"
            payload["_error_message"] = "Mouser Search API request failed"
            return payload
        errors = payload.get("Errors") or []
        if errors:
            message = " ".join(str((item or {}).get("Message") or (item or {}).get("message") or "") for item in errors)
            lowered = message.lower()
            error_code = "AUTHENTICATION_FAILURE" if any(token in lowered for token in ("api key", "invalid", "unauthorized")) else "PROVIDER_ERROR"
            self.raw_store.save(query_type, mpn, payload, http_status=response.status_code, success=False, error_code=error_code)
            payload["_ok"] = False
            payload["_error_code"] = error_code
            payload["_error_message"] = message or "Mouser Search API returned Errors"
            return payload
        self.raw_store.save(query_type, mpn, payload, http_status=response.status_code, success=True)
        payload["_ok"] = True
        return payload

    def _error_part(self, mpn: str, query_type: str, payload: Dict[str, Any]) -> ProviderPart:
        return ProviderPart(
            provider=self.name,
            mpn=mpn,
            query_type=query_type,
            success=False,
            error_code=str(payload.get("_error_code") or "PROVIDER_ERROR"),
            error_message=str(payload.get("_error_message") or "Mouser Search API request failed"),
            http_status=_int(payload.get("_http_status")),
            raw=payload,
        )

    def _map_payload(self, raw: Dict[str, Any], mpn: str, query_type: str, region: str) -> ProviderPart:
        results = raw.get("SearchResults") if isinstance(raw.get("SearchResults"), dict) else raw
        parts = results.get("Parts") if isinstance(results, dict) else None
        if not isinstance(parts, list) or not parts:
            return ProviderPart(
                provider=self.name,
                mpn=mpn,
                query_type=query_type,
                success=False,
                error_code="NO_MATCH",
                error_message="Mouser Search API returned no parts",
                raw=raw,
            )
        wanted = str(mpn or "").strip().upper()
        exact: List[Dict[str, Any]] = []
        compatible: List[Dict[str, Any]] = []
        for item in parts:
            if not isinstance(item, dict):
                continue
            manufacturer_mpn = str(item.get("ManufacturerPartNumber") or "").strip().upper()
            if manufacturer_mpn == wanted:
                exact.append(item)
            elif compatible_manufacturer_mpn(wanted, manufacturer_mpn):
                compatible.append(item)
        chosen = exact[0] if exact else (compatible[0] if compatible else None)
        if chosen is None:
            return ProviderPart(
                provider=self.name,
                mpn=mpn,
                query_type=query_type,
                success=False,
                error_code="NO_MATCH",
                error_message="Mouser Search API returned no compatible manufacturer part number",
                raw=raw,
            )
        return self._map_part(chosen, mpn, query_type, region, raw)

    def _map_part(self, part: Dict[str, Any], mpn: str, query_type: str, region: str, raw: Dict[str, Any]) -> ProviderPart:
        specs: List[ProviderSpec] = []
        for attribute in part.get("ProductAttributes") or []:
            if not isinstance(attribute, dict):
                continue
            name = str(attribute.get("AttributeName") or attribute.get("Name") or "").strip()
            value = str(attribute.get("AttributeValue") or attribute.get("Value") or "").strip()
            if name and value:
                specs.append(ProviderSpec(parameter_name=name, value=value))
        documents: List[ProviderDocument] = []
        datasheet = str(part.get("DataSheetUrl") or "").strip()
        if datasheet:
            documents.append(ProviderDocument(title="Datasheet", url=datasheet, document_type="datasheet"))
        detail_url = str(part.get("ProductDetailUrl") or "").strip()
        if detail_url:
            documents.append(ProviderDocument(title="Mouser product page", url=detail_url, document_type="product"))
        price_breaks = part.get("PriceBreaks") or []
        first_price = price_breaks[0] if price_breaks and isinstance(price_breaks[0], dict) else {}
        stock = _int(part.get("AvailabilityInStock") or part.get("Availability"))
        country, currency_default = ("IN", "INR") if region.upper() == "IN" else ("US", "USD")
        offer = ProviderOffer(
            vendor_name="Mouser Electronics",
            vendor_part_number=str(part.get("MouserPartNumber") or ""),
            region=region.upper(),
            country=country,
            stock_quantity=stock,
            stock_status=str(part.get("Availability") or ""),
            lead_time_days=_lead_time_days(part.get("LeadTime")),
            moq=_int(part.get("Min")),
            unit_price=_num(first_price.get("Price")),
            currency=str(first_price.get("Currency") or currency_default),
            authorized=True,
        )
        replacements = [str(part.get("SuggestedReplacement") or "").strip()] if part.get("SuggestedReplacement") else []
        return ProviderPart(
            provider=self.name,
            mpn=str(part.get("ManufacturerPartNumber") or mpn),
            manufacturer=str(part.get("Manufacturer") or ""),
            description=str(part.get("Description") or ""),
            category=str(part.get("Category") or ""),
            package="",
            lifecycle_status=str(part.get("LifecycleStatus") or ""),
            lifecycle_source_status=str(part.get("LifecycleStatus") or ""),
            datasheet_url=datasheet,
            specifications=specs,
            documents=documents,
            offers=[offer],
            substitutions=replacements,
            raw=raw,
            query_type=query_type,
            success=True,
            http_status=_int(raw.get("_http_status")),
        )
