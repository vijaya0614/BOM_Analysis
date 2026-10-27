"""Industry HTTP payloads are compact, provenance-aware, and credential-safe."""

import base64

from src.industry_data import http_routes


def test_industry_status_never_exposes_credentials():
    payload = http_routes.handle_get("/api/industry/status", {})

    assert payload is not None
    assert payload["data_source"] == "REAL_PUBLIC_SOURCE"
    assert {"digikey", "nexar", "mouser"} == set(payload["providers"])
    assert "client_secret" not in str(payload).lower()
    assert "access_token" not in str(payload).lower()


def test_component_industry_route_marks_missing_data_explicitly():
    payload = http_routes.handle_get("/api/industry/component/NOT-A-REAL-MPN", {})

    assert payload is not None
    assert payload["data_source"] == "MISSING"
    assert payload["vendor_records"] == []


def test_component_industry_route_preserves_local_bom_provenance():
    payload = http_routes.handle_get("/api/industry/component/TPS65217C", {})

    assert payload is not None
    # Existing local BOM provenance must not be downgraded when a separate
    # provider-backed record is also present from a prior opt-in enrichment.
    assert payload["data_source"] in {"REAL_PUBLIC_SOURCE", "REAL_DISTRIBUTOR_DATA"}
    assert "documents" in payload


def test_import_route_summarizes_importer_result(monkeypatch):
    def fake_import(**_kwargs):
        return {
            "import_id": "imp_test",
            "dry_run": True,
            "input_files": ["a.csv"],
            "products_detected": ["example"],
            "boms_detected": [{"file": "a.csv"}],
            "bom_rows": 2,
            "files_classified": [{"file": "a.csv"}],
            "duplicates": ["same.csv"],
            "warnings": [],
            "errors": [],
            "manifest": "",
        }

    monkeypatch.setattr(http_routes, "run_import", fake_import)
    payload = http_routes.handle_post("/api/industry/import", {"dry_run": True})

    assert payload == {
        "import_id": "imp_test", "dry_run": True, "files_detected": 1,
        "products_detected": ["example"], "bom_files": 1, "bom_rows": 2,
        "documents_registered": 1, "duplicates": 1, "warnings": [], "errors": [], "manifest": "",
    }


def test_uploaded_industry_file_is_written_only_to_controlled_inbox(monkeypatch, tmp_path):
    paths = http_routes.ImportPaths(tmp_path / "incoming", tmp_path / "raw", tmp_path / "manifests")
    monkeypatch.setattr(http_routes.ImportPaths, "defaults", classmethod(lambda _cls: paths))
    monkeypatch.setattr(
        http_routes,
        "run_import",
        lambda **_kwargs: {
            "import_id": "imp_upload", "dry_run": False, "input_files": ["custom.csv"],
            "products_detected": ["custom"], "boms_detected": [{"file": "custom.csv"}], "bom_rows": 1,
            "files_classified": [{"file": "custom.csv"}], "duplicates": [], "warnings": [], "errors": [], "manifest": "manifest.json",
        },
    )

    payload = http_routes.handle_post(
        "/api/industry/upload",
        {"filename": "../../custom.csv", "content_base64": base64.b64encode(b"MPN\nTPS65217C\n").decode("ascii")},
    )

    assert payload["uploaded_file"] == "custom.csv"
    assert (paths.incoming / "custom.csv").read_bytes() == b"MPN\nTPS65217C\n"
    assert payload["bom_rows"] == 1


def test_industry_components_returns_normalized_models_only(monkeypatch):
    rows = {
        "bom_lines.csv": [{"product_id": "custom", "component_model_id": "mdl_one"}],
        "component_models.csv": [
            {"component_model_id": "mdl_one", "mpn": "TPS65217C", "manufacturer": "Texas Instruments", "description": "PMIC", "package": "VQFN", "lifecycle_status": "UNKNOWN"},
            {"component_model_id": "mdl_other", "mpn": "OTHER", "manufacturer": "", "description": "", "package": "", "lifecycle_status": "UNKNOWN"},
        ],
    }
    monkeypatch.setattr(http_routes, "read_csv", lambda name: rows.get(name, []))

    payload = http_routes.handle_get("/api/industry/components", {"product_id": ["custom"]})

    assert payload["total"] == 1
    assert payload["components"] == [{"mpn": "TPS65217C", "manufacturer": "Texas Instruments", "description": "PMIC", "package": "VQFN", "lifecycle_status": "UNKNOWN"}]


def test_industry_boms_returns_real_counts_and_load_session(monkeypatch):
    rows = {
        "products.csv": [{"product_id": "beaglebone-black", "product_name": "BeagleBone Black", "manufacturer": "BeagleBoard.org"}],
        "bom_lines.csv": [{"product_id": "beaglebone-black", "component_model_id": "mdl_one"}],
        "documents.csv": [{"product_id": "beaglebone-black", "filename": "bbb-bom.csv"}],
        "vendor_supply_records.csv": [{"component_model_id": "mdl_one"}],
    }
    monkeypatch.setattr(http_routes, "read_csv", lambda name: rows.get(name, []))
    monkeypatch.setattr(http_routes, "industry_status", lambda: {"latest_manifest": "imp_test.json"})

    listing = http_routes.handle_get("/api/industry/boms", {})
    loaded = http_routes.handle_post("/api/industry/bom/load", {"product_id": "beaglebone-black"})

    assert listing["boms"][0]["bom_lines"] == 1
    assert listing["boms"][0]["unique_mpns"] == 1
    assert loaded["status"] == "READY"
    assert loaded["source_document"] == "bbb-bom.csv"


def test_single_mpn_enrichment_request_passes_only_bounded_targets(monkeypatch):
    captured = {}
    monkeypatch.setattr(http_routes, "run_enrichment", lambda **kwargs: captured.update(kwargs) or {"resolved": 0})

    payload = http_routes.handle_post("/api/enrichment/run", {"mpns": [" TPS65217C "] * 12, "region": "IN", "force_refresh": True})

    assert payload == {"resolved": 0}
    assert captured["mpns"] == ["TPS65217C"] * 10
    assert captured["region"] == "IN"
    assert captured["force_refresh"] is True
