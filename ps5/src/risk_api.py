import json
import os
import re
import tempfile
import csv
import hashlib
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from src.component_catalog import find_component
from src.main import run_pipeline
from src.industry_data.csv_store import read_csv
from src.industry_data.http_routes import handle_get as handle_industry_get, handle_post as handle_industry_post


DATA_DIR = "data"
OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "bom_risk_sentinel_api_reports")
UPLOAD_DIR = os.path.join("outputs", "api_uploads")
MAX_REQUEST_BYTES = 70 * 1024 * 1024

INDUSTRY_PROJECT_IDS = {
    "beaglebone_black": "beaglebone-black",
    "beaglebone_black_wireless": "beaglebone-black-wireless",
    "beaglebone_ai": "beaglebone-ai",
    "ti_tida_00222": "ti-tida-00222",
    "ti_tidep_0050": "ti-tidep-0050",
}

SAMPLE_PROJECTS = {
    "industrial_iot": {
        "name": "Industrial IoT Gateway",
        "bom_path": os.path.join("data", "sample_projects", "bom_industrial_iot_gateway.csv"),
    },
    "drone_controller": {
        "name": "Smart Drone Controller",
        "bom_path": os.path.join("data", "sample_projects", "bom_smart_drone_flight_controller.csv"),
    },
    "medical_oximeter": {
        "name": "Medical Oximeter",
        "bom_path": os.path.join("data", "sample_projects", "bom_medical_oximeter.csv"),
    },
    "burglar_alarm": {
        "name": "Burglar Alarm System",
        "bom_path": os.path.join("data", "sample_projects", "bom_burglar_alarm.csv"),
    },
    "fan_controller": {
        "name": "Mini Fan Controller",
        "bom_path": os.path.join("data", "sample_projects", "bom_mini_fan_controller.csv"),
    },
    "smart_cooling": {
        "name": "Smart Cooling Controller",
        "bom_path": os.path.join("data", "sample_projects", "bom_mini_smart_cooling_controller.csv"),
    },
    "touch_lamp": {
        "name": "Touch Sensor Lamp",
        "bom_path": os.path.join("data", "sample_projects", "bom_touch_sensor_lamp.csv"),
    },
    "water_level": {
        "name": "Water Level Indicator",
        "bom_path": os.path.join("data", "sample_projects", "bom_water_level_indicator.csv"),
    },
    "beaglebone_black": {
        "name": "BeagleBone Black System",
        "bom_path": os.path.join("data", "industry", "raw", "beaglebone_black", "bom.csv"),
    },
    "beaglebone_black_wireless": {
        "name": "BeagleBone Black Wireless",
        "bom_path": os.path.join("data", "industry", "raw", "beaglebone_black_wireless", "bom.csv"),
    },
    "beaglebone_ai": {
        "name": "BeagleBone AI System",
        "bom_path": os.path.join("data", "industry", "raw", "beaglebone_ai", "bom.csv"),
    },
    "ti_tida_00222": {
        "name": "TI TIDA-00222 Reference Design",
        "bom_path": os.path.join("data", "industry", "raw", "ti_tida_00222", "bom.csv"),
    },
    "ti_tidep_0050": {
        "name": "TI TIDEP0050 Industrial EVM",
        "bom_path": os.path.join("data", "industry", "raw", "ti_tidep_0050", "bom.csv"),
    },
}


def _safe_name(value: str) -> str:
    value = os.path.basename(value or "uploaded_bom.csv")
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value) or "uploaded_bom.csv"


def _output_path(label: str) -> str:
    safe = _safe_name(label).rsplit(".", 1)[0]
    return os.path.join(OUTPUT_DIR, f"risk_analysis_{safe}.json")


def _normalize_band(band: Any) -> str:
    """Map engine bands (Critical/High/…) to frontend uppercase keys."""
    raw = str(band or "").strip().upper()
    aliases = {
        "CRITICAL": "CRITICAL",
        "CRIT": "CRITICAL",
        "HIGH": "HIGH",
        "AT RISK": "HIGH",
        "MEDIUM": "MEDIUM",
        "MED": "MEDIUM",
        "LOW": "LOW",
        "HEALTHY": "LOW",
        "INSUFFICIENT_DATA": "INSUFFICIENT_DATA",
        "UNKNOWN": "INSUFFICIENT_DATA",
    }
    if raw in aliases:
        return aliases[raw]
    return "INSUFFICIENT_DATA" if not raw else aliases.get(raw, "INSUFFICIENT_DATA")


def _lifecycle_ui(status: Any) -> str:
    raw = str(status or "").strip().upper()
    if raw in ("OBSOLETE", "EOL"):
        return "EOL"
    if raw == "NRND":
        return "NRND"
    if raw in ("SINGLE_SOURCE", "SINGLE-SOURCE"):
        return "SINGLE_SOURCE"
    if raw in ("ACTIVE",):
        return "ACTIVE"
    if raw in ("UNCONFIRMED", "UNKNOWN"):
        return "UNCONFIRMED"
    return "INSUFFICIENT_DATA"


def _factor_scores(part: Dict[str, Any]) -> Dict[str, Any]:
    """Recompute the five engine risk dimensions (0–100) from report fields.

    Missing evidence stays null. A missing field is never replaced with 0.5.
    """
    def life_score():
        lifecycle = str(part.get("lifecycle_status") or "").strip()
        if lifecycle == "Active":
            return 0.0
        if lifecycle == "NRND":
            return 0.6
        if lifecycle in ("Obsolete", "EOL"):
            return 1.0
        return None

    second = part.get("has_second_source")
    if second is True:
        source = 0.0
    elif second is False:
        source = 1.0
    else:
        source = None

    lead = part.get("lead_time_weeks")
    lead_n = None if lead is None else min(float(lead) / 26.0, 1.0)

    stock = part.get("stock")
    stock_n = None if stock is None else max(0.0, 1.0 - min(float(stock) / 1000.0, 1.0))

    crit_raw = str(part.get("criticality") or "").strip().capitalize()
    if crit_raw == "Low":
        crit = 0.0
    elif crit_raw == "High":
        crit = 1.0
    elif crit_raw == "Medium":
        crit = 0.5
    else:
        crit = None

    score = part.get("risk_score")
    composite = None if score is None else round(float(score) * 100, 1)
    return {
        "lifecycle": None if life_score() is None else round(life_score() * 100, 1),
        "sourcing": None if source is None else round(source * 100, 1),
        "lead_time": None if lead_n is None else round(lead_n * 100, 1),
        "stock": None if stock_n is None else round(stock_n * 100, 1),
        "criticality": None if crit is None else round(crit * 100, 1),
        "composite": composite,
    }


def _category_ui(taxonomy: Any) -> str | None:
    text = str(taxonomy or "").lower()
    if not text:
        return None
    if any(k in text for k in ("mcu", "microcontroller", "soc", "flash", "memory")):
        return "Microcontroller"
    if any(k in text for k in ("power", "regulator", "buck", "ldo", "converter")):
        return "Power Management"
    if any(k in text for k in ("sensor", "mems", "imu", "temp")):
        return "Sensor"
    if any(k in text for k in ("transistor", "mosfet", "fet", "bjt")):
        return "Transistor"
    if any(k in text for k in ("passive", "resistor", "capacitor", "inductor", "discrete")):
        return "Passive"
    if any(k in text for k in ("interface", "logic", "usb", "uart", "connector")):
        return "Interface"
    return None


def _sparkline_from_factors(factors: Dict[str, Any], score: Any) -> list:
    """Build a deterministic series only from measured factor contributions."""
    numeric = []
    for key in ("lifecycle", "sourcing", "lead_time", "stock", "criticality", "composite"):
        value = factors.get(key)
        if value is None:
            return []
        numeric.append(float(value))
    if score is None:
        return []
    series = [
        numeric[0] * 0.55,
        numeric[1] * 0.60,
        numeric[2] * 0.70,
        numeric[3] * 0.75,
        numeric[4] * 0.85,
        (numeric[0] + numeric[1]) / 2,
        (numeric[2] + numeric[3]) / 2,
        numeric[5] * 0.92,
        float(score) * 100,
    ]
    return [round(max(0.0, min(100.0, v)), 1) for v in series]


def _dashboard_payload(report: Dict[str, Any], project_name: str) -> Dict[str, Any]:
    from src.industry_data.catalog_adapter import conflicts_for_mpn, lifecycle_label_for_mpn, lifecycle_quality_for_mpn, supply_overlay
    from src.industry_data.identity import is_industry_mpn
    from src.risk_engine import AHP_WEIGHTS, HORIZON_YEARS

    summary = report["summary"]
    parts = []
    for part in report["parts"]:
        pn = part.get("part_number") or ""
        if is_industry_mpn(pn):
            component = None
        else:
            component = find_component(pn, match_refdes=False)
        score_raw = part.get("risk_score")
        score = None if score_raw is None else float(score_raw)
        qty = int(part.get("qty") or 1)
        raw_exp = part.get("exposure_score")
        if raw_exp is None:
            exp = None
        else:
            raw_exp = float(raw_exp)
            exp = min(1.0, raw_exp / max(qty, 1)) if raw_exp > 1 else raw_exp
        factors = _factor_scores(part)
        band = _normalize_band(part.get("risk_band"))
        taxonomy = part.get("taxonomy_category")
        overlay = supply_overlay(pn) if pn else {}
        lifecycle_label = lifecycle_label_for_mpn(pn) if pn else None
        stock = part.get("stock")
        lead = part.get("lead_time_weeks")
        price = part.get("unit_cost_usd")
        if overlay:
            if stock is None and overlay.get("stock") is not None:
                stock = overlay["stock"]
            if lead is None and overlay.get("lead_time_weeks") is not None:
                lead = overlay["lead_time_weeks"]
            if price is None and overlay.get("unit_price") is not None:
                price = overlay["unit_price"]
        second_source = part.get("has_second_source")
        if second_source is None:
            second_source = overlay.get("has_second_source")
        parts.append(
            {
                "pn": pn or f"TBD-{part.get('raw_reference_str') or 'UNK'}",
                "ref": part.get("raw_reference_str") or ", ".join(part.get("references") or []),
                "qty": qty,
                "band": band,
                "score": score,
                "exp": exp,
                "conf": float(part.get("confidence_score") or 0.0),
                "criticality": part.get("criticality"),
                "reasons": part.get("risk_reasons") or ["No specific risk triggers"],
                "component_id": component.component_id if component else None,
                "substitute_lookup_id": component.component_id if component else None,
                "catalog_status": "FOUND" if component else "MISSING",
                "lead_time_weeks": lead,
                "stock_level": stock,
                "price": price,
                "lifecycle_status": _lifecycle_ui(part.get("lifecycle_status") or lifecycle_label),
                "source_quality": {
                    "vendor_supply": overlay.get("freshness", "INSUFFICIENT_DATA"),
                    "vendor_records_used": overlay.get("fresh_records", 0),
                    "vendor_records_excluded": overlay.get("excluded_records", 0),
                    "lifecycle": lifecycle_quality_for_mpn(pn) if pn else "INSUFFICIENT_DATA",
                    "conflicts": conflicts_for_mpn(pn) if pn else [],
                },
                "has_second_source": second_source,
                "evidence_status": part.get("evidence_status") or "",
                "is_dynamically_inferred": bool(part.get("is_dynamically_inferred")),
                "missing_fields": part.get("missing_fields") or [],
                "category": _category_ui(taxonomy),
                "risk_factors": factors,
                "sparkline_data": _sparkline_from_factors(factors, score),
            }
        )

    scores = [part["score"] for part in parts if part["score"] is not None]
    return {
        "name": project_name,
        "source_bom": report.get("source_bom"),
        "overall": _normalize_band(summary.get("overall_bom_risk_band")),
        "max_score": max(scores, default=None),
        "avg_score": summary.get("average_risk_score"),
        "completeness": int(round((summary.get("average_confidence_score") or 0.0) * 100)),
        "total_parts": summary["total_parts"],
        "total_units": summary["total_component_count"],
        "critical": summary["critical_count"],
        "high": summary["high_count"],
        "medium": summary["medium_count"],
        "low": summary["low_count"],
        "insufficient_data": summary.get("insufficient_data_count", 0),
        "source_quality": {
            "vendor_supply_current_parts": sum(1 for part in parts if part.get("source_quality", {}).get("vendor_supply") == "CURRENT"),
            "vendor_supply_stale_parts": sum(1 for part in parts if part.get("source_quality", {}).get("vendor_supply") == "STALE"),
            "vendor_supply_unknown_parts": sum(1 for part in parts if part.get("source_quality", {}).get("vendor_supply") in {"UNKNOWN", "INCOMPLETE", "CONFLICT", "INSUFFICIENT_DATA"}),
            "parts_with_unresolved_conflicts": sum(1 for part in parts if part.get("source_quality", {}).get("conflicts")),
        },
        "model_metadata": {
            "risk_score": {
                "method": "Fuzzy AHP weighted risk dimensions with deterministic override floors",
                "weights": AHP_WEIGHTS,
                "obsolescence_horizon_years": HORIZON_YEARS,
                "band_thresholds": {"LOW_MIN": 0.0, "MEDIUM_MIN": 0.30, "HIGH_MIN": 0.60, "CRITICAL_MIN": 0.85},
                "weight_calibration_status": "EXPERT_JUDGMENT_PRIORS_NOT_OUTCOME_CALIBRATED",
            }
        },
        "parts": parts,
    }


def analyze_bom_path(bom_path: str, project_name: str) -> Dict[str, Any]:
    output_path = _output_path(os.path.basename(bom_path))
    analysis = run_pipeline(bom_path, DATA_DIR, output_path, quiet=True)
    if not analysis:
        return {"error": "NO_VALID_BOM_ROWS", "message": "No valid BOM entries were parsed."}

    with open(output_path, mode="r", encoding="utf-8") as f:
        report = json.load(f)

    with open(bom_path, "rb") as source_handle:
        source_sha256 = hashlib.sha256(source_handle.read()).hexdigest()
    input_integrity = {
        "status": "USER_SUPPLIED_REVISION_UNVERIFIED",
        "source_bom": os.path.basename(bom_path),
        "source_sha256": source_sha256,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "limitations": ["Import time and file hash identify this input snapshot; they do not prove the BOM is the current released revision."],
    }
    report["input_integrity"] = input_integrity
    dashboard = _dashboard_payload(report, project_name)
    dashboard["input_integrity"] = input_integrity
    return {
        "project_name": project_name,
        "report_path": output_path,
        "report": report,
        "dashboard": dashboard,
        "input_integrity": input_integrity,
    }


def analyze_uploaded_csv(csv_text: str, filename: str) -> Dict[str, Any]:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_filename = _safe_name(filename)
    bom_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(bom_path, mode="w", encoding="utf-8") as f:
        f.write(csv_text)
    return analyze_bom_path(bom_path, safe_filename)


def analyze_industry_product(project_id: str, project_name: str) -> Dict[str, Any]:
    """Run the existing risk engine over normalized imported BOM occurrences.

    The importer is authoritative for industry files.  This adapter exports
    only identity/quantity fields into an ephemeral CSV accepted by the
    existing engine; it neither replaces source BOMs nor manufactures specs.
    """
    product_id = INDUSTRY_PROJECT_IDS.get(project_id)
    if not product_id:
        return {"error": "PROJECT_NOT_FOUND", "message": f"Unknown industry project '{project_id}'."}
    from src.industry_data.revision_selection import select_product_bom

    lines, revision_selection = select_product_bom(product_id, reader=read_csv)
    sources = {row.get("source_id"): row for row in read_csv("source_registry.csv")}
    if not lines:
        if revision_selection["status"] == "AMBIGUOUS_REVISION":
            return {"error": "AMBIGUOUS_REVISION", "message": "Multiple BOM revisions are present without an unambiguous source observation time; no report was generated."}
        return {"error": "NO_IMPORTED_BOM", "message": f"No normalized BOM lines are available for {project_name}. Import its source package first."}
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    bom_path = os.path.join(UPLOAD_DIR, f"normalized_{_safe_name(project_id)}.csv")
    with open(bom_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Part Number", "Reference", "Quantity", "Manufacturer", "Description", "Package"])
        writer.writeheader()
        for row in lines:
            writer.writerow(
                {
                    "Part Number": row.get("original_mpn", ""),
                    "Reference": row.get("reference_designator", ""),
                    "Quantity": row.get("quantity", "1"),
                    "Manufacturer": row.get("original_manufacturer", ""),
                    "Description": row.get("original_description", ""),
                    "Package": "",
                }
            )
    result = analyze_bom_path(bom_path, project_name)
    selected_source_ids = sorted({row.get("source_id") for row in lines if row.get("source_id")})
    retrieved = [sources[source_id].get("retrieved_at") for source_id in selected_source_ids if source_id in sources]
    unresolved = [row for row in read_csv("unresolved_mpns.csv") if row.get("product_id") == product_id]
    model_ids = {row.get("component_model_id") for row in lines if row.get("component_model_id")}
    conflicts = [row for row in read_csv("data_conflicts.csv") if row.get("component_model_id") in model_ids and (row.get("resolution_status") or "UNRESOLVED").upper() != "RESOLVED"]
    quality_status = (
        "CONFLICT" if conflicts else
        "INCOMPLETE" if unresolved or revision_selection["status"] == "INCOMPLETE" else
        revision_selection["status"]
    )
    input_integrity = {
        **revision_selection,
        "status": quality_status,
        "bom_line_count": len(lines),
        "source_ids": selected_source_ids,
        "source_document_count": len(selected_source_ids),
        "source_observed_at": sorted({value for value in retrieved if value}),
        "unresolved_mpn_count": len(unresolved),
        "unresolved_conflict_count": len(conflicts),
        "limitations": [
            "Imported revision metadata is not treated as current manufacturer revision unless a release date is recorded.",
            "Source observation time records when this package was imported; it does not prove the package is the latest released BOM.",
        ],
    }
    result["input_integrity"] = input_integrity
    if isinstance(result.get("report"), dict):
        result["report"]["input_integrity"] = input_integrity
    if isinstance(result.get("dashboard"), dict):
        result["dashboard"]["input_integrity"] = input_integrity
    return result


class RiskRequestHandler(BaseHTTPRequestHandler):
    def _send(self, payload: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]

        if parts == ["risk", "projects"]:
            projects = [
                {"id": project_id, "name": meta["name"], "bom_path": meta["bom_path"]}
                for project_id, meta in SAMPLE_PROJECTS.items()
            ]
            self._send({"projects": projects})
            return

        if parts == ["risk", "analyze"]:
            project_id = parse_qs(parsed.query).get("project", ["industrial_iot"])[0]
            project = SAMPLE_PROJECTS.get(project_id)
            if project is None:
                self._send({"error": "PROJECT_NOT_FOUND", "message": f"Unknown project '{project_id}'."}, 404)
                return
            result = analyze_industry_product(project_id, project["name"]) if project_id in INDUSTRY_PROJECT_IDS else analyze_bom_path(project["bom_path"], project["name"])
            self._send(result, 404 if result.get("error") else 200)
            return

        industry_payload = handle_industry_get(parsed.path, parse_qs(parsed.query))
        if industry_payload is not None:
            self._send(industry_payload)
            return

        self._send({"error": "NOT_FOUND", "message": "Route not found."}, 404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_REQUEST_BYTES:
            self._send({"error": "REQUEST_TOO_LARGE", "message": "Request body exceeds the 70 MiB local upload limit."}, 413)
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send({"error": "VALIDATION_ERROR", "message": "Body must be valid JSON."}, 400)
            return

        industry_payload = handle_industry_post(parsed.path, payload)
        if industry_payload is not None:
            self._send(industry_payload)
            return

        if parsed.path != "/risk/analyze":
            self._send({"error": "NOT_FOUND", "message": "Route not found."}, 404)
            return

        if payload.get("project"):
            project = SAMPLE_PROJECTS.get(payload["project"])
            if project is None:
                self._send({"error": "PROJECT_NOT_FOUND", "message": f"Unknown project '{payload['project']}'."}, 404)
                return
            project_id = payload["project"]
            result = analyze_industry_product(project_id, project["name"]) if project_id in INDUSTRY_PROJECT_IDS else analyze_bom_path(project["bom_path"], project["name"])
            self._send(result, 404 if result.get("error") else 200)
            return

        csv_text = payload.get("csv_text")
        if not csv_text:
            self._send({"error": "VALIDATION_ERROR", "message": "Body must include csv_text or project."}, 400)
            return
        self._send(analyze_uploaded_csv(csv_text, payload.get("filename", "uploaded_bom.csv")))


def run_server(host: str = "127.0.0.1", port: int = 8001) -> None:
    server = HTTPServer((host, port), RiskRequestHandler)
    print(f"Risk API listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
