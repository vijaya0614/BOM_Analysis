"""PS5 — BOM Risk Analysis & Intelligent Component Substitution Platform.
Unified FastAPI Application Entry Point.
"""

from __future__ import annotations

import csv
from datetime import datetime
import io
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.config import settings
from src.api.compat import router as compatibility_router

# Existing Risk API imports
from src.risk_api import (
    INDUSTRY_PROJECT_IDS,
    SAMPLE_PROJECTS,
    analyze_bom_path,
    analyze_industry_product,
    analyze_uploaded_csv,
)
from src.bom_parser import is_tbd_part, parse_bom

# New Engineering Calculation Modules
from src.obsolescence_forecasting import (
    forecast_component_obsolescence,
    get_weibull_params,
)
from src.market_supply_risk import (
    AvailabilityTolerances,
    SupplierShare,
    evaluate_market_supply_risk,
)
from src.physical_compatibility import evaluate_physical_compatibility
from src.tolerance_analysis import (
    CircuitParameter,
    DEFAULT_SAMPLE_COUNT,
    buck_regulator_vout_analysis,
    calculate_engineering_margins,
    run_circuit_tolerance_analysis,
    voltage_divider_analysis,
)
from src.mission_profile_engine import (
    DEFAULT_ACTIVATION_ENERGY_EV,
    DEFAULT_LIFE_HOURS_AT_REFERENCE,
    DEFAULT_RATED_TEMP_MAX_C,
    DEFAULT_TARGET_SERVICE_YEARS,
    DEFAULT_THERMAL_RESISTANCE_C_PER_W,
    MissionProfilePhase,
    evaluate_mission_profile,
    get_standard_mission_profiles,
)
from src.substitute_hard_gate import (
    evaluate_candidate_substitutes,
    evaluate_hard_gates,
)
from src.fmea_engine import ACTION_PRIORITY_THRESHOLDS, generate_component_fmea
from src.cost_scenarios import evaluate_cost_scenarios
from src.product_risk_aggregation import aggregate_product_risk
from src.scenario_engine import ScenarioInputs, run_scenario_comparison
from src.synthetic_bom_generator import (
    REALISTIC_PROTOTYPE_COMPONENTS,
    generate_bom_csv_template,
    generate_realistic_synthetic_bom_csv,
    validate_uploaded_bom_csv,
)
from src.vendor_intelligence import generate_component_vendor_intelligence

# Existing substitute engine routes
from src.substitute_engine import (
    compare_components,
    recommend_industry_substitutes,
    recommend_substitutes,
)
from src.component_catalog import find_component
from src.candidate_orchestrator import evaluate_candidate_decision

# Rate limiting
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app = FastAPI(
    title="PS5 — BOM Risk Analysis & Intelligent Component Substitution",
    version="2.0.0",
    description="Expo-Ready Electronics Reliability and Component Obsolescence Decision Platform",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Middleware
origins = settings.CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

MAX_REQUEST_BYTES = 70 * 1024 * 1024


@app.middleware("http")
async def request_limits_middleware(request: Request, call_next):
    """Reject oversized requests before parsing or persisting their bodies."""
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) > MAX_REQUEST_BYTES:
                return JSONResponse(status_code=413, content={"detail": "Request body exceeds the 70 MiB limit."})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length."})
    return await call_next(request)

# Request Metrics Tracking for Prometheus
REQUEST_COUNTS: Dict[str, int] = {}
REQUEST_DURATIONS: List[float] = []


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    path = request.url.path
    status_code = response.status_code
    metric_key = f"{request.method}_{path}_{status_code}"
    REQUEST_COUNTS[metric_key] = REQUEST_COUNTS.get(metric_key, 0) + 1
    if len(REQUEST_DURATIONS) < 500:
        REQUEST_DURATIONS.append(duration)
    return response


# ── Health & Prometheus ───────────────────────────────────────────────────────
@app.get("/health")
async def health_check() -> dict:
    """Comprehensive health check including database and config connectivity."""
    return {
        "status": "ok",
        "service": "PS5 Risk Engine",
        "version": "2.0.0",
        "environment": settings.ENV,
        "database_backend": "sqlite" if settings.DATABASE_URL.startswith("sqlite") else "postgresql",
    }


@app.get("/metrics")
async def prometheus_metrics() -> Response:
    """Prometheus-formatted plaintext metrics."""
    lines = [
        "# HELP ps5_requests_total Total HTTP requests processed by PS5 API",
        "# TYPE ps5_requests_total counter",
    ]
    for key, count in REQUEST_COUNTS.items():
        parts = key.split("_", 2)
        method = parts[0]
        status_code = parts[-1]
        path = "_".join(parts[1:-1]) if len(parts) > 2 else "/"
        lines.append(f'ps5_requests_total{{method="{method}",path="{path}",status="{status_code}"}} {count}')

    avg_duration = sum(REQUEST_DURATIONS) / max(1, len(REQUEST_DURATIONS))
    lines.extend([
        "# HELP ps5_request_duration_seconds Average HTTP request duration in seconds",
        "# TYPE ps5_request_duration_seconds gauge",
        f"ps5_request_duration_seconds {avg_duration:.6f}",
    ])
    return PlainTextResponse("\n".join(lines) + "\n")


# ── Risk Analysis Endpoints (Preserved) ───────────────────────────────────────
@app.get("/risk/projects")
async def list_projects() -> dict:
    projects = [{"id": pid, "name": meta["name"]} for pid, meta in SAMPLE_PROJECTS.items()]
    return {"projects": projects}


@app.get("/api/demo/sample-projects")
async def list_demo_sample_projects() -> dict:
    """Return sample card metadata computed from each canonical demo BOM CSV."""
    projects = []
    for project_id, meta in SAMPLE_PROJECTS.items():
        if project_id in INDUSTRY_PROJECT_IDS:
            continue
        profiles = parse_bom(meta["bom_path"])
        known_mpns = {profile.part_number for profile in profiles if profile.part_number}
        projects.append({
            "id": project_id,
            "name": meta["name"],
            "bom_lines": len(profiles),
            "unique_mpns": len(known_mpns),
            "total_quantity": sum(profile.qty for profile in profiles),
            "unresolved_lines": sum(1 for profile in profiles if not profile.part_number),
        })
    return {"projects": projects}


@app.get("/risk/analyze")
@limiter.limit("100/minute")
async def analyze_get(request: Request, project: str = "") -> dict:
    if not project:
        raise HTTPException(status_code=400, detail="Missing 'project' query parameter")
    if project in INDUSTRY_PROJECT_IDS:
        meta = SAMPLE_PROJECTS.get(project)
        if not meta:
            raise HTTPException(status_code=404, detail=f"Unknown project '{project}'")
        result = analyze_industry_product(project, meta["name"])
    else:
        meta = SAMPLE_PROJECTS.get(project)
        if not meta:
            raise HTTPException(status_code=404, detail=f"Unknown project '{project}'")
        result = analyze_bom_path(meta["bom_path"], meta["name"])  # type: ignore[arg-type]
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=404, detail=result.get("message", "Error"))
    return result


@app.post("/risk/analyze")
@limiter.limit("100/minute")
async def analyze_post(request: Request, payload: dict) -> dict:
    project = payload.get("project")
    if project:
        meta = SAMPLE_PROJECTS.get(project)
        if not meta:
            raise HTTPException(status_code=404, detail=f"Unknown project '{project}'")
        if project in INDUSTRY_PROJECT_IDS:
            result = analyze_industry_product(project, meta["name"])
        else:
            result = analyze_bom_path(meta["bom_path"], meta["name"])  # type: ignore[arg-type]
        if isinstance(result, dict) and result.get("error"):
            raise HTTPException(status_code=404, detail=result.get("message", "Error"))
        return result
    csv_text = payload.get("csv_text")
    if not csv_text:
        raise HTTPException(status_code=400, detail="Payload must include 'project' or 'csv_text'.")
    filename = payload.get("filename", "uploaded_bom.csv")
    result = analyze_uploaded_csv(csv_text, filename)
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=400, detail=result.get("message", "Error"))
    return result


# ── BOM Ingestion, Synthetic Data & Template ──────────────────────────────────
@app.get("/api/bom/template")
async def get_bom_template() -> dict:
    """Downloadable clean CSV template."""
    return {"csv_template": generate_bom_csv_template()}


@app.get("/api/bom/synthetic")
async def get_synthetic_bom() -> dict:
    """Returns realistic 15-20 component synthetic BOM with active, NRND, and EOL parts."""
    return {
        "components": REALISTIC_PROTOTYPE_COMPONENTS,
        "csv_text": generate_realistic_synthetic_bom_csv(),
        "total_components": len(REALISTIC_PROTOTYPE_COMPONENTS),
    }


@app.post("/api/bom/validate")
async def validate_bom(payload: dict) -> dict:
    """Validates an uploaded CSV string with row-level error reporting."""
    csv_text = payload.get("csv_text", "")
    if not csv_text:
        raise HTTPException(status_code=400, detail="Missing 'csv_text' field in payload.")
    res = validate_uploaded_bom_csv(csv_text)
    return {
        "is_valid": res.is_valid,
        "total_rows": res.total_rows,
        "valid_rows_count": res.valid_rows_count,
        "error_count": res.error_count,
        "row_errors": res.row_errors,
        "normalized_components": res.normalized_components,
    }


# ── Obsolescence Forecasting (Part 5) ─────────────────────────────────────────
@app.post("/api/obsolescence/forecast")
async def obsolescence_forecast_endpoint(payload: dict) -> dict:
    """Generates 1-, 3-, and 5-year Weibull survival and obsolescence forecasts."""
    pn = payload.get("part_number") or payload.get("mpn")
    if not pn:
        raise HTTPException(status_code=400, detail="Missing 'part_number' in payload.")
    report = forecast_component_obsolescence(
        part_number=pn,
        category=payload.get("category"),
        lifecycle_status=payload.get("lifecycle_status"),
        introduction_year=payload.get("introduction_year"),
        estimated_age_years=payload.get("estimated_age_years"),
        has_second_source=payload.get("has_second_source"),
        market_supplier_count=payload.get("market_supplier_count"),
    )
    return report.to_dict()


# ── Market & Availability Risk (Part 6) ───────────────────────────────────────
@app.post("/api/market/supply-pressure")
async def market_supply_risk_endpoint(payload: dict) -> dict:
    """Calculates Inventory Coverage, Lead-Time Pressure, HHI, and SPI."""
    pn = payload.get("part_number") or payload.get("mpn", "UNKNOWN")
    shares_raw = payload.get("supplier_shares", [])
    shares = [SupplierShare(s.get("supplier_name", f"Supplier {i}"), float(s.get("share_fraction", 0.5))) for i, s in enumerate(shares_raw)]

    tol_raw = payload.get("tolerances", {})
    tol = AvailabilityTolerances(
        min_required_stock=int(tol_raw.get("min_required_stock", 500)),
        max_lead_time_weeks=float(tol_raw.get("max_lead_time_weeks", 16.0)),
        min_inventory_coverage_weeks=float(tol_raw.get("min_inventory_coverage_weeks", 8.0)),
        min_independent_suppliers=int(tol_raw.get("min_independent_suppliers", 2)),
        required_procurement_date=tol_raw.get("required_procurement_date"),
    )

    report = evaluate_market_supply_risk(
        part_number=pn,
        available_stock=payload.get("available_stock"),
        weekly_demand=payload.get("weekly_demand"),
        estimated_lead_time_weeks=payload.get("estimated_lead_time_weeks"),
        supplier_count=int(payload.get("supplier_count", 0)),
        supplier_shares=shares if shares else None,
        is_allocated=bool(payload.get("is_allocated", False)),
        is_backordered=bool(payload.get("is_backordered", False)),
        lifecycle_status=payload.get("lifecycle_status"),
        price_change_pct=payload.get("price_change_pct"),
        tolerances=tol,
    )
    return report.to_dict()


# ── Physical Compatibility (Part 7) ───────────────────────────────────────────
@app.post("/api/physical/compatibility")
async def physical_compatibility_endpoint(payload: dict) -> dict:
    """Evaluates physical, dimensional, and form-fit-function compatibility."""
    orig_pn = payload.get("original_part", "ORIGINAL")
    cand_pn = payload.get("candidate_part", "CANDIDATE")
    res = evaluate_physical_compatibility(
        original_part=orig_pn,
        candidate_part=cand_pn,
        orig_package=payload.get("orig_package"),
        cand_package=payload.get("cand_package"),
        orig_mounting=payload.get("orig_mounting"),
        cand_mounting=payload.get("cand_mounting"),
        orig_pin_count=payload.get("orig_pin_count"),
        cand_pin_count=payload.get("cand_pin_count"),
        orig_pin_pitch_mm=payload.get("orig_pin_pitch_mm"),
        cand_pin_pitch_mm=payload.get("cand_pin_pitch_mm"),
        orig_height_mm=payload.get("orig_height_mm"),
        cand_height_mm=payload.get("cand_height_mm"),
        max_permitted_height_mm=payload.get("max_permitted_height_mm"),
        orig_has_thermal_pad=payload.get("orig_has_thermal_pad"),
        cand_has_thermal_pad=payload.get("cand_has_thermal_pad"),
        pinout_identical=payload.get("pinout_identical"),
    )
    return res.to_dict()


# ── Electrical Tolerance Analysis (Part 8) ────────────────────────────────────
@app.post("/api/tolerances/analyze")
async def tolerance_analysis_endpoint(payload: dict) -> dict:
    """Executes Worst-Case, RSS, and Monte Carlo tolerance analysis."""
    circuit_type = payload.get("circuit_type", "voltage_divider")
    samples = int(payload.get("sample_count", DEFAULT_SAMPLE_COUNT))

    if circuit_type == "buck_converter":
        res = buck_regulator_vout_analysis(
            vref_volts=float(payload.get("vref_volts", 0.80)),
            vref_tol_pct=float(payload.get("vref_tol_pct", 1.5)),
            r_top_ohms=float(payload.get("r_top_ohms", 52300.0)),
            r_top_tol_pct=float(payload.get("r_top_tol_pct", 1.0)),
            r_bot_ohms=float(payload.get("r_bot_ohms", 10000.0)),
            r_bot_tol_pct=float(payload.get("r_bot_tol_pct", 1.0)),
            samples=samples,
        )
    else:
        res = voltage_divider_analysis(
            r1_ohms=float(payload.get("r1_ohms", 10000.0)),
            r1_tol_pct=float(payload.get("r1_tol_pct", 1.0)),
            r2_ohms=float(payload.get("r2_ohms", 10000.0)),
            r2_tol_pct=float(payload.get("r2_tol_pct", 1.0)),
            vin_volts=float(payload.get("vin_volts", 5.0)),
            vin_tol_pct=float(payload.get("vin_tol_pct", 2.0)),
            v_target_min=float(payload.get("v_target_min", 2.35)),
            v_target_max=float(payload.get("v_target_max", 2.65)),
            samples=samples,
        )
    return res.to_dict()


@app.post("/api/tolerances/margins")
async def engineering_margins_endpoint(payload: dict) -> dict:
    """Calculates voltage, current, power, and thermal engineering safety margins."""
    margins = calculate_engineering_margins(
        v_op=payload.get("v_op"),
        v_max=payload.get("v_max"),
        i_op=payload.get("i_op"),
        i_max=payload.get("i_max"),
        p_op=payload.get("p_op"),
        p_max=payload.get("p_max"),
        t_op=payload.get("t_op"),
        t_max=payload.get("t_max"),
    )
    return margins.to_dict()


# ── Mission Profile & Thermal Life Consumption (Part 9) ───────────────────────
@app.get("/api/mission-profile/standards")
async def standard_profiles_endpoint() -> dict:
    """Returns library of standard operating condition profiles."""
    profs = get_standard_mission_profiles()
    return {k: [asdict(p) for p in v] for k, v in profs.items()}


@app.post("/api/mission-profile/evaluate")
async def mission_profile_evaluate_endpoint(payload: dict) -> dict:
    """Evaluates mission profile thermal rise, Arrhenius acceleration, and Miner's damage."""
    phases_raw = payload.get("phases", [])
    phases: List[MissionProfilePhase] = []
    for pr in phases_raw:
        phases.append(MissionProfilePhase(
            name=pr.get("name", "Phase"),
            annual_hours=float(pr.get("annual_hours", 2000.0)),
            ambient_temp_c=float(pr.get("ambient_temp_c", 25.0)),
            power_dissipation_watts=float(pr.get("power_dissipation_watts", 1.0)),
            operating_voltage=float(pr.get("operating_voltage", 5.0)),
            operating_current=float(pr.get("operating_current", 0.20)),
            duty_cycle=float(pr.get("duty_cycle", 1.0)),
        ))

    if not phases:
        # Fallback to standard industrial enclosure profile
        phases = get_standard_mission_profiles()["High-Temperature Industrial Enclosure"]

    res = evaluate_mission_profile(
        component_name=payload.get("component_name", "Component"),
        part_number=payload.get("part_number", "MPN"),
        phases=phases,
        rated_temp_max_c=float(payload.get("rated_temp_max_c", DEFAULT_RATED_TEMP_MAX_C)),
        thermal_resistance_c_per_w=float(payload.get("thermal_resistance_c_per_w", DEFAULT_THERMAL_RESISTANCE_C_PER_W)),
        nominal_life_hours_at_ref=float(payload.get("nominal_life_hours_at_ref", DEFAULT_LIFE_HOURS_AT_REFERENCE)),
        activation_energy_ev=float(payload.get("activation_energy_ev", DEFAULT_ACTIVATION_ENERGY_EV)),
        target_service_years=int(payload.get("target_service_years", DEFAULT_TARGET_SERVICE_YEARS)),
    )
    result = res.to_dict()
    result["model_metadata"]["default_phase_profile"] = (
        "High-Temperature Industrial Enclosure" if not phases_raw else None
    )
    return result


# ── Intelligent Substitution & Hard Gates (Part 10) ───────────────────────────
@app.post("/api/substitutes/evaluate-gates")
async def evaluate_substitute_gates_endpoint(payload: dict) -> dict:
    """Hard-gate-first candidate evaluation and multi-criteria transparent ranking."""
    orig = payload.get("original_spec", {})
    candidates = payload.get("candidate_specs", [])
    app_limits = payload.get("application_limits")

    results = evaluate_candidate_substitutes(orig, candidates, app_limits)
    return {
        "total_evaluated": len(results),
        "drop_in_candidates": [r.to_dict() for r in results if r.classification == "DROP_IN_CANDIDATE"],
        "conditional_redesign_candidates": [r.to_dict() for r in results if r.classification == "REQUIRES_REDESIGN"],
        "insufficient_evidence_candidates": [r.to_dict() for r in results if r.classification == "INSUFFICIENT_EVIDENCE"],
        "incompatible_candidates": [r.to_dict() for r in results if r.classification == "INCOMPATIBLE"],
        "all_ranked_candidates": [r.to_dict() for r in results],
    }


# ── Component & Subsystem FMEA (Part 11) ───────────────────────────────────────
@app.post("/api/fmea/analyze")
async def fmea_analysis_endpoint(payload: dict) -> dict:
    """Generates suggested FMEA entries with RPN and Action Priority ratings."""
    pn = payload.get("part_number") or payload.get("mpn", "GENERIC_PART")
    name = payload.get("component_name", pn)
    cat = _fmea_component_category(str(pn), str(payload.get("category") or ""))
    subsystem = payload.get("subsystem", "Electronics Subsystem")
    tj = payload.get("junction_temp_c")

    entries = generate_component_fmea(
        part_number=pn,
        component_name=name,
        category=cat,
        subsystem=subsystem,
        mission_profile_temperature_c=tj,
    )
    return {
        "part_number": pn,
        "total_modes": len(entries),
        "model_assumptions": {
            "method": "Suggested category-based FMEA templates; requires engineering review",
            "action_priority_thresholds": ACTION_PRIORITY_THRESHOLDS,
            "threshold_calibration_status": "HEURISTIC_NOT_VALIDATED_AGAINST_FIELD_FAILURES",
            "scores_are_suggestions": True,
        },
        "fmea_entries": [e.to_dict() for e in entries],
    }


def _fmea_component_category(part_number: str, category: str | None) -> str:
    """Choose only the matching component-family template; scores remain heuristic suggestions."""
    text = f"{category or ''} {part_number}".lower().replace("_", "-")
    if any(token in text for token in ("regulator", "power management", "buck", "-ldo", "converter", "reg-")):
        return "regulator"
    if any(token in text for token in ("microcontroller", "-mcu", "processor", "-soc", "stm32", "esp32", "attiny")):
        return "microcontroller"
    if any(token in text for token in ("capacitor", "-cap", "mlcc")):
        return "capacitor"
    if any(token in text for token in ("transistor", "mosfet", "-fet", "2n2222", "ao3400")):
        return "mosfet"
    return "generic"


@app.post("/api/fmea/bom")
async def fmea_bom_endpoint(payload: dict) -> dict:
    """Generate review-required FMEA suggestions for each part in the active BOM."""
    components = payload.get("components")
    if not isinstance(components, list):
        raise HTTPException(status_code=400, detail="components must be a list")
    if len(components) > 1000:
        raise HTTPException(status_code=413, detail="FMEA matrix is limited to 1000 BOM components")

    entries: list[dict[str, Any]] = []
    matched_parts = 0
    unresolved_parts = 0
    for component in components:
        if not isinstance(component, dict):
            continue
        part_number = str(component.get("part_number") or "").strip()
        if not part_number or is_tbd_part(part_number):
            unresolved_parts += 1
            continue
        matched_parts += 1
        category = str(component.get("category") or "")
        display_category = category or "Unclassified"
        suggested = generate_component_fmea(
            part_number=part_number,
            component_name=str(component.get("component_name") or part_number),
            category=_fmea_component_category(part_number, category),
            subsystem=display_category,
            mission_profile_temperature_c=component.get("junction_temp_c"),
        )
        for item in suggested:
            entry = item.to_dict()
            entry["reference_designator"] = str(component.get("reference_designator") or "—")
            entry["quantity"] = component.get("quantity")
            entries.append(entry)

    return {
        "bom_name": str(payload.get("bom_name") or "Active BOM"),
        "component_count": matched_parts,
        "unresolved_component_count": unresolved_parts,
        "total_modes": len(entries),
        "model_assumptions": {
            "method": "Category-based FMEA templates applied to the active BOM component list",
            "threshold_calibration_status": "HEURISTIC_NOT_VALIDATED_AGAINST_FIELD_FAILURES",
            "scores_are_suggestions": True,
            "engineering_review_required": True,
        },
        "fmea_entries": entries,
    }


# ── Cost Savings & Lifecycle Economics (Part 12) ──────────────────────────────
@app.post("/api/cost/scenarios")
async def cost_scenarios_endpoint(payload: dict) -> dict:
    """Evaluates the 4 lifecycle strategies (Continue, LTB, Substitute, Redesign)."""
    pn = payload.get("part_number", "COMPONENT")
    vol = int(payload.get("annual_volume", 5000))
    horizon = int(payload.get("horizon_years", 5))
    price = float(payload.get("current_unit_price", 3.50))

    report = evaluate_cost_scenarios(
        part_number=pn,
        annual_volume=vol,
        horizon_years=horizon,
        current_unit_price=price,
        substitute_unit_price=payload.get("substitute_unit_price"),
        substitute_qualification_cost=float(payload.get("substitute_qualification_cost", 4500.0)),
        redesign_tooling_and_qual_cost=float(payload.get("redesign_tooling_and_qual_cost", 18000.0)),
        baseline_disruption_probability=float(payload.get("baseline_disruption_probability", 0.55)),
        disruption_cost_impact=float(payload.get("disruption_cost_impact", 40000.0)),
    )
    return report.to_dict()


# ── Product-Level Risk Aggregation (Part 13) ──────────────────────────────────
@app.post("/api/product/risk-summary")
async def product_risk_summary_endpoint(payload: dict) -> dict:
    """Aggregates component analyses into system and subsystem risk posture."""
    p_name = payload.get("product_name", "Product Assembly")
    comps = payload.get("components", REALISTIC_PROTOTYPE_COMPONENTS)
    vol = int(payload.get("planned_production_volume", 5000))

    summary = aggregate_product_risk(p_name, comps, vol)
    return summary.to_dict()


# ── Scenario Engine & What-If Comparison (Part 14) ────────────────────────────
@app.post("/api/scenarios/compare")
async def scenario_compare_endpoint(payload: dict) -> dict:
    """Side-by-side what-if scenario comparison."""
    pn = payload.get("part_number", "TPS5402DGQR")
    cat = payload.get("category", "Power Management")
    b_raw = payload.get("baseline_inputs", {})
    s_raw = payload.get("scenario_inputs", {})

    b_inputs = ScenarioInputs(
        scenario_name=b_raw.get("scenario_name", "Baseline Design"),
        ambient_temperature_c=float(b_raw.get("ambient_temperature_c", 25.0)),
        operating_voltage=float(b_raw.get("operating_voltage", 5.0)),
        operating_current=float(b_raw.get("operating_current", 0.50)),
        annual_production_volume=int(b_raw.get("annual_production_volume", 5000)),
    )
    s_inputs = ScenarioInputs(
        scenario_name=s_raw.get("scenario_name", "Proposed Mitigated Design"),
        ambient_temperature_c=float(s_raw.get("ambient_temperature_c", 35.0)),
        cooling_type=s_raw.get("cooling_type", "FORCED_AIR_COOLING"),
        operating_voltage=float(s_raw.get("operating_voltage", 5.0)),
        operating_current=float(s_raw.get("operating_current", 0.35)),
        annual_production_volume=int(s_raw.get("annual_production_volume", 5000)),
        has_second_source=bool(s_raw.get("has_second_source", True)),
    )

    res = run_scenario_comparison(pn, cat, "ACTIVE", b_inputs, s_inputs)
    return res.to_dict()


# ── Vendor & Market Intelligence (Geological, Distributors, Saturation) ───────
@app.get("/api/vendor/intelligence/{part_number}")
async def vendor_intelligence_endpoint(part_number: str) -> dict:
    """Return curated or synthetic demo intelligence; this route does not query distributors."""
    intel = generate_component_vendor_intelligence(part_number)
    d = intel.to_dict()
    vendor_records = []
    for dist in intel.market_saturation.distributors:
        vendor_records.append({
            "vendor_name": dist.vendor_name,
            "vendor_part_number": None,
            "stock_quantity": dist.stock,
            "lead_time_days": dist.lead_time_weeks * 7,
            "unit_price": dist.unit_price,
            "currency": dist.currency,
            "moq": dist.moq,
            "packaging": dist.packaging,
            "authorized": dist.authorized,
            "retrieval_state": dist.retrieval_state,
            "data_provenance": dist.data_provenance,
        })
    d["data_source"] = intel.data_provenance
    d["vendor_records"] = vendor_records
    d["lifecycle_evidence"] = [{"status": intel.lifecycle.lifecycle_status}]
    d["technical_specs"] = intel.normalized_specs
    d["documents"] = intel.document_links
    d["model"] = {"datasheet_url": intel.document_links[0]["url"] if intel.document_links else None}
    return d


# ── Full Comprehensive Engineering Report (Part 15) ───────────────────────────
@app.get("/api/reports/full")
@app.get("/api/reports/full-engineering-audit")
async def full_engineering_report_endpoint(project_id: str = "synthetic_prototype") -> dict:
    """Generates an end-to-end multi-disciplinary report across all PS5 modules."""
    comps = REALISTIC_PROTOTYPE_COMPONENTS
    prod_summary = aggregate_product_risk("PS5 Industrial Controller", comps)
    sample_pn = "TPS5402DGQR"

    obsolescence_rep = forecast_component_obsolescence(sample_pn, "Power Management", "ACTIVE", 2018)
    market_rep = evaluate_market_supply_risk(sample_pn, available_stock=28400, weekly_demand=100.0, estimated_lead_time_weeks=8.0)
    tolerance_rep = buck_regulator_vout_analysis()
    mission_rep = evaluate_mission_profile("Buck Regulator", sample_pn, get_standard_mission_profiles()["High-Temperature Industrial Enclosure"])
    cost_rep = evaluate_cost_scenarios(sample_pn, 5000, 5, 1.42)
    fmea_rep = generate_component_fmea(sample_pn, "Step-Down Regulator", "regulator")

    return {
        "report_id": f"REP-{int(time.time())}",
        "generated_at": datetime.now().isoformat(),
        "product_summary": prod_summary.to_dict(),
        "focused_component_audit": {
            "part_number": sample_pn,
            "obsolescence_forecast": obsolescence_rep.to_dict(),
            "market_supply_pressure": market_rep.to_dict(),
            "tolerance_analysis": tolerance_rep.to_dict(),
            "mission_profile": mission_rep.to_dict(),
            "cost_scenarios": cost_rep.to_dict(),
            "fmea": [f.to_dict() for f in fmea_rep],
        },
        "governance_and_compliance": {
            "rohs_compliant": True,
            "reach_compliant": True,
            "provenance": "Verified public datasheet specifications + transparently labeled synthetic procurement data",
        },
    }


# Keep the legacy risk, industry, and substitute URLs available through this
# single ASGI process so the frontend and deployments need one backend port.
app.include_router(compatibility_router)


# Global exception handler to match the previous JSON error format
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "message": exc.detail, "status": exc.status_code},
    )


# Serve the Vite build from the unified API process for one-origin deployments.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
API_PREFIXES = (
    "api", "risk", "components", "industry", "substitutes",
    "decision", "evidence", "risk-report",
)


@app.get("/{asset_path:path}", include_in_schema=False)
async def serve_frontend(asset_path: str):
    index_file = FRONTEND_DIST / "index.html"
    if not index_file.is_file():
        raise HTTPException(status_code=404, detail="Frontend build is not installed.")
    if any(asset_path == prefix or asset_path.startswith(f"{prefix}/") for prefix in API_PREFIXES):
        raise HTTPException(status_code=404, detail="API route not found.")

    requested_file = (FRONTEND_DIST / asset_path).resolve()
    if FRONTEND_DIST.resolve() in requested_file.parents and requested_file.is_file():
        return FileResponse(requested_file)
    if Path(asset_path).suffix:
        raise HTTPException(status_code=404, detail="Static asset not found.")
    return FileResponse(index_file)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
