"""Industry-design risk requests must use normalized imported BOM lines."""

from src import risk_api


def test_analyze_industry_product_exports_only_normalized_bom_identity(monkeypatch, tmp_path):
    monkeypatch.setattr(
        risk_api,
        "read_csv",
        lambda name: [
            {
                "product_id": "beaglebone-black", "original_mpn": "TPS65217C", "reference_designator": "U1",
                "quantity": "1", "original_manufacturer": "Texas Instruments", "original_description": "PMIC",
            }
        ] if name == "bom_lines.csv" else [],
    )
    monkeypatch.setattr(risk_api, "UPLOAD_DIR", str(tmp_path))
    captured = {}
    monkeypatch.setattr(risk_api, "analyze_bom_path", lambda path, title: captured.update(path=path, title=title) or {"dashboard": {}})

    result = risk_api.analyze_industry_product("beaglebone_black", "BeagleBone Black System")

    assert result == {"dashboard": {}}
    content = (tmp_path / "normalized_beaglebone_black.csv").read_text(encoding="utf-8")
    assert "TPS65217C" in content
    assert captured["title"] == "BeagleBone Black System"


def test_analyze_industry_product_reports_missing_normalized_bom(monkeypatch):
    monkeypatch.setattr(risk_api, "read_csv", lambda _name: [])

    result = risk_api.analyze_industry_product("beaglebone_black", "BeagleBone Black System")

    assert result["error"] == "NO_IMPORTED_BOM"
