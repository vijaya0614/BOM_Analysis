"""DigiKey Product Information V4 provider."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from src.industry_data.api_cache import ApiCache
from src.industry_data.raw_response_store import RawResponseStore
from src.providers.base import ProviderDocument, ProviderOffer, ProviderPart, ProviderSpec
from src.providers.digikey_auth import DigiKeyAuthManager
from src.providers.http import HttpTransport
from src.providers.settings import ProviderSettings, get_settings
from src.providers.status_store import ProviderStatusStore

logger = logging.getLogger("sentinel.providers.digikey")

REGION_SITE = {
    "US": ("US", "USD"),
    "IN": ("IN", "INR"),
    "EU": ("DE", "EUR"),
    "APAC": ("SG", "USD"),
}


def _num(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> Optional[int]:
    num = _num(value)
    return int(num) if num is not None else None


def _weeks_to_days(value: Any) -> Optional[int]:
    weeks = _num(value)
    if weeks is None:
        return None
    return int(weeks * 7)


class DigiKeyProvider:
    name = "digikey"

    def __init__(
        self,
        settings: Optional[ProviderSettings] = None,
        auth: Optional[DigiKeyAuthManager] = None,
        transport: Optional[HttpTransport] = None,
        cache: Optional[ApiCache] = None,
        raw_store: Optional[RawResponseStore] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport or HttpTransport(self.settings)
        self.auth = auth or DigiKeyAuthManager(self.settings, self.transport)
        self.cache = cache or ApiCache("digikey", ttl_seconds=self.settings.cache_ttl_seconds)
        self.raw_store = raw_store or RawResponseStore("digikey")

    def configured(self) -> bool:
        return self.auth.configured()

    def health(self) -> Dict[str, Any]:
        observed = ProviderStatusStore(self.name).read()
        status = "unconfigured"
        if self.configured():
            status = "account_id_missing" if not self.settings.digikey_account_id else "configured"
            if self.auth._access_token and self.settings.digikey_account_id:
                status = "authenticated"
        observed_error = observed.get("last_error", "")
        error_category = observed_error
        if observed_error == "HTTP 401" and self.settings.digikey_account_id:
            error_category = "PROVIDER_AUTHORIZATION_REQUIRED"
        return {
            "provider": self.name,
            "configured": self.configured(),
            "product_access_ready": bool(self.settings.digikey_account_id),
            "authentication_status": status,
            "environment": self.settings.digikey_environment,
            "api_base": self.settings.digikey_api_base,
            "last_error_category": error_category,
            "last_success": self.auth.last_success or self.transport.last_success or observed.get("last_success"),
            "last_error": self.auth.last_error or self.transport.last_error or observed.get("last_error", ""),
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

    def _headers(self, region: str) -> Dict[str, str]:
        site, currency = REGION_SITE.get(region.upper(), ("US", "USD"))
        token = self.auth.get_valid_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-DIGIKEY-Client-Id": self.settings.digikey_client_id,
            "X-DIGIKEY-Locale-Site": site,
            "X-DIGIKEY-Locale-Language": "en",
            "X-DIGIKEY-Locale-Currency": currency,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.settings.digikey_account_id:
            headers["X-DIGIKEY-Account-Id"] = self.settings.digikey_account_id
        return headers

    def _lookup(self, mpn: str, manufacturer: str, region: str, query_type: str) -> ProviderPart:
        cached = self.cache.get(query_type, mpn, manufacturer, region)
        if cached is not None:
            part = self._map_payload(cached.get("body") or cached, mpn, query_type, region)
            part.cache_hit = True
            return part
        if not self.configured():
            return ProviderPart(
                provider=self.name,
                mpn=mpn,
                query_type=query_type,
                success=False,
                error_code="UNCONFIGURED",
                error_message="DigiKey credentials are not configured",
            )
        product_access_attempted = False
        try:
            keyword_body = self._keyword_search(mpn, manufacturer, region)
            product_access_attempted = True
            # Product Information calls can return 401 when an otherwise valid
            # cached token has just been revoked or expired.  The auth manager
            # invalidates that token in ``_keyword_search``; retry exactly once
            # so this is recovery, not an uncontrolled retry loop.
            if self._status(keyword_body) == 401:
                keyword_body = self._keyword_search(mpn, manufacturer, region)
            self._raise_for_error(keyword_body, query_type, mpn)
            details_body: Dict[str, Any] = {}
            dkpn = self._extract_dkpn(keyword_body)
            if dkpn:
                details_body = self._product_details(dkpn, mpn, region)
                if self._status(details_body) == 401:
                    # A refreshed token is required for the retry.  Re-run the
                    # keyword lookup too because DigiKey product numbers are
                    # search-result specific.
                    self.auth.invalidate_token()
                    keyword_body = self._keyword_search(mpn, manufacturer, region)
                    self._raise_for_error(keyword_body, query_type, mpn)
                    dkpn = self._extract_dkpn(keyword_body)
                    details_body = self._product_details(dkpn, mpn, region) if dkpn else {}
                self._raise_for_error(details_body, query_type, mpn)
            raw = {"keyword": keyword_body, "details": details_body}
            self.raw_store.save(query_type, mpn, raw, http_status=200, success=True)
            self.cache.set(query_type, mpn, manufacturer, region, raw)
            return self._map_payload(raw, mpn, query_type, region)
        except Exception as exc:
            logger.warning("digikey lookup failed mpn=%s error=%s", mpn, type(exc).__name__)
            match = re.search(r"HTTP\s+(\d{3})", str(exc))
            return ProviderPart(
                provider=self.name,
                mpn=mpn,
                query_type=query_type,
                success=False,
                error_code=("PROVIDER_AUTHORIZATION_REQUIRED" if product_access_attempted and match and match.group(1) == "401" else f"HTTP_{match.group(1)}" if match else type(exc).__name__),
                error_message=str(type(exc).__name__),
            )

    @staticmethod
    def _status(body: Dict[str, Any]) -> Optional[int]:
        value = body.get("_http_status") if isinstance(body, dict) else None
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _raise_for_error(self, body: Dict[str, Any], query_type: str, mpn: str) -> None:
        status = self._status(body)
        if status is not None and status >= 400:
            self.raw_store.save(
                query_type,
                mpn,
                body if isinstance(body, dict) else {"error": "invalid_response"},
                http_status=status,
                success=False,
                error_code=f"HTTP_{status}",
                error_message="DigiKey request failed",
            )
            raise RuntimeError(f"DigiKey request failed: HTTP {status}")

    def _keyword_search(self, mpn: str, manufacturer: str, region: str) -> Dict[str, Any]:
        url = self.settings.digikey_api_base.rstrip("/") + "/products/v4/search/keyword"
        keywords = mpn if not manufacturer else f"{manufacturer} {mpn}"
        response = self.transport.request(
            "POST",
            url,
            headers=self._headers(region),
            json={"Keywords": keywords, "Limit": 5, "Offset": 0},
            provider=self.name,
            mpn=mpn,
        )
        try:
            body = response.json()
        except Exception:
            body = {"error": "invalid_json"}
        body["_http_status"] = response.status_code
        if response.status_code == 401:
            self.auth.invalidate_token()
        return body

    def _product_details(self, product_number: str, mpn: str, region: str) -> Dict[str, Any]:
        encoded = quote(product_number, safe="")
        url = self.settings.digikey_api_base.rstrip("/") + f"/products/v4/search/{encoded}/productdetails"
        response = self.transport.request("GET", url, headers=self._headers(region), provider=self.name, mpn=mpn)
        try:
            body = response.json()
        except Exception:
            body = {"error": "invalid_json"}
        body["_http_status"] = response.status_code
        return body

    def _extract_dkpn(self, keyword_body: Dict[str, Any]) -> str:
        products = keyword_body.get("Products") or keyword_body.get("ExactMatches") or []
        if not products and isinstance(keyword_body.get("ProductList"), list):
            products = keyword_body["ProductList"]
        if products and isinstance(products[0], dict):
            product = products[0].get("Product") if isinstance(products[0].get("Product"), dict) else products[0]
            return str(product.get("DigiKeyProductNumber") or product.get("ProductNumber") or "")
        return ""

    def _map_payload(self, raw: Dict[str, Any], mpn: str, query_type: str, region: str) -> ProviderPart:
        details = raw.get("details") if isinstance(raw.get("details"), dict) else {}
        product = details.get("Product") if isinstance(details.get("Product"), dict) else details
        if not product:
            keyword = raw.get("keyword") if isinstance(raw.get("keyword"), dict) else raw
            products = keyword.get("Products") or keyword.get("ExactMatches") or keyword.get("ProductList") or []
            if products and isinstance(products[0], dict):
                product = products[0].get("Product") if isinstance(products[0].get("Product"), dict) else products[0]
            else:
                product = {}
        manufacturer = ""
        mfr = product.get("Manufacturer")
        if isinstance(mfr, dict):
            manufacturer = str(mfr.get("Name") or "")
        elif mfr:
            manufacturer = str(mfr)
        parameters: List[ProviderSpec] = []
        package = ""
        for param in product.get("Parameters") or []:
            name = str(param.get("ParameterName") or param.get("ParameterText") or "")
            value = str(param.get("ValueText") or param.get("Value") or "")
            parameters.append(ProviderSpec(parameter_name=name, value=value))
            if "package" in name.lower() or "case/package" in name.lower():
                package = package or value
        docs = []
        for media in product.get("MediaLinks") or product.get("Datasheets") or []:
            url = str(media.get("Url") or media.get("PDFUrl") or "")
            if url:
                docs.append(ProviderDocument(title=str(media.get("Title") or "Document"), url=url, document_type="datasheet"))
        datasheet = product.get("PrimaryDatasheet") or product.get("DatasheetUrl") or (docs[0].url if docs else "")
        substitutions = []
        for rec in product.get("RecommendedProducts") or []:
            rec_mpn = rec.get("ManufacturerProductNumber") or rec.get("ManufacturerPartNumber")
            if rec_mpn:
                substitutions.append(str(rec_mpn))
        qty = _int(product.get("QuantityAvailable"))
        unit_price = None
        currency = ""
        pricing = product.get("ProductVariations") or product.get("StandardPricing") or []
        if pricing and isinstance(pricing, list):
            first = pricing[0]
            if isinstance(first, dict):
                unit_price = _num(first.get("UnitPrice") or first.get("Price"))
                currency = str(first.get("Currency") or "")
                if qty is None:
                    qty = _int(first.get("QuantityAvailableforPackageType") or first.get("QuantityAvailable"))
        classification = product.get("ProductStatus") or {}
        status_text = ""
        if isinstance(classification, dict):
            status_text = str(classification.get("Status") or classification.get("Id") or "")
        else:
            status_text = str(classification or "")
        category = ""
        cat = product.get("Category") or product.get("Classifications")
        if isinstance(cat, dict):
            category = str(cat.get("Name") or cat.get("CategoryName") or "")
        elif isinstance(cat, list) and cat:
            category = str((cat[0] or {}).get("Name") or "")
        offer = ProviderOffer(
            vendor_name="DigiKey",
            vendor_part_number=str(product.get("DigiKeyProductNumber") or product.get("ProductNumber") or ""),
            region=region,
            country=REGION_SITE.get(region.upper(), ("US", "USD"))[0],
            stock_quantity=qty,
            stock_status="IN_STOCK" if (qty or 0) > 0 else "UNKNOWN",
            lead_time_days=_weeks_to_days(product.get("ManufacturerLeadWeeks")),
            unit_price=unit_price,
            currency=currency,
            authorized=True,
        )
        http_status = (raw.get("keyword") or {}).get("_http_status") if isinstance(raw.get("keyword"), dict) else None
        return ProviderPart(
            provider=self.name,
            mpn=str(product.get("ManufacturerProductNumber") or product.get("ManufacturerPartNumber") or mpn),
            manufacturer=manufacturer,
            description=str(product.get("Description") or product.get("ProductDescription") or ""),
            category=category,
            package=package,
            lifecycle_status=status_text,
            lifecycle_source_status=status_text,
            datasheet_url=str(datasheet or ""),
            specifications=parameters,
            documents=docs,
            offers=[offer] if product else [],
            substitutions=substitutions,
            raw=raw,
            query_type=query_type,
            success=bool(product),
            error_code="" if product else "NO_RESULT",
            error_message="" if product else "No DigiKey match",
            http_status=http_status,
        )
