from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.providers.base import ProviderDocument, ProviderOffer, ProviderPart, ProviderSpec
from src.providers.nexar.models import NexarOffer, NexarPart, NexarPrice, NexarSeller


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


def parse_part_node(node: Dict[str, Any] | None) -> NexarPart:
    node = node or {}
    manufacturer = ((node.get("manufacturer") or {}) or {}).get("name") or ""
    category = ((node.get("category") or {}) or {}).get("name") or ""
    datasheet = node.get("bestDatasheet") or {}
    sellers: List[NexarSeller] = []
    for seller in node.get("sellers") or []:
        offers = []
        for offer in seller.get("offers") or []:
            prices = [
                NexarPrice(
                    quantity=_int(price.get("quantity")),
                    price=_num(price.get("convertedPrice") or price.get("price")),
                    currency=(price.get("convertedCurrency") or price.get("currency") or ""),
                )
                for price in offer.get("prices") or []
            ]
            offers.append(
                NexarOffer(
                    inventory_level=_int(offer.get("inventoryLevel")),
                    moq=_int(offer.get("moq")),
                    factory_lead_days=_int(offer.get("factoryLeadDays")),
                    packaging=str(offer.get("packaging") or ""),
                    prices=prices,
                )
            )
        sellers.append(
            NexarSeller(
                company_name=((seller.get("company") or {}) or {}).get("name") or "",
                country=str(seller.get("country") or ""),
                offers=offers,
            )
        )
    similar = []
    for item in node.get("similarParts") or []:
        mpn = item.get("mpn") if isinstance(item, dict) else None
        if mpn:
            similar.append(str(mpn))
    return NexarPart(
        mpn=str(node.get("mpn") or ""),
        manufacturer=str(manufacturer),
        description=str(node.get("shortDescription") or node.get("name") or ""),
        category=str(category),
        datasheet_url=str(datasheet.get("url") or ""),
        specs=list(node.get("specs") or []),
        sellers=sellers,
        similar_mpns=similar,
        raw=node,
    )


def to_provider_part(part: NexarPart, *, query_type: str, region: str, raw: Dict[str, Any]) -> ProviderPart:
    specs = []
    package = ""
    lifecycle = ""
    for spec in part.specs:
        attr = ((spec.get("attribute") or {}) if isinstance(spec, dict) else {}) or {}
        name = str(attr.get("name") or "")
        value = str(spec.get("displayValue") or spec.get("value") or "")
        specs.append(ProviderSpec(parameter_name=name, value=value))
        lowered = name.lower()
        if "package" in lowered or "case/package" in lowered:
            package = package or value
        if "lifecycle" in lowered or "part status" in lowered or "manufacturer status" in lowered:
            lifecycle = lifecycle or value
    offers: List[ProviderOffer] = []
    for seller in part.sellers:
        for offer in seller.offers:
            unit_price = offer.prices[0].price if offer.prices else None
            currency = offer.prices[0].currency if offer.prices else ""
            offers.append(
                ProviderOffer(
                    vendor_name=seller.company_name,
                    region=region,
                    country=seller.country or region,
                    stock_quantity=offer.inventory_level,
                    stock_status="IN_STOCK" if (offer.inventory_level or 0) > 0 else "UNKNOWN",
                    lead_time_days=offer.factory_lead_days,
                    moq=offer.moq,
                    unit_price=unit_price,
                    currency=currency,
                    packaging=offer.packaging,
                )
            )
    documents = []
    if part.datasheet_url:
        documents.append(ProviderDocument(title="Datasheet", url=part.datasheet_url, document_type="datasheet"))
    return ProviderPart(
        provider="nexar",
        mpn=part.mpn,
        manufacturer=part.manufacturer,
        description=part.description,
        category=part.category,
        package=package,
        lifecycle_status=lifecycle,
        lifecycle_source_status=lifecycle,
        datasheet_url=part.datasheet_url,
        specifications=specs,
        documents=documents,
        offers=offers,
        substitutions=part.similar_mpns,
        raw=raw,
        query_type=query_type,
        success=True,
    )
