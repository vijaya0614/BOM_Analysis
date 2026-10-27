"""Shared provider types. SENTINEL engines depend on this interface, not DigiKey/Nexar SDKs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class ProviderDocument:
    title: str = ""
    url: str = ""
    document_type: str = ""


@dataclass
class ProviderSpec:
    parameter_name: str
    value: str = ""
    unit: str = ""
    condition: str = ""


@dataclass
class ProviderOffer:
    vendor_name: str
    vendor_part_number: str = ""
    region: str = ""
    country: str = ""
    stock_quantity: Optional[int] = None
    stock_status: str = ""
    lead_time_days: Optional[int] = None
    moq: Optional[int] = None
    unit_price: Optional[float] = None
    currency: str = ""
    authorized: Optional[bool] = None
    packaging: str = ""


@dataclass
class ProviderPart:
    provider: str
    mpn: str
    manufacturer: str = ""
    description: str = ""
    category: str = ""
    package: str = ""
    lifecycle_status: str = ""
    lifecycle_source_status: str = ""
    datasheet_url: str = ""
    specifications: List[ProviderSpec] = field(default_factory=list)
    documents: List[ProviderDocument] = field(default_factory=list)
    offers: List[ProviderOffer] = field(default_factory=list)
    substitutions: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)
    query_type: str = ""
    success: bool = True
    error_code: str = ""
    error_message: str = ""
    http_status: Optional[int] = None
    cache_hit: bool = False


class PartProvider(Protocol):
    name: str

    def configured(self) -> bool: ...
    def health(self) -> Dict[str, Any]: ...
    def search_part(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart: ...
    def get_part_details(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart: ...
    def get_specifications(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart: ...
    def get_pricing(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart: ...
    def get_supply(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart: ...
    def get_lifecycle(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart: ...
    def get_substitutions(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart: ...
    def get_documents(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart: ...
    def get_alternatives(self, mpn: str, manufacturer: str = "", region: str = "US") -> ProviderPart: ...
