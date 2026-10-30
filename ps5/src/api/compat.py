"""Compatibility routes that keep the existing frontend on the unified API."""

from __future__ import annotations

from typing import Any, Dict
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request

from src.candidate_orchestrator import evaluate_candidate_decision
from src.component_intelligence import get_component_analysis
from src.industry_data.http_routes import handle_get as handle_industry_get
from src.industry_data.http_routes import handle_post as handle_industry_post
from src.risk_report_bridge import substitutes_for_risk_report
from src.substitute_api import get_component, search_substitutes
from src.substitute_engine import compare_components, recommend_industry_substitutes, recommend_substitutes

router = APIRouter()


@router.get("/components/{component_id}")
async def component_get(component_id: str) -> Dict[str, Any]:
    return get_component(component_id)


@router.get("/components/{component_id}/substitutes")
async def component_substitutes(component_id: str, include_incompatible: bool = True) -> Dict[str, Any]:
    return recommend_substitutes(component_id, include_incompatible=include_incompatible)


@router.get("/industry/{product_id}/{reference}/substitutes")
async def industry_substitutes(product_id: str, reference: str) -> Dict[str, Any]:
    return recommend_industry_substitutes(product_id, reference, "data")


@router.get("/decision/{product_id}/{component_id}")
async def component_decision(product_id: str, component_id: str) -> Dict[str, Any]:
    result = evaluate_candidate_decision(product_id, component_id)
    if result.get("reason_codes") == ["TARGET_COMPONENT_SPEC_UNAVAILABLE"]:
        raise HTTPException(status_code=404, detail=f"No decision target found for {product_id}/{component_id}.")
    return result


@router.get("/evidence/components/{component_id}/analysis")
async def component_analysis(component_id: str) -> Dict[str, Any]:
    return get_component_analysis(component_id)


@router.get("/substitutes/{original_id}/{candidate_id}")
@router.get("/substitutes/{original_id}/{candidate_id}/comparison")
async def substitute_comparison(original_id: str, candidate_id: str) -> Dict[str, Any]:
    return compare_components(original_id, candidate_id)


@router.get("/risk-report/substitutes")
async def risk_report_substitutes(path: str = "outputs/risk_analysis.json", include_incompatible: bool = True) -> Dict[str, Any]:
    return substitutes_for_risk_report(path, include_incompatible=include_incompatible)


@router.post("/substitutes/search")
async def substitute_search(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = search_substitutes(payload)
    if result.get("error") == "VALIDATION_ERROR":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@router.api_route("/api/{path:path}", methods=["GET", "POST"], include_in_schema=False)
async def industry_api_compatibility(request: Request, path: str) -> Dict[str, Any]:
    """Bridge industry/provider HTTP handlers into this ASGI application."""
    api_path = f"/api/{path}"
    query = parse_qs(request.url.query)

    if request.method == "GET":
        result = handle_industry_get(api_path, query)
    else:
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Body must be valid JSON.") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Body must be a JSON object.")
        result = handle_industry_post(api_path, payload)

    if result is None:
        raise HTTPException(status_code=404, detail="Route not found.")
    return result
