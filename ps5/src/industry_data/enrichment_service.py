"""Lifecycle + spec + vendor enrichment from DigiKey/Nexar. Unique MPNs only."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.industry_data.csv_store import (
    append_rows,
    find_model_by_mpn,
    read_csv,
    stable_id,
    upsert_by_key,
    upsert_rows,
)
from src.industry_data.mpn_resolver import normalize_mpn, resolve_mpn
from src.industry_data.provenance import ProvenanceStore
from src.industry_data.source_registry import SourceRegistry
from src.providers.base import ProviderPart
from src.providers.digikey_provider import DigiKeyProvider
from src.providers.mouser_provider import MouserProvider
from src.providers.nexar_provider import NexarProvider
from src.providers.settings import ROOT, get_settings

LIFECYCLE_MAP = {
    "active": "ACTIVE",
    "nrnd": "NRND",
    "not recommended for new designs": "NRND",
    "ltb": "LTB",
    "last time buy": "LTB",
    "eol": "EOL",
    "end of life": "EOL",
    "obsolete": "OBSOLETE",
    "discontinued": "OBSOLETE",
    "unconfirmed": "UNCONFIRMED",
}


def map_lifecycle(raw: str) -> str:
    if not raw:
        return "UNKNOWN"
    key = raw.strip().lower()
    return LIFECYCLE_MAP.get(key, "UNCONFIRMED" if key else "UNKNOWN")


def _providers(names: Iterable[str]):
    wanted = {name.lower() for name in names}
    out = []
    if "digikey" in wanted:
        out.append(DigiKeyProvider())
    if "nexar" in wanted:
        out.append(NexarProvider())
    if "mouser" in wanted:
        out.append(MouserProvider())
    return out


def unique_mpns(product_ids: Optional[List[str]] = None) -> List[Dict[str, str]]:
    lines = read_csv("bom_lines.csv")
    if product_ids:
        wanted = set(product_ids)
        lines = [row for row in lines if row.get("product_id") in wanted]
    seen = {}
    for row in lines:
        mpn = row.get("original_mpn") or ""
        if not mpn:
            continue
        key = normalize_mpn(mpn)
        seen.setdefault(
            key,
            {
                "original_mpn": mpn,
                "manufacturer": row.get("original_manufacturer") or "",
                "component_model_id": row.get("component_model_id") or "",
            },
        )
    return list(seen.values())


def _vendor_id(name: str, region: str, country: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in f"{name}_{region}_{country}")
    return f"vnd_{slug[:40]}"


def persist_part(part: ProviderPart, model_id: str, region: str, source_id: str, provenance: ProvenanceStore) -> Dict[str, int]:
    stats = {"vendor_records": 0, "specs": 0, "documents": 0, "lifecycle": 0, "conflicts": 0}
    if not part.success:
        return stats
    provenance_label = "REAL_DISTRIBUTOR_DATA"
    existing_model = next((row for row in read_csv("component_models.csv") if row.get("component_model_id") == model_id), {})
    # Provider facts enrich a BOM model but never replace BOM identity
    # with a different distributor hit (eval boards, packing aliases, etc.).
    model_row = {
        "component_model_id": model_id,
        "manufacturer": existing_model.get("manufacturer") or part.manufacturer or "",
        "mpn": existing_model.get("mpn") or part.mpn or "",
        "normalized_mpn": normalize_mpn(existing_model.get("mpn") or part.mpn or ""),
        "description": existing_model.get("description") or part.description or "",
        "package": existing_model.get("package") or part.package or "",
        "mounting_type": existing_model.get("mounting_type", ""),
        "component_category": existing_model.get("component_category") or part.category or "",
        "datasheet_url": existing_model.get("datasheet_url") or part.datasheet_url or "",
        "lifecycle_status": map_lifecycle(part.lifecycle_status) if part.lifecycle_status else existing_model.get("lifecycle_status", "UNKNOWN"),
    }
    upsert_by_key(
        "component_models.csv",
        "component_model_id",
        model_row,
    )
    if part.datasheet_url:
        provenance.record(
            source_id=source_id,
            entity_type="component_model",
            entity_id=model_id,
            field_name="datasheet_url",
            source_type=part.provider,
            data_provenance=provenance_label,
            confidence="MEDIUM",
        )
    if part.lifecycle_status:
        upsert_rows(
            "lifecycle_records.csv",
            ["component_model_id", "source_id"],
            [
                {
                    "lifecycle_id": stable_id("lc", model_id, source_id),
                    "component_model_id": model_id,
                    "status": map_lifecycle(part.lifecycle_status),
                    "source_status": part.lifecycle_source_status or part.lifecycle_status,
                    "status_date": "",
                    "announcement_date": "",
                    "last_order_date": "",
                    "last_ship_date": "",
                    "replacement_mpn": "",
                    "pcn_number": "",
                    "support_status": "",
                    "source_id": source_id,
                    "confidence": "MEDIUM",
                }
            ],
        )
        stats["lifecycle"] = 1
        provenance.record(
            source_id=source_id,
            entity_type="lifecycle",
            entity_id=model_id,
            field_name="status",
            source_type=part.provider,
            data_provenance=provenance_label,
            confidence="MEDIUM",
        )
    spec_rows = []
    for spec in part.specifications:
        spec_rows.append(
            {
                "spec_id": f"sp_{uuid.uuid4().hex[:12]}",
                "component_model_id": model_id,
                "parameter_name": spec.parameter_name,
                "nominal_value": spec.value,
                "min_value": "",
                "max_value": "",
                "unit": spec.unit,
                "condition": spec.condition,
                "source_document": part.provider,
                "source_page": "",
                "confidence": "MEDIUM",
                "provenance": provenance_label,
            }
        )
    if spec_rows:
        append_rows("component_specs.csv", spec_rows)
        stats["specs"] = len(spec_rows)
    existing_documents = {(row.get("component_model_id"), row.get("url")) for row in read_csv("documents.csv")}
    document_rows = []
    for document in part.documents:
        if not document.url or (model_id, document.url) in existing_documents:
            continue
        document_rows.append(
            {
                "document_id": f"doc_{uuid.uuid4().hex[:12]}",
                "component_model_id": model_id,
                "product_id": "",
                "document_type": document.document_type or "datasheet",
                "title": document.title or "Provider document",
                "url": document.url,
                "revision": "",
                "publication_date": "",
                "source_id": source_id,
                "filename": "",
                "file_hash": "",
                "source_path": "",
                "imported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "extraction_status": "PROVIDER_REFERENCE",
                "confidence": "MEDIUM",
                "source_page": "",
            }
        )
    if document_rows:
        append_rows("documents.csv", document_rows)
        stats["documents"] = len(document_rows)
    cached_at = part.raw.get("_sentinel_cache_stored_at") if isinstance(part.raw, dict) else None
    cache_ttl = part.raw.get("_sentinel_cache_ttl_seconds") if isinstance(part.raw, dict) else None
    if cached_at and cache_ttl:
        retrieved_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(cached_at)))
        expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(cached_at) + float(cache_ttl)))
        retrieval_state = "CACHED" if time.time() <= float(cached_at) + float(cache_ttl) else "STALE"
    else:
        retrieved_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        expires_at = ""
        retrieval_state = "CACHED" if part.cache_hit else "LIVE"
    for offer in part.offers:
        vendor_id = _vendor_id(offer.vendor_name or part.provider, offer.region or region, offer.country or region)
        upsert_by_key(
            "vendors.csv",
            "vendor_id",
            {
                "vendor_id": vendor_id,
                "vendor_name": offer.vendor_name or part.provider,
                "region": offer.region or region,
                "country": offer.country or region,
                "vendor_type": "distributor",
            },
        )
        upsert_rows(
            "vendor_supply_records.csv",
            ["component_model_id", "vendor_id", "provider"],
            [
                {
                    "vendor_record_id": stable_id("vs", model_id, vendor_id, part.provider),
                    "component_model_id": model_id,
                    "vendor_id": vendor_id,
                    "vendor_part_number": offer.vendor_part_number,
                    "region": offer.region or region,
                    "country": offer.country or region,
                    "stock_quantity": "" if offer.stock_quantity is None else str(offer.stock_quantity),
                    "stock_status": offer.stock_status,
                    "lead_time_days": "" if offer.lead_time_days is None else str(offer.lead_time_days),
                    "moq": "" if offer.moq is None else str(offer.moq),
                    "unit_price": "" if offer.unit_price is None else str(offer.unit_price),
                    "currency": offer.currency,
                    "authorized": "" if offer.authorized is None else str(offer.authorized),
                    "last_updated": retrieved_at,
                    "retrieved_at": retrieved_at,
                    "expires_at": expires_at,
                    "retrieval_state": retrieval_state,
                    "provider": part.provider,
                    "source_id": source_id,
                    "data_provenance": provenance_label,
                    "confidence": "MEDIUM",
                }
            ],
        )
        append_rows(
            "vendor_stock_snapshots.csv",
            [
                {
                    "snapshot_id": f"snap_{uuid.uuid4().hex[:12]}",
                    "component_model_id": model_id,
                    "vendor_id": vendor_id,
                    "timestamp": retrieved_at,
                    "stock_quantity": "" if offer.stock_quantity is None else str(offer.stock_quantity),
                    "stock_status": offer.stock_status,
                    "lead_time_days": "" if offer.lead_time_days is None else str(offer.lead_time_days),
                    "unit_price": "" if offer.unit_price is None else str(offer.unit_price),
                    "currency": offer.currency,
                    "region": offer.region or region,
                    "source": part.provider,
                    "data_provenance": provenance_label,
                }
            ],
        )
        stats["vendor_records"] += 1
    return stats


def detect_conflicts(model_id: str) -> int:
    records = [row for row in read_csv("lifecycle_records.csv") if row.get("component_model_id") == model_id]
    statuses = {(row.get("source_id"), row.get("status"), row.get("source_status")) for row in records}
    unique_status = {row.get("status") for row in records if row.get("status")}
    if len(unique_status) <= 1:
        return 0
    providers = list(unique_status)
    append_rows(
        "data_conflicts.csv",
        [
            {
                "component_model_id": model_id,
                "field_name": "lifecycle_status",
                "provider_a": "provider_a",
                "value_a": providers[0],
                "provider_b": "provider_b",
                "value_b": providers[1] if len(providers) > 1 else "",
                "detected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "resolution_status": "UNRESOLVED",
            }
        ],
    )
    _ = statuses
    return 1


def run_enrichment(
    *,
    mpns: Optional[List[str]] = None,
    product_ids: Optional[List[str]] = None,
    providers: Optional[List[str]] = None,
    region: Optional[str] = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    settings = get_settings()
    region = (region or settings.target_region).upper()
    provider_names = providers or ["digikey", "nexar", "mouser"]
    instances = _providers(provider_names)
    registry = SourceRegistry()
    provenance = ProvenanceStore()
    if mpns:
        targets = [{"original_mpn": m, "manufacturer": "", "component_model_id": ""} for m in mpns]
        bom_line_count = 0
    else:
        lines = read_csv("bom_lines.csv")
        if product_ids:
            lines = [row for row in lines if row.get("product_id") in product_ids]
        bom_line_count = len(lines)
        targets = unique_mpns(product_ids)
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_bom_lines": bom_line_count,
        "unique_mpns": len(targets),
        "resolved": 0,
        "unresolved": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "api_calls": 0,
        "errors": 0,
        "conflicts": 0,
        "digikey_matches": 0,
        "nexar_matches": 0,
        "mouser_matches": 0,
        "vendor_records": 0,
        "technical_fields_enriched": 0,
        "lifecycle_fields_enriched": 0,
        "failed": [],
        "providers": {name: {"attempted": 0, "resolved": 0, "errors": 0, "last_error": ""} for name in provider_names},
    }
    for target in targets:
        resolution = resolve_mpn(target["original_mpn"], target.get("manufacturer") or "")
        if resolution.resolution_status != "RESOLVED":
            report["unresolved"] += 1
            continue
        model = find_model_by_mpn(resolution.normalized_mpn, resolution.normalized_manufacturer)
        model_id = (model or {}).get("component_model_id") or target.get("component_model_id") or f"mdl_{uuid.uuid4().hex[:12]}"
        matched_any = False
        for provider in instances:
            if not getattr(provider, "configured", lambda: True)():
                continue
            provider_report = report["providers"].setdefault(provider.name, {"attempted": 0, "resolved": 0, "errors": 0, "last_error": ""})
            provider_report["attempted"] += 1
            if force_refresh:
                provider.cache.clear_mpn(resolution.normalized_mpn)
            try:
                part = provider.get_part_details(resolution.original_mpn, resolution.normalized_manufacturer, region)
            except Exception as exc:
                report["errors"] += 1
                provider_report["errors"] += 1
                provider_report["last_error"] = type(exc).__name__
                report["failed"].append(
                    {
                        "mpn": resolution.original_mpn,
                        "provider": provider.name,
                        "error": type(exc).__name__,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
                )
                continue
            if part.cache_hit:
                report["cache_hits"] += 1
            else:
                report["cache_misses"] += 1
                report["api_calls"] += 1
            if not part.success:
                report["errors"] += 1
                provider_report["errors"] += 1
                provider_report["last_error"] = part.error_code or "LOOKUP_FAILED"
                report["failed"].append(
                    {
                        "mpn": resolution.original_mpn,
                        "provider": provider.name,
                        "error": part.error_code or "LOOKUP_FAILED",
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
                )
                continue
            matched_any = True
            provider_report["resolved"] += 1
            if provider.name == "digikey":
                report["digikey_matches"] += 1
            if provider.name == "nexar":
                report["nexar_matches"] += 1
            if provider.name == "mouser":
                report["mouser_matches"] += 1
            source_id = registry.register(
                source_type="REAL_DISTRIBUTOR_DATA",
                title=f"{provider.name} {part.query_type}",
                notes=f"region={region}",
            )
            stats = persist_part(part, model_id, region, source_id, provenance)
            report["vendor_records"] += stats["vendor_records"]
            report["technical_fields_enriched"] += stats["specs"]
            report["lifecycle_fields_enriched"] += stats["lifecycle"]
            report["conflicts"] += detect_conflicts(model_id)
        if matched_any:
            report["resolved"] += 1
        else:
            report["unresolved"] += 1
    out_dir = ROOT / "outputs" / "api_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    path = out_dir / f"enrichment_{stamp}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(path)
    return report


def latest_status() -> Dict[str, Any]:
    folder = ROOT / "outputs" / "api_reports"
    files = sorted(folder.glob("enrichment_*.json")) if folder.is_dir() else []
    if not files:
        return {"status": "idle"}
    return json.loads(files[-1].read_text(encoding="utf-8"))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Enrich unique MPNs via DigiKey/Nexar")
    parser.add_argument("--mpn")
    parser.add_argument("--product")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--providers", default="digikey,nexar,mouser")
    parser.add_argument("--region")
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args(argv)
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    if args.mpn:
        report = run_enrichment(mpns=[args.mpn], providers=providers, region=args.region, force_refresh=args.force_refresh)
    elif args.product:
        report = run_enrichment(product_ids=[args.product], providers=providers, region=args.region, force_refresh=args.force_refresh)
    else:
        report = run_enrichment(providers=providers, region=args.region, force_refresh=args.force_refresh)
    print(json.dumps({k: v for k, v in report.items() if k != "failed"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
