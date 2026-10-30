"""Provider data must never be fabricated from a local BOM model."""

from datetime import datetime, timedelta, timezone

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


def _vendor_row(**overrides):
    row = {
        "component_model_id": "mdl_one", "vendor_id": "vnd_one", "vendor_name": "DigiKey",
        "stock_quantity": "0", "lead_time_days": "14", "unit_price": "1.25", "currency": "USD",
        "retrieval_state": "LIVE", "data_provenance": "REAL_DISTRIBUTOR_DATA",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
    }
    row.update(overrides)
    return row


def test_supply_overlay_uses_current_rows_and_preserves_zero_stock(monkeypatch):
    monkeypatch.setattr(catalog_adapter, "find_model_by_mpn", lambda _mpn: {"component_model_id": "mdl_one"})
    monkeypatch.setattr(catalog_adapter, "vendor_rows_for_mpn", lambda _mpn: [_vendor_row()])
    monkeypatch.setattr(catalog_adapter, "read_csv", lambda name: [] if name == "data_conflicts.csv" else [])

    overlay = catalog_adapter.supply_overlay("PART-1")
    assert overlay["freshness"] == "CURRENT"
    assert overlay["stock"] == 0
    assert overlay["fresh_records"] == 1


def test_supply_overlay_excludes_stale_or_undated_rows(monkeypatch):
    monkeypatch.setattr(catalog_adapter, "find_model_by_mpn", lambda _mpn: {"component_model_id": "mdl_one"})
    stale = _vendor_row(expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())
    unknown = _vendor_row(expires_at="")
    monkeypatch.setattr(catalog_adapter, "vendor_rows_for_mpn", lambda _mpn: [stale, unknown])
    monkeypatch.setattr(catalog_adapter, "read_csv", lambda name: [] if name == "data_conflicts.csv" else [])

    overlay = catalog_adapter.supply_overlay("PART-1")
    assert overlay["freshness"] == "STALE"
    assert overlay["stock"] is None
    assert overlay["excluded_records"] == 2


def test_supply_overlay_withholds_conflicted_values(monkeypatch):
    monkeypatch.setattr(catalog_adapter, "find_model_by_mpn", lambda _mpn: {"component_model_id": "mdl_one"})
    monkeypatch.setattr(catalog_adapter, "vendor_rows_for_mpn", lambda _mpn: [_vendor_row()])
    monkeypatch.setattr(
        catalog_adapter,
        "read_csv",
        lambda name: [{"component_model_id": "mdl_one", "field_name": "unit_price", "resolution_status": "UNRESOLVED"}] if name == "data_conflicts.csv" else [],
    )

    overlay = catalog_adapter.supply_overlay("PART-1")
    assert overlay["freshness"] == "CONFLICT"
    assert overlay["stock"] is None
    assert overlay["conflicts"]
