import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from src.component_intelligence import (
    compare_reliability_outlook,
    get_component_analysis,
    get_component_degradation,
    get_component_evidence,
    get_component_profile,
    get_component_reliability,
    get_downstream_impact,
    get_operating_margins,
    build_degradation_scenario,
)
from src.component_catalog import find_component
from src.candidate_orchestrator import evaluate_candidate_decision
from src.risk_report_bridge import substitutes_for_risk_report
from src.substitute_engine import compare_components, recommend_industry_substitutes, recommend_substitutes


def get_component(component_id: str, catalog_path: str = "data/component_specs.csv") -> Dict[str, Any]:
    component = find_component(component_id, catalog_path)
    if component is None:
        return {
            "error": "COMPONENT_NOT_FOUND",
            "message": f"No component found for identifier '{component_id}'.",
        }
    return {"component": component.to_dict()}


def search_substitutes(payload: Dict[str, Any], catalog_path: str = "data/component_specs.csv", data_dir: str = "data") -> Dict[str, Any]:
    component_id = payload.get("component_id") or payload.get("original_id")
    if not component_id:
        return {
            "error": "VALIDATION_ERROR",
            "message": "Request must include component_id or original_id.",
        }
    include_incompatible = bool(payload.get("include_incompatible", True))
    return recommend_substitutes(component_id, catalog_path, data_dir, include_incompatible)


class SubstituteRequestHandler(BaseHTTPRequestHandler):
    catalog_path = "data/component_specs.csv"
    data_dir = "data"

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

        if len(parts) == 2 and parts[0] == "components":
            self._send(get_component(parts[1], self.catalog_path))
            return

        if len(parts) == 3 and parts[0] == "decision":
            decision = evaluate_candidate_decision(parts[1], parts[2])
            if decision.get("reason_codes") == ["TARGET_COMPONENT_SPEC_UNAVAILABLE"]:
                self._send(
                    {
                        "error": "NOT_FOUND",
                        "message": f"No decision target found for {parts[1]}/{parts[2]}.",
                    },
                    404,
                )
                return
            self._send(decision)
            return

        if len(parts) == 4 and parts[0] == "evidence" and parts[1] == "components":
            endpoint = parts[3]
            identifier = parts[2]
            if endpoint == "profile":
                self._send(get_component_profile(identifier, self.catalog_path))
                return
            if endpoint == "evidence":
                self._send(get_component_evidence(identifier, self.catalog_path))
                return
            if endpoint == "reliability":
                self._send(get_component_reliability(identifier, self.catalog_path))
                return
            if endpoint == "degradation":
                self._send(get_component_degradation(identifier, self.catalog_path))
                return
            if endpoint == "analysis":
                self._send(get_component_analysis(identifier, self.catalog_path))
                return
            if endpoint == "operating-margin":
                self._send(get_operating_margins(identifier, self.catalog_path))
                return
            if endpoint == "scenario":
                self._send(build_degradation_scenario(identifier, self.catalog_path))
                return
            if endpoint == "downstream-impact":
                query = parse_qs(parsed.query)
                product_id = (query.get("product_id") or [None])[0]
                self._send(get_downstream_impact(identifier, self.catalog_path, product_id=product_id))
                return

        if len(parts) == 4 and parts[0] == "industry" and parts[3] == "substitutes":
            self._send(recommend_industry_substitutes(parts[1], parts[2], self.data_dir))
            return

        if len(parts) == 3 and parts[0] == "components" and parts[2] == "substitutes":
            query = parse_qs(parsed.query)
            include_incompatible = query.get("include_incompatible", ["true"])[0].lower() != "false"
            self._send(recommend_substitutes(parts[1], self.catalog_path, self.data_dir, include_incompatible))
            return

        if len(parts) == 4 and parts[0] == "evidence" and parts[1] == "outlook":
            self._send(compare_reliability_outlook(parts[2], parts[3], self.catalog_path))
            return

        if len(parts) == 3 and parts[0] == "substitutes":
            self._send(compare_components(parts[1], parts[2], self.catalog_path, self.data_dir))
            return

        if len(parts) == 4 and parts[0] == "substitutes" and parts[3] == "comparison":
            self._send(compare_components(parts[1], parts[2], self.catalog_path, self.data_dir))
            return

        if len(parts) == 2 and parts[0] == "risk-report" and parts[1] == "substitutes":
            query = parse_qs(parsed.query)
            report_path = query.get("path", ["outputs/risk_analysis.json"])[0]
            include_incompatible = query.get("include_incompatible", ["true"])[0].lower() != "false"
            self._send(
                substitutes_for_risk_report(
                    report_path,
                    catalog_path=self.catalog_path,
                    data_dir=self.data_dir,
                    include_incompatible=include_incompatible,
                )
            )
            return

        self._send({"error": "NOT_FOUND", "message": "Route not found."}, 404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/substitutes/search":
            self._send({"error": "NOT_FOUND", "message": "Route not found."}, 404)
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send({"error": "VALIDATION_ERROR", "message": "Body must be valid JSON."}, 400)
            return

        self._send(search_substitutes(payload, self.catalog_path, self.data_dir))


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = HTTPServer((host, port), SubstituteRequestHandler)
    print(f"Substitute API listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
