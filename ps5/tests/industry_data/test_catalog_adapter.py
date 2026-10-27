"""Provider data must never be fabricated from a local BOM model."""

from src.industry_data import catalog_adapter


def test_vendor_rows_are_empty_without_persisted_provider_evidence(monkeypatch):
    monkeypatch.setattr(catalog_adapter, "find_model_by_mpn", lambda _mpn: {"component_model_id": "mdl_one"})
    monkeypatch.setattr(catalog_adapter, "read_csv", lambda name: [] if name in {"vendors.csv", "vendor_supply_records.csv"} else [])

    assert catalog_adapter.vendor_rows_for_mpn("TPS65217C") == []


def test_vendor_rows_preserve_only_persisted_provider_values(monkeypatch):
    rows = {
        "vendors.csv": [{"vendor_id": "vnd_one", "vendor_name": "DigiKey", "region": "IN", "country": "IN"}],
        "vendor_supply_records.csv": [{"component_model_id": "mdl_one", "vendor_id": "vnd_one", "stock_quantity": "25", "data_provenance": "REAL_DISTRIBUTOR_DATA"}],
    }
    monkeypatch.setattr(catalog_adapter, "find_model_by_mpn", lambda _mpn: {"component_model_id": "mdl_one"})
    monkeypatch.setattr(catalog_adapter, "read_csv", lambda name: rows.get(name, []))

    assert catalog_adapter.vendor_rows_for_mpn("TPS65217C") == [{"component_model_id": "mdl_one", "vendor_id": "vnd_one", "stock_quantity": "25", "data_provenance": "REAL_DISTRIBUTOR_DATA", "vendor_name": "DigiKey"}]
