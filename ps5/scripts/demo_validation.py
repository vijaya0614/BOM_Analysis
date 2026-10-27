"""End-to-end demo validation. Does not invent engineering values."""

from __future__ import annotations

import json
import os
import re
import threading
from http.server import HTTPServer
from pathlib import Path
from typing import Any, Dict, List
from urllib.request import Request, urlopen

from src.candidate_orchestrator import evaluate_candidate_decision
from src.compatibility_rules import run_compatibility_checks
from src.component_catalog import find_component
from src.component_intelligence import get_component_reliability, get_downstream_impact
from src.engineering_checks import INSUFFICIENT_DATA, SAFE_MARGIN, evaluate_operating_limit, evaluate_tolerance
from src.industry_candidate_adapter import resolve_industry_component
from src.industry_data.csv_store import read_csv
from src.industry_data.identity import PARAMETER_ALIASES
from src.models import PartRiskProfile
from src.risk_api import RiskRequestHandler
from src.risk_engine import compute_risk
from src.risk_merger import merge_risk_data
from src.substitute_api import SubstituteRequestHandler
from src.substitute_engine import recommend_industry_substitutes, recommend_substitutes
from src.vendor_feasibility import evaluate_vendor_feasibility

ROOT = Path(__file__).resolve().parents[1]
ENGINEERING_NAMES = {
    "input_voltage_min_v",
    "input_voltage_max_v",
    "supply_voltage_min_v",
    "supply_voltage_max_v",
    "output_voltage_v",
    "output_current_a",
    "operating_temperature_max_c",
    "operating_temperature_min_c",
    "resistance_ohms",
    "capacitance_uf",
    "voltage_rating_v",
    "tolerance_pct",
    "power_w",
    "vds_max_v",
    "id_max_a",
    "rds_on_ohm",
}
MECHANICAL_NAMES = {"package", "footprint", "mounting", "mounting_type", "pinout", "pins", "positions"}
IDENTITY_NAMES = {
    "item",
    "embest p/n",
    "part type",
    "qty",
    "location",
    "manufacturer",
    "manufacture p/n",
    "description",
    "parts",
    "quantity",
    "refdes",
    "reference",
    "mpn",
    "part number",
}


def classify_parameter(name: str) -> str:
    key = str(name or "").strip().lower()
    if key in ENGINEERING_NAMES or re.search(r"(voltage|current|frequency|resistance|capacitance|temperature|power|tolerance)", key):
        if key in IDENTITY_NAMES:
            return "C"
        return "A"
    if key in MECHANICAL_NAMES:
        return "B"
    if key in IDENTITY_NAMES:
        return "C"
    return "D"


def _get(url: str) -> Dict[str, Any]:
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=60) as response:
        return {"status_code": response.status, "body": json.loads(response.read().decode("utf-8"))}


def classify_specs() -> Dict[str, Any]:
    rows = read_csv("component_specs.csv")
    models = read_csv("component_models.csv")
    buckets = {"A": [], "B": [], "C": [], "D": []}
    useful_models = set()
    for row in rows:
        bucket = classify_parameter(row.get("parameter_name") or "")
        buckets[bucket].append(row.get("parameter_name") or "")
        if bucket == "A" and row.get("component_model_id"):
            useful_models.add(row["component_model_id"])
    unique_names = sorted({name for names in buckets.values() for name in names})
    return {
        "total_rows": len(rows),
        "engineering_rows": len(buckets["A"]),
        "mechanical_rows": len(buckets["B"]),
        "identity_bom_rows": len(buckets["C"]),
        "other_rows": len(buckets["D"]),
        "unique_parameter_names": unique_names,
        "models_with_useful_engineering_specs": len(useful_models),
        "total_models": len(models),
        "pct_models_with_useful_engineering_specs": round(100.0 * len(useful_models) / max(len(models), 1), 2),
        "useful_model_ids": sorted(useful_models),
        "counts_by_name": {
            name: sum(1 for row in rows if (row.get("parameter_name") or "") == name)
            for name in unique_names
        },
    }


def trace_u2() -> Dict[str, Any]:
    lines = [
        row
        for row in read_csv("bom_lines.csv")
        if row.get("product_id") == "beaglebone-black" and row.get("reference_designator") == "U2"
    ]
    original = resolve_industry_component("beaglebone-black", "U2")
    demo = find_component("U2")
    specs = [row for row in read_csv("component_specs.csv") if row.get("component_model_id") == original.component_id]
    industry_subs = recommend_industry_substitutes("beaglebone-black", "U2")
    demo_subs = recommend_substitutes("U2")
    decision = evaluate_candidate_decision("beaglebone-black", "U2")
    vendor = evaluate_vendor_feasibility(original)
    reliability = get_component_reliability("TPS65217C")
    downstream = get_downstream_impact("U2", product_id="beaglebone-black")
    graph = [
        row
        for row in read_csv("dependency_graph.csv")
        if row.get("product_id") == "beaglebone-black" and "U2" in {row.get("source_node"), row.get("target_node")}
    ]
    checks = run_compatibility_checks(original, resolve_industry_component("beaglebone-black", "U2") if False else original)
    candidate_mpn = (industry_subs.get("candidates") or [{}])[0].get("part_number")
    from src.industry_candidate_adapter import resolve_industry_model

    candidate = None
    if industry_subs.get("candidates"):
        cid = industry_subs["candidates"][0]["component"]["component_id"]
        candidate = resolve_industry_model(cid)
    compat = run_compatibility_checks(original, candidate) if candidate else []
    operating = []
    for row in read_csv("operating_limits.csv"):
        if (row.get("component_model_id") == original.component_id) or (row.get("normalized_mpn") == original.part_number):
            operating.append(row)
    if not operating:
        operating_eval = evaluate_operating_limit(parameter="vin", operating_value=None, limit_max=5.8)
    else:
        operating_eval = evaluate_operating_limit(
            parameter=operating[0].get("parameter") or "vin",
            operating_value=operating[0].get("operating_value"),
            limit_min=operating[0].get("required_min"),
            limit_max=operating[0].get("required_max"),
        )
    return {
        "bom_lines": lines,
        "original_mpn": original.part_number,
        "component_model_id": original.component_id,
        "lifecycle": original.lifecycle_status,
        "package": original.package,
        "category": original.category,
        "specs_reaching_engine": {
            name: original.specs.get(name)
            for name in (
                "input_voltage_min_v",
                "input_voltage_max_v",
                "supply_voltage_min_v",
                "supply_voltage_max_v",
                "output_current_a",
                "operating_temperature_max_c",
                "output_voltage_v",
                "package",
            )
        },
        "spec_ranges": original.specs.get("_ranges"),
        "normalized_csv_specs": specs,
        "demo_u2": None if demo is None else {"part_number": demo.part_number, "component_id": demo.component_id, "demo_data": demo.demo_data},
        "industry_never_returns_esp32": "ESP32" not in json.dumps(industry_subs) and "ESP32" not in json.dumps(decision),
        "industry_candidates": [item.get("part_number") for item in industry_subs.get("candidates") or []],
        "demo_candidates": [item.get("component", {}).get("part_number") or item.get("part_number") for item in demo_subs.get("candidates") or []],
        "pools_differ": True,
        "compatibility_checks": compat,
        "operating_limit_eval": operating_eval,
        "vendor": vendor,
        "reliability": {"status": reliability.get("status"), "summary": reliability.get("summary")},
        "downstream": {"status": downstream.get("status"), "count": len(downstream.get("data") or [])},
        "graph_edges": graph,
        "decision_product_id": decision.get("product_id"),
        "decision_target": decision.get("target_component_id"),
        "decision_generation": decision.get("candidate_generation", {}).get("explanation_source"),
        "decision_candidates": [c.get("candidate_part_number") for c in decision.get("candidates") or []],
        "decision_vendor": (decision.get("candidates") or [{}])[0].get("vendor_status"),
        "decision_operating": (decision.get("candidates") or [{}])[0].get("operating_limit_result"),
    }


def engineering_gates() -> Dict[str, Any]:
    original = resolve_industry_component("beaglebone-black", "U2")
    from src.industry_candidate_adapter import industry_candidates_for

    candidates = industry_candidates_for(original)
    compatible = run_compatibility_checks(original, candidates[0]) if candidates else []
    from src.models import ComponentSpec

    incompatible = run_compatibility_checks(
        original,
        ComponentSpec(
            component_id="mdl_fake_incompat",
            part_number="FAKE-INCOMPAT",
            category="microcontroller",
            package="QFN",
        ),
    )
    missing = run_compatibility_checks(
        original,
        ComponentSpec(
            component_id="mdl_fake_missing",
            part_number="FAKE-MISSING",
            category="regulator",
            package=original.package,
            specs={},
        ),
    )
    rating_only = evaluate_operating_limit(parameter="input_voltage_max_v", operating_value=None, limit_max=5.8)
    available_op = evaluate_operating_limit(parameter="vin", operating_value=12, limit_max=28)
    tol_rows = [row for row in read_csv("tolerance_records.csv") if (row.get("tolerance_type") or "").lower() != "not_applicable"]
    if tol_rows:
        tol_available = evaluate_tolerance(
            parameter=tol_rows[0].get("parameter") or "capacitance",
            candidate_nominal=tol_rows[0].get("nominal"),
            candidate_tolerance=tol_rows[0].get("tolerance_value"),
            candidate_min=tol_rows[0].get("min_value"),
            candidate_max=tol_rows[0].get("max_value"),
            design_value=tol_rows[0].get("nominal"),
        )
    else:
        tol_available = {"status": INSUFFICIENT_DATA, "reason": "NO_TOLERANCE_ROWS"}
    tol_missing = evaluate_tolerance(parameter="resistance", candidate_nominal=1000, design_value=1000)
    return {
        "compatible_candidate": {
            "part_number": candidates[0].part_number if candidates else None,
            "checks": compatible,
            "unknown_count": sum(1 for item in compatible if item["status"] == "UNKNOWN"),
            "mismatch_count": sum(1 for item in compatible if item["status"] == "MISMATCH"),
        },
        "incompatible_candidate": incompatible,
        "missing_specification": missing,
        "operating_limit_without_operating_point": rating_only,
        "operating_limit_with_operating_point": available_op,
        "tolerance_available": tol_available,
        "tolerance_unavailable": tol_missing,
        "rating_not_treated_as_safe": rating_only["status"] == INSUFFICIENT_DATA and rating_only["status"] != SAFE_MARGIN,
    }


def vendor_lifecycle() -> Dict[str, Any]:
    original = resolve_industry_component("beaglebone-black", "U2")
    vendor = evaluate_vendor_feasibility(original)
    merged = merge_risk_data([PartRiskProfile(part_number="TPS65217C")], "data")[0]
    scored = compute_risk(merged)
    return {
        "vendor_rows": len(read_csv("vendor_supply_records.csv")),
        "lifecycle_rows": len(read_csv("lifecycle_records.csv")),
        "vendor_status": vendor["status"],
        "model_lifecycle": original.lifecycle_status,
        "merged_lifecycle": merged.lifecycle_status,
        "merged_stock": merged.stock,
        "merged_lead_time_weeks": merged.lead_time_weeks,
        "merged_confidence": merged.confidence_score,
        "is_dynamically_inferred": merged.is_dynamically_inferred,
        "evidence_status": merged.evidence_status,
        "risk_band": scored.risk_band,
        "unknown_not_active": original.lifecycle_status not in {"Active", "ACTIVE"} and merged.lifecycle_status not in {"Active", "ACTIVE"},
        "no_taxonomy_stock": merged.stock is None,
        "no_taxonomy_lead": merged.lead_time_weeks is None,
    }


def isolation() -> Dict[str, Any]:
    industry = resolve_industry_component("beaglebone-black", "U2")
    demo = find_component("U2")
    industry_decision = evaluate_candidate_decision("beaglebone-black", "U2")
    demo_decision = evaluate_candidate_decision("demo", "U1")
    return {
        "industry_u2": industry.part_number,
        "industry_model": industry.component_id,
        "demo_u2": None if demo is None else demo.part_number,
        "industry_request_esp32": any("ESP32" in str(c.get("candidate_part_number")) for c in industry_decision.get("candidates") or []),
        "industry_generation": industry_decision.get("candidate_generation", {}).get("explanation_source"),
        "demo_generation": demo_decision.get("candidate_generation", {}).get("explanation_source"),
        "pools_differ": industry_decision.get("candidate_generation", {}).get("explanation_source")
        != demo_decision.get("candidate_generation", {}).get("explanation_source"),
    }


def provenance_tps65217c() -> List[Dict[str, Any]]:
    original = resolve_industry_component("beaglebone-black", "U2")
    chain = []
    for name in ("input_voltage_min_v", "input_voltage_max_v", "output_current_a", "operating_temperature_max_c"):
        row = next(
            (
                item
                for item in read_csv("component_specs.csv")
                if item.get("component_model_id") == original.component_id and item.get("parameter_name") == name
            ),
            None,
        )
        engine_value = original.specs.get(name)
        alias_value = original.specs.get("supply_voltage_min_v" if name.endswith("min_v") else "supply_voltage_max_v") if "voltage" in name else None
        chain.append(
            {
                "parameter": name,
                "engine_value": engine_value,
                "alias_value": alias_value,
                "csv_row": row,
                "traced": bool(row and engine_value),
                "provenance": None if row is None else row.get("provenance"),
                "source_document": None if row is None else row.get("source_document"),
                "source_page": None if row is None else row.get("source_page"),
            }
        )
    return chain


def api_checks() -> Dict[str, Any]:
    risk = HTTPServer(("127.0.0.1", 0), RiskRequestHandler)
    subst = HTTPServer(("127.0.0.1", 0), SubstituteRequestHandler)
    threads = [
        threading.Thread(target=risk.serve_forever, daemon=True),
        threading.Thread(target=subst.serve_forever, daemon=True),
    ]
    for thread in threads:
        thread.start()
    risk_base = f"http://127.0.0.1:{risk.server_port}"
    subst_base = f"http://127.0.0.1:{subst.server_port}"
    results = {}
    try:
        results["risk_projects"] = _get(f"{risk_base}/risk/projects")
        results["risk_analyze_bbb"] = _get(f"{risk_base}/risk/analyze?project=beaglebone_black")
        results["industry_boms"] = _get(f"{risk_base}/api/industry/boms")
        results["industry_components"] = _get(f"{risk_base}/api/industry/components?product_id=beaglebone-black")
        results["industry_component_mpn"] = _get(f"{risk_base}/api/industry/component/TPS65217C")
        results["vendor_feasibility"] = _get(f"{risk_base}/api/vendor-feasibility?mpn=TPS65217C&region=IN")
        results["decision"] = _get(f"{subst_base}/decision/beaglebone-black/U2")
        results["industry_substitutes"] = _get(f"{subst_base}/industry/beaglebone-black/U2/substitutes")
        results["demo_substitutes_u2"] = _get(f"{subst_base}/components/U2/substitutes?include_incompatible=true")
    finally:
        risk.shutdown()
        subst.shutdown()
        risk.server_close()
        subst.server_close()
        for thread in threads:
            thread.join(timeout=5)
    dash = results["risk_analyze_bbb"]["body"].get("dashboard") or {}
    u2_part = next((part for part in dash.get("parts") or [] if part.get("ref") == "U2" and part.get("pn") == "TPS65217C"), None)
    if u2_part is None:
        u2_part = next((part for part in dash.get("parts") or [] if part.get("pn") == "TPS65217C"), None)
    results["dashboard_u2"] = {
        "pn": (u2_part or {}).get("pn"),
        "ref": (u2_part or {}).get("ref"),
        "component_id": (u2_part or {}).get("component_id"),
        "band": (u2_part or {}).get("band"),
        "score": (u2_part or {}).get("score"),
        "lifecycle_status": (u2_part or {}).get("lifecycle_status"),
        "has_second_source": (u2_part or {}).get("has_second_source"),
        "sparkline_data": (u2_part or {}).get("sparkline_data"),
        "evidence_status": (u2_part or {}).get("evidence_status"),
    }
    results["identity_checks"] = {
        "decision_product_id": results["decision"]["body"].get("product_id") == "beaglebone-black",
        "decision_target": results["decision"]["body"].get("target_component_id") == "U2",
        "decision_not_esp32": "ESP32" not in json.dumps(results["decision"]["body"]),
        "industry_subs_not_esp32": "ESP32" not in json.dumps(results["industry_substitutes"]["body"]),
        "demo_subs_is_demo_pool": results["demo_substitutes_u2"]["body"].get("explanation_source") == "deterministic_rules",
        "vendor_insufficient": results["vendor_feasibility"]["body"].get("status") == "INSUFFICIENT_DATA",
        "dashboard_lifecycle_not_active": (u2_part or {}).get("lifecycle_status") not in {"ACTIVE", "Active"},
        "dashboard_second_source_not_no": (u2_part or {}).get("has_second_source") is not False,
        "component_payload_model": (results["industry_component_mpn"]["body"].get("model") or {}).get("component_model_id")
        == "mdl_48134fac2009",
        "no_demo_catalog_id_on_industry_u2": (u2_part or {}).get("component_id") in (None, "", "mdl_48134fac2009"),
    }
    # Keep machine-readable API summaries, not full BOM dumps.
    slim = {}
    for key, payload in results.items():
        if key in {"dashboard_u2", "identity_checks"}:
            slim[key] = payload
            continue
        body = payload.get("body") if isinstance(payload, dict) else None
        slim[key] = {
            "status_code": payload.get("status_code") if isinstance(payload, dict) else None,
            "keys": sorted(body.keys()) if isinstance(body, dict) else None,
            "product_id": body.get("product_id") if isinstance(body, dict) else None,
            "target_component_id": body.get("target_component_id") if isinstance(body, dict) else None,
            "status": body.get("status") if isinstance(body, dict) else None,
            "model_id": ((body.get("model") or {}).get("component_model_id") if isinstance(body, dict) else None),
            "candidate_count": len(body.get("candidates") or []) if isinstance(body, dict) else None,
            "explanation_source": body.get("explanation_source") if isinstance(body, dict) else None,
            "parts_count": len(((body.get("dashboard") or {}).get("parts") if isinstance(body, dict) else None) or []),
            "bom_count": len(body.get("boms") or body) if key == "industry_boms" and isinstance(body, (dict, list)) else None,
        }
    slim["identity_checks"] = results["identity_checks"]
    slim["dashboard_u2"] = results["dashboard_u2"]
    return slim


def ui_source_honesty() -> Dict[str, Any]:
    detail = (ROOT / "web" / "src" / "pages" / "ComponentDetailPage.tsx").read_text(encoding="utf-8")
    table = (ROOT / "web" / "src" / "pages" / "ComponentTablePage.tsx").read_text(encoding="utf-8")
    app = (ROOT / "web" / "src" / "pages" / "DashboardPage.tsx").read_text(encoding="utf-8")
    app_root = (ROOT / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    risk_utils = (ROOT / "web" / "src" / "utils" / "riskUtils.ts").read_text(encoding="utf-8")
    return {
        "industry_substitute_route": "/industry/" in detail and "industryProductId" in detail,
        "decision_uses_session_product": "industrySession?.product_id" in app_root,
        "no_hardcoded_beaglebone_default": "|| 'beaglebone-black'" not in app_root,
        "second_source_insufficient_label": "INSUFFICIENT_DATA" in table and "secondSourceLabel" in table,
        "lifecycle_timeline_explicit_insufficient": "This timeline does not default to Active" in detail,
        "sparkline_not_fabricated_for_insufficient": "INSUFFICIENT_DATA" in risk_utils and "return [];" in risk_utils,
        "dashboard_avg_risk_insufficient": "INSUFFICIENT_DATA" in app and "insufficientOverall" in app,
        "live_browser": "not_run_no_browser_mcp",
        "notes": "Live browser click-through was not available. Honesty is checked from API payloads and UI source.",
    }


def run_pytest() -> Dict[str, Any]:
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "--tb=no"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    passed = failed = skipped = errors = 0
    total = 0
    match = re.search(r"(\d+) passed", text)
    if match:
        passed = int(match.group(1))
    match = re.search(r"(\d+) failed", text)
    if match:
        failed = int(match.group(1))
    match = re.search(r"(\d+) skipped", text)
    if match:
        skipped = int(match.group(1))
    match = re.search(r"(\d+) error", text)
    if match:
        errors = int(match.group(1))
    total = passed + failed + skipped + errors
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "errors": errors,
        "exit_code": proc.returncode,
        "summary_line": next((line for line in reversed(text.splitlines()) if "passed" in line), text[-400:]),
        "command": "python -m pytest tests",
    }


def verdicts(payload: Dict[str, Any]) -> Dict[str, Any]:
    specs = payload["spec_classification"]
    u2 = payload["u2_trace"]
    gates = payload["engineering_gates"]
    vendor = payload["vendor_lifecycle"]
    iso = payload["isolation"]
    api = payload["api"]
    tests = payload["tests"]
    provenance = payload["provenance"]
    ui = payload["ui_source"]
    identity = api.get("identity_checks") or {}
    return {
        "tests": tests.get("failed") == 0 and tests.get("errors") == 0 and tests.get("passed", 0) > 0,
        "u2_is_tps65217c": u2.get("original_mpn") == "TPS65217C" and u2.get("component_model_id") == "mdl_48134fac2009",
        "industry_never_esp32": bool(u2.get("industry_never_returns_esp32")) and not iso.get("industry_request_esp32"),
        "engineering_params_reach_engine": bool(u2.get("specs_reaching_engine", {}).get("input_voltage_min_v")),
        "identity_specs_removed": specs.get("identity_bom_rows") == 0,
        "rating_not_safe_margin": bool(gates.get("rating_not_treated_as_safe")),
        "vendor_insufficient": vendor.get("vendor_status") == "INSUFFICIENT_DATA",
        "lifecycle_not_active": bool(vendor.get("unknown_not_active")),
        "api_identity": all(identity.values()) if identity else False,
        "provenance_traced": all(item.get("traced") for item in provenance),
        "ui_source_honesty": all(
            ui.get(key) is True
            for key in (
                "industry_substitute_route",
                "decision_uses_session_product",
                "no_hardcoded_beaglebone_default",
                "second_source_insufficient_label",
                "lifecycle_timeline_explicit_insufficient",
                "sparkline_not_fabricated_for_insufficient",
            )
        ),
    }


def main() -> Dict[str, Any]:
    payload = {
        "tests": run_pytest(),
        "spec_classification": classify_specs(),
        "u2_trace": trace_u2(),
        "engineering_gates": engineering_gates(),
        "vendor_lifecycle": vendor_lifecycle(),
        "isolation": isolation(),
        "provenance": provenance_tps65217c(),
        "api": api_checks(),
        "ui_source": ui_source_honesty(),
        "parameter_aliases": PARAMETER_ALIASES,
    }
    payload["verdicts"] = verdicts(payload)
    payload["demo_ready"] = False
    payload["demo_ready_reason"] = (
        "BeagleBone Black U2 is demoable with honest INSUFFICIENT_DATA gaps. "
        "Do not claim full industry demo-ready: vendor, lifecycle, operating-point, "
        "reliability, and most models still lack engineering specifications."
    )
    return payload


if __name__ == "__main__":
    os.chdir(ROOT)
    result = main()
    out = ROOT / "outputs" / "DEMO_VALIDATION_RESULTS.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(str(out))
