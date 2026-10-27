from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.component_catalog import find_component, load_component_catalog
from src.find_substitutes_api import GENERIC_500, build_app
from src.hybrid_substitute import (
    EXACT_DROP_IN,
    REQUIRES_REDESIGN,
    CosineReranker,
    HashingEmbedder,
    HybridSubstitutePipeline,
    LocalVectorIndex,
    mechanical_match,
    pin_count,
)


def _pipeline() -> HybridSubstitutePipeline:
    embedder = HashingEmbedder()
    return HybridSubstitutePipeline(
        embedder=embedder,
        reranker=CosineReranker(embedder),
        index=LocalVectorIndex(),
        catalog_path="data/component_specs.csv",
        data_dir="data",
    )


def _client(pipeline=None) -> TestClient:
    return TestClient(build_app(pipeline or _pipeline()), raise_server_exceptions=False)


def _token(client: TestClient, username: str = "engineer", password: str = "changeme") -> str:
    response = client.post("/token", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(client: TestClient, username: str = "engineer") -> dict:
    return {"Authorization": f"Bearer {_token(client, username)}"}


def test_hard_filter_requires_exact_package_and_pin_count():
    original = find_component("U1")
    drop_in = find_component("REG_DROPIN_5V_3A")
    redesign_pkg = find_component("REG_REDESIGN_5V_3A")
    wrong_pkg = find_component("REG_BAD_3V3_1A")
    assert original and drop_in and redesign_pkg and wrong_pkg
    assert pin_count(original) == pin_count(drop_in)
    assert mechanical_match(original, drop_in) is True
    assert mechanical_match(original, redesign_pkg) is False
    assert mechanical_match(original, wrong_pkg) is False


def test_pipeline_returns_top_10_classified_drop_in_or_redesign():
    result = _pipeline().find_substitutes("NMOS-FAN-01", top_k=10)
    assert result["hard_filter"]["package"] == "SOT-223"
    assert result["pipeline"][0] == "exact_pin_count_and_package_filter"
    assert "pinecone_top_10" in result["pipeline"]
    assert "cross_encoder_rerank" in result["pipeline"]
    assert len(result["substitutes"]) <= 10
    packages = {item["package"] for item in result["substitutes"]}
    assert packages <= {"SOT-223"}
    classes = {item["classification"] for item in result["substitutes"]}
    assert classes <= {EXACT_DROP_IN, REQUIRES_REDESIGN}
    assert EXACT_DROP_IN in classes
    assert REQUIRES_REDESIGN in classes
    part_numbers = [item["part_number"] for item in result["substitutes"]]
    assert "NMOS-FAN-03" not in part_numbers


def test_find_substitutes_requires_jwt():
    client = _client()
    response = client.get("/find_substitutes", params={"part_number": "U1"})
    assert response.status_code == 401
    assert "Internal server error" not in response.text


def test_fastapi_find_substitutes_get_and_post():
    client = _client()
    missing = client.get("/find_substitutes", params={"part_number": "NO-SUCH-PART"}, headers=_auth(client, "auditor"))
    assert missing.status_code == 404
    assert "Traceback" not in missing.text

    response = client.get(
        "/find_substitutes",
        params={"part_number": "REG-5V-BUCK-01"},
        headers=_auth(client, "reviewer"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["part_number"] == "REG-5V-BUCK-01"
    assert all(item["classification"] in {EXACT_DROP_IN, REQUIRES_REDESIGN} for item in body["substitutes"])
    assert all(item["package"] == "TO-263" for item in body["substitutes"])

    posted = client.post(
        "/find_substitutes",
        json={"part_number": "U1", "top_k": 10},
        headers=_auth(client, "engineer"),
    )
    assert posted.status_code == 200
    assert posted.json()["component_id"] == "U1"


def test_find_substitutes_rate_limited_per_user():
    client = _client()
    headers = _auth(client, "engineer")
    first = client.get("/find_substitutes", params={"part_number": "U1"}, headers=headers)
    second = client.get("/find_substitutes", params={"part_number": "U1"}, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 429


def test_unhandled_errors_go_to_sentry_with_generic_500():
    pipeline = _pipeline()
    pipeline.find_substitutes = MagicMock(side_effect=RuntimeError("secret stack internals"))
    capture = MagicMock()
    with patch("src.find_substitutes_api.sentry_sdk.capture_exception", capture):
        client = _client(pipeline)
        response = client.get("/find_substitutes", params={"part_number": "U1"}, headers=_auth(client, "engineer"))
    assert response.status_code == 500
    assert response.json() == GENERIC_500
    assert "secret stack internals" not in response.text
    assert "Traceback" not in response.text
    capture.assert_called_once()
    logged = capture.call_args[0][0]
    assert isinstance(logged, RuntimeError)


def test_catalog_pin_counts_are_stable_for_known_packages():
    catalog = load_component_catalog()
    lqfp = catalog["STM32F401RCT6_COMP"]
    assert pin_count(lqfp) == 64
    assert pin_count(catalog["R1"]) == 2
