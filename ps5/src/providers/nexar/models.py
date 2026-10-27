from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class NexarPrice:
    quantity: Optional[int] = None
    price: Optional[float] = None
    currency: str = ""


@dataclass
class NexarOffer:
    inventory_level: Optional[int] = None
    moq: Optional[int] = None
    factory_lead_days: Optional[int] = None
    packaging: str = ""
    prices: List[NexarPrice] = field(default_factory=list)


@dataclass
class NexarSeller:
    company_name: str = ""
    country: str = ""
    offers: List[NexarOffer] = field(default_factory=list)


@dataclass
class NexarPart:
    mpn: str = ""
    manufacturer: str = ""
    description: str = ""
    category: str = ""
    datasheet_url: str = ""
    specs: List[Dict[str, Any]] = field(default_factory=list)
    sellers: List[NexarSeller] = field(default_factory=list)
    similar_mpns: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)
