import json
import threading
from http.server import HTTPServer
from urllib.request import urlopen

from src.candidate_orchestrator import evaluate_candidate_decision
from src.substitute_api import SubstituteRequestHandler


def _get(server: HTTPServer, path: str) -> dict:
    with urlopen(f"http://127.0.0.1:{server.server_port}{path}") as response:
        assert response.status == 200
        return json.loads(response.read())


def test_decision_route_returns_unwrapped_orchestrator_result_and_keeps_missing_data():
    server = HTTPServer(("127.0.0.1", 0), SubstituteRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        u2 = _get(server, "/decision/beaglebone-black/U2")
        assert u2 == evaluate_candidate_decision("beaglebone-black", "U2")
        generated = u2["candidates"][0]["candidate_generation"]
        assert generated["compatibility_score"] == 70
        assert generated["confidence_score"] == 70

        u5 = _get(server, "/decision/beaglebone-black/U5")
        assert u5["risk_trigger"]["status"] == "INSUFFICIENT_DATA"
        assert u5["candidates"][0]["downstream_impact"]["status"] == "INSUFFICIENT_DATA"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
