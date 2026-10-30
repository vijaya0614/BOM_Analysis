"""Shared JSON handlers for enrichment/provider routes used by both HTTP servers."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from typing import Any, Dict, Optional
from urllib.parse import parse_qs

from src.industry_data.catalog_adapter import component_enrichment_payload
from src.industry_data.csv_store import read_csv
from src.industry_data.data_quality import run_quality
from src.industry_data.enrichment_service import latest_status, run_enrichment
from src.industry_data.importer import ImportPaths, run_import
from src.providers.digikey_provider import DigiKeyProvider
from src.providers.mouser_provider import MouserProvider
from src.providers.nexar_provider import NexarProvider
from src.vendor_feasibility import evaluate_vendor_feasibility
from src.models import ComponentSpec

UPLOAD_SUFFIXES = {".zip", ".csv", ".xls", ".xlsx", ".pdf", ".txt", ".json"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
INDUSTRY_PROJECT_KEYS = {
    "beaglebone-black": "beaglebone_black",
    "beaglebone-black-wireless": "beaglebone_black_wireless",
    "beaglebone-ai": "beaglebone_ai",
    "ti-tida-00222": "ti_tida_00222",
    "ti-tidep-0050": "ti_tidep_0050",
}


def _provider_status_category(provider: Any, part: Any) -> str:
    if getattr(part, "success", False):
        return "SUCCESS"
    error_code = getattr(part, "error_code", "") or ""
    if error_code in {"QUOTA_EXHAUSTED", "PART_LIMIT_EXCEEDED"}:
        return "QUOTA_EXHAUSTED"
    if error_code in {"NO_RESULT", "NO_MATCH"}:
        return "NO_MATCH"
    if error_code in {"HTTP_401", "AUTHENTICATION_FAILURE"}:
        health = provider.health()
        if provider.name == "digikey" and health.get("product_access_ready") and health.get("environment") == "production":
            return "PROVIDER_AUTHORIZATION_REQUIRED"
        return "PROVIDER_AUTHORIZATION_REQUIRED" if health.get("authentication_status") == "authenticated" else "AUTHENTICATION_FAILED"
    if error_code in {"NO_SUPPLY_ENTITLEMENT", "PROVIDER_AUTHORIZATION_REQUIRED"}:
        return "PROVIDER_AUTHORIZATION_REQUIRED"
    if error_code in {"HTTP_429", "RATE_LIMITED"}:
        return "RATE_LIMITED"
    if error_code == "UNCONFIGURED":
        return "UNKNOWN"
    if error_code:
        return "PROVIDER_ERROR"
    return "UNKNOWN"


def providers_health() -> Dict[str, Any]:
    return {
        "digikey": DigiKeyProvider().health(),
        "nexar": NexarProvider().health(),
        "mouser": MouserProvider().health(),
    }


def test_provider(provider_name: str, mpn: str = "TPS5402DGQ") -> Dict[str, Any]:
    mpn = (mpn or "TPS5402DGQ").strip()
    provider_name = (provider_name or "digikey").lower().strip()
    providers = {
        "digikey": DigiKeyProvider,
        "nexar": NexarProvider,
        "mouser": MouserProvider,
    }
    factory = providers.get(provider_name)
    if factory is None:
        return {"error": "INVALID_PROVIDER", "message": "Provider must be 'digikey', 'nexar', or 'mouser'"}
    provider = factory()

    if not provider.configured():
        return {
            "provider": provider_name,
            "mpn": mpn,
            "configured": False,
            "status": "UNCONFIGURED",
            "error_code": "UNCONFIGURED",
            "error_message": f"{provider_name.title()} credentials are not configured in environment",
            "result": None,
        }

    try:
        part = provider.search_part(mpn, region="US")
        status = _provider_status_category(provider, part)

        return {
            "provider": provider_name,
            "mpn": mpn,
            "configured": True,
            "status": status,
            "status_category": status,
            "success": part.success,
            "error_code": part.error_code,
            "error_message": part.error_message,
            "http_status": part.http_status,
            "cache_hit": part.cache_hit,
            "result": {
                "mpn": part.mpn,
                "manufacturer": part.manufacturer,
                "description": part.description,
                "category": part.category,
                "package": part.package,
                "lifecycle_status": part.lifecycle_status,
                "offers_count": len(part.offers),
                "stock": part.offers[0].stock_quantity if part.offers else None,
                "unit_price": part.offers[0].unit_price if part.offers else None,
                "currency": part.offers[0].currency if part.offers else None,
                "lead_time_days": part.offers[0].lead_time_days if part.offers else None,
            } if part.success else None,
        }
    except Exception as exc:
        return {
            "provider": provider_name,
            "mpn": mpn,
            "configured": True,
            "status": "PROVIDER_ERROR",
            "error_code": type(exc).__name__,
            "error_message": str(type(exc).__name__),
            "status_category": "PROVIDER_ERROR",
            "result": None,
        }


def provider_conflicts() -> Dict[str, Any]:
    return {"conflicts": read_csv("data_conflicts.csv")}


def unresolved() -> Dict[str, Any]:
    return {"unresolved": read_csv("unresolved_mpns.csv")}


def industry_status() -> Dict[str, Any]:
    """Compact, credential-safe status for the existing frontend surfaces."""
    from src.industry_data.catalog_adapter import _vendor_freshness

    paths = ImportPaths.defaults()
    incoming_files = 0
    if paths.incoming.is_dir():
        incoming_files = sum(1 for path in paths.incoming.rglob("*") if path.is_file())
    manifests = sorted(paths.manifests.glob("*.json"), key=lambda path: path.stat().st_mtime) if paths.manifests.is_dir() else []
    vendor_rows = read_csv("vendor_supply_records.csv")
    lifecycle_rows = read_csv("lifecycle_records.csv")
    freshness_counts = {state: 0 for state in ("CURRENT", "STALE", "UNKNOWN", "UNTRUSTED_SOURCE")}
    for row in vendor_rows:
        state = _vendor_freshness(row)
        freshness_counts[state] = freshness_counts.get(state, 0) + 1
    observations = [row.get("retrieved_at") or "" for row in read_csv("source_registry.csv")]
    return {
        "incoming_files": incoming_files,
        "documents_registered": len(read_csv("documents.csv")),
        "bom_lines": len(read_csv("bom_lines.csv")),
        "unresolved_mpns": len(read_csv("unresolved_mpns.csv")),
        "vendor_supply_records": len(vendor_rows),
        "vendor_record_freshness": freshness_counts,
        "lifecycle_records": len(lifecycle_rows),
        "vendor_status": "INSUFFICIENT_DATA" if not vendor_rows else "REAL_DATA",
        "lifecycle_status": "INSUFFICIENT_DATA" if not lifecycle_rows else "REAL_DATA",
        "providers": providers_health(),
        "latest_manifest": manifests[-1].name if manifests else "",
        "latest_source_observed_at": max((value for value in observations if value), default=""),
        "data_source": "REAL_PUBLIC_SOURCE",
    }


def import_industry_data(body: Dict[str, Any]) -> Dict[str, Any]:
    report = run_import(dry_run=bool(body.get("dry_run")), enrich=bool(body.get("enrich")))
    return {
        "import_id": report["import_id"],
        "dry_run": report["dry_run"],
        "files_detected": len(report["input_files"]),
        "products_detected": report["products_detected"],
        "bom_files": len(report["boms_detected"]),
        "bom_rows": report["bom_rows"],
        "documents_registered": len(report["files_classified"]),
        "duplicates": len(report["duplicates"]),
        "warnings": report["warnings"],
        "errors": report["errors"],
        "manifest": report.get("manifest", ""),
    }


def _safe_upload_name(value: Any) -> str:
    name = str(value or "").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name


def _import_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "import_id": report["import_id"],
        "dry_run": report["dry_run"],
        "files_detected": len(report["input_files"]),
        "products_detected": report["products_detected"],
        "bom_files": len(report["boms_detected"]),
        "bom_rows": report["bom_rows"],
        "documents_registered": len(report["files_classified"]),
        "duplicates": len(report["duplicates"]),
        "warnings": report["warnings"],
        "errors": report["errors"],
        "manifest": report.get("manifest", ""),
    }


def upload_industry_file(body: Dict[str, Any]) -> Dict[str, Any]:
    """Accept one browser-uploaded industry source into the controlled inbox.

    The browser provides only a filename plus base64 bytes.  Paths, archive
    extraction, format parsing, hashing, duplicate handling, and provenance
    all remain inside the established importer.
    """
    filename = _safe_upload_name(body.get("filename"))
    suffix = filename[filename.rfind(".") :].lower() if "." in filename else ""
    if not filename or suffix not in UPLOAD_SUFFIXES:
        return {"error": "UNSUPPORTED_FILE", "message": "Supported files: ZIP, CSV, XLS, XLSX, PDF, TXT, JSON."}
    encoded = body.get("content_base64")
    if not isinstance(encoded, str) or not encoded:
        return {"error": "VALIDATION_ERROR", "message": "content_base64 is required."}
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return {"error": "VALIDATION_ERROR", "message": "content_base64 is invalid."}
    if not content or len(content) > MAX_UPLOAD_BYTES:
        return {"error": "FILE_TOO_LARGE", "message": "Uploaded file must be between 1 byte and 50 MiB."}
    paths = ImportPaths.defaults()
    paths.incoming.mkdir(parents=True, exist_ok=True)
    target = paths.incoming / filename
    digest = hashlib.sha256(content).hexdigest()
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        target = paths.incoming / f"{target.stem}-{digest[:12]}{suffix}"
    if not target.exists():
        target.write_bytes(content)
    report = run_import(enrich=False)
    return {"uploaded_file": target.name, "file_hash": digest, **_import_summary(report)}


def industry_components(query: Dict[str, list[str]]) -> Dict[str, Any]:
    from src.industry_data.catalog_adapter import lifecycle_label_for_mpn, lifecycle_quality_for_mpn

    product_id = (query.get("product_id") or [""])[0]
    lines = read_csv("bom_lines.csv")
    if product_id:
        lines = [line for line in lines if line.get("product_id") == product_id]
    wanted = {line.get("component_model_id") for line in lines if line.get("component_model_id")}
    models = [model for model in read_csv("component_models.csv") if model.get("component_model_id") in wanted]
    models.sort(key=lambda model: (model.get("mpn") or "").casefold())
    return {
        "components": [
            {
                "mpn": model.get("mpn", ""),
                "manufacturer": model.get("manufacturer", ""),
                "description": model.get("description", ""),
                "package": model.get("package", ""),
                "lifecycle_status": lifecycle_label_for_mpn(model.get("mpn", "")) or "UNKNOWN",
                "lifecycle_evidence_status": lifecycle_quality_for_mpn(model.get("mpn", "")),
            }
            for model in models[:2000]
            if model.get("mpn")
        ],
        "product_id": product_id,
        "total": len(models),
        "data_source": "REAL_PUBLIC_SOURCE",
    }


def industry_boms() -> Dict[str, Any]:
    from src.industry_data.catalog_adapter import _vendor_freshness
    from src.industry_data.revision_selection import select_product_bom

    documents = read_csv("documents.csv")
    vendor_models = {
        row.get("component_model_id") for row in read_csv("vendor_supply_records.csv")
        if row.get("component_model_id") and _vendor_freshness(row) == "CURRENT"
    }
    boms = []
    for product in read_csv("products.csv"):
        product_id = product.get("product_id", "")
        if product_id not in INDUSTRY_PROJECT_KEYS:
            continue
        product_lines, revision_quality = select_product_bom(product_id, reader=read_csv)
        models = {row.get("component_model_id") for row in product_lines if row.get("component_model_id")}
        active_source_ids = {row.get("source_id") for row in product_lines if row.get("source_id")}
        source_documents = [
            row for row in documents if row.get("product_id") == product_id
            and (not active_source_ids or row.get("source_id") in active_source_ids)
        ]
        boms.append(
            {
                "product_id": product_id,
                "project_key": INDUSTRY_PROJECT_KEYS[product_id],
                "name": product.get("product_name", product_id),
                "manufacturer": product.get("manufacturer", ""),
                "bom_lines": len(product_lines),
                "unique_mpns": len(models),
                "source_documents": len(source_documents),
                "source_document": (source_documents[0].get("filename") or source_documents[0].get("title") or "") if source_documents else "",
                "enriched_components": len(models & vendor_models),
                "revision_quality": revision_quality,
                "data_source": "REAL_PUBLIC_SOURCE",
            }
        )
    boms.sort(key=lambda item: item["name"].casefold())
    return {"boms": boms, "data_source": "REAL_PUBLIC_SOURCE"}


def load_industry_bom(body: Dict[str, Any]) -> Dict[str, Any]:
    product_id = str(body.get("product_id") or "")
    for bom in industry_boms()["boms"]:
        if bom["product_id"] == product_id:
            if bom["revision_quality"].get("status") == "AMBIGUOUS_REVISION":
                return {"error": "AMBIGUOUS_REVISION", "message": "Cannot load a BOM until one revision can be selected unambiguously."}
            if bom["bom_lines"] == 0:
                return {"error": "NO_IMPORTED_BOM", "message": "No reportable BOM lines exist in the selected revision."}
            return {
                "status": "READY",
                "source": "Industry Dataset",
                "enrichment_status": (
                    "INSUFFICIENT_DATA"
                    if bom["enriched_components"] == 0
                    else f"{bom['enriched_components']} / {bom['unique_mpns']}"
                ),
                "last_updated": bom["revision_quality"].get("source_observed_at", ""),
                **bom,
            }
    return {"error": "BOM_NOT_FOUND", "message": "Requested industry BOM is not available in normalized data."}


def handle_get(path: str, query: Dict[str, list[str]]) -> Optional[Dict[str, Any]]:
    if path in {"/api/providers/health", "/api/providers/health/"}:
        return providers_health()
    if path in {"/api/providers/test", "/api/providers/test/", "/api/industry/providers/test", "/api/industry/providers/test/"}:
        p = (query.get("provider") or ["digikey"])[0]
        mpn = (query.get("mpn") or ["TPS5402DGQ"])[0]
        return test_provider(p, mpn)
    if path in {"/api/providers/conflicts", "/api/providers/conflicts/"}:
        return provider_conflicts()
    if path in {"/api/enrichment/status", "/api/enrichment/status/"}:
        return latest_status()
    if path in {"/api/industry/status", "/api/industry/status/"}:
        return industry_status()
    if path in {"/api/industry/providers", "/api/industry/providers/"}:
        return providers_health()
    if path in {"/api/industry/components", "/api/industry/components/"}:
        return industry_components(query)
    if path in {"/api/industry/boms", "/api/industry/boms/"}:
        return industry_boms()
    if path.startswith("/api/industry/component/"):
        return component_enrichment_payload(path.rsplit("/", 1)[-1])
    if path in {"/api/enrichment/unresolved", "/api/enrichment/unresolved/"}:
        return unresolved()
    if path in {"/api/enrichment/quality", "/api/enrichment/quality/"}:
        return {"issues": run_quality()}
    if path.startswith("/api/enrichment/component/"):
        mpn = path.rsplit("/", 1)[-1]
        return component_enrichment_payload(mpn)
    if path in {"/api/vendors", "/api/vendors/"}:
        mpn = (query.get("mpn") or [""])[0]
        region = (query.get("region") or [""])[0]
        payload = component_enrichment_payload(mpn)
        if region:
            payload["vendor_records"] = [
                row for row in payload["vendor_records"] if (row.get("region") or "").upper() == region.upper()
            ]
        return payload
    if path in {"/api/vendor-feasibility", "/api/vendor-feasibility/"}:
        mpn = (query.get("mpn") or [""])[0]
        region = (query.get("region") or ["IN"])[0]
        candidate = ComponentSpec(component_id=mpn, part_number=mpn, category="generic")
        return evaluate_vendor_feasibility(candidate, target_region=region)
    return None


def handle_post(path: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if path in {"/api/providers/test", "/api/providers/test/", "/api/industry/providers/test", "/api/industry/providers/test/"}:
        p = str(body.get("provider") or "digikey")
        mpn = str(body.get("mpn") or "TPS5402DGQ")
        return test_provider(p, mpn)
    if path in {"/api/industry/import", "/api/industry/import/"}:
        return import_industry_data(body)
    if path in {"/api/industry/upload", "/api/industry/upload/"}:
        return upload_industry_file(body)
    if path in {"/api/industry/bom/load", "/api/industry/bom/load/"}:
        return load_industry_bom(body)
    if path in {"/api/enrichment/run", "/api/enrichment/run/"}:
        return run_enrichment(
            mpns=[str(mpn).strip() for mpn in (body.get("mpns") or []) if str(mpn).strip()][:10] or None,
            product_ids=body.get("product_ids") or None,
            providers=body.get("providers") or ["digikey", "nexar", "mouser"],
            region=body.get("region"),
            force_refresh=bool(body.get("force_refresh")),
        )
    return None


def parse_query(raw: str) -> Dict[str, list[str]]:
    return parse_qs(raw)
