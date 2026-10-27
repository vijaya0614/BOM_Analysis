"""Unit tests for DigiKey and Nexar provider integrations with mocked data."""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from src.industry_data.api_cache import ApiCache
from src.industry_data import enrichment_service
from src.providers.base import ProviderPart
from src.providers.digikey_auth import DigiKeyAuthManager
from src.providers.digikey_provider import DigiKeyProvider
from src.providers.http import HttpTransport
from src.providers.mouser_provider import MouserProvider, compatible_manufacturer_mpn
from src.providers.nexar.client import NexarClient
from src.providers.nexar_provider import NexarProvider
from src.providers.settings import ROOT, get_settings

FIXTURES_DIR = ROOT / "tests" / "fixtures" / "providers"


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_digikey_provider_health():
    provider = DigiKeyProvider()
    health = provider.health()
    assert "configured" in health
    assert "authentication_status" in health
    assert "client_secret" not in json.dumps(health)
    assert "access_token" not in json.dumps(health)


def test_nexar_provider_health():
    provider = NexarProvider()
    health = provider.health()
    assert "configured" in health
    assert "authentication_status" in health
    assert "client_secret" not in json.dumps(health)
    assert "access_token" not in json.dumps(health)


def test_mouser_provider_health():
    provider = MouserProvider()
    health = provider.health()
    assert "configured" in health
    assert "authentication_status" in health
    assert "api_key" not in json.dumps(health).lower()
    assert "mouser_api_key" not in json.dumps(health)


def test_mouser_mock_response_parsing():
    fixture_path = FIXTURES_DIR / "mouser" / "mouser_search.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    part = MouserProvider()._map_payload(data, "TPS65217C", "search", "IN")
    assert part.success is True
    assert part.mpn == "TPS65217C"
    assert part.manufacturer == "Texas Instruments"
    assert part.offers[0].vendor_name == "Mouser Electronics"
    assert part.offers[0].stock_quantity == 248
    assert part.offers[0].lead_time_days == 112
    assert part.offers[0].unit_price == 4.21


def test_mouser_rejects_eval_board_for_ic_mpn():
    payload = {
        "SearchResults": {
            "Parts": [
                {
                    "ManufacturerPartNumber": "TPS65217CEVM",
                    "Manufacturer": "Texas Instruments",
                    "Description": "TPS65217C Eval Mod",
                    "AvailabilityInStock": "1",
                    "PriceBreaks": [{"Price": "$58.80", "Currency": "USD"}],
                }
            ]
        }
    }
    part = MouserProvider()._map_payload(payload, "TPS65217C", "search", "IN")
    assert part.success is False
    assert part.error_code == "NO_MATCH"


def test_mouser_accepts_orderable_packing_suffix():
    assert compatible_manufacturer_mpn("TPS65217C", "TPS65217CRSLR") is True
    assert compatible_manufacturer_mpn("TPS65217C", "TPS65217CEVM") is False
    payload = {
        "SearchResults": {
            "Parts": [
                {"ManufacturerPartNumber": "TPS65217CEVM", "Manufacturer": "Texas Instruments"},
                {
                    "ManufacturerPartNumber": "TPS65217CRSLR",
                    "Manufacturer": "Texas Instruments",
                    "AvailabilityInStock": "12",
                    "PriceBreaks": [{"Price": "$2.40", "Currency": "USD"}],
                },
            ]
        }
    }
    part = MouserProvider()._map_payload(payload, "TPS65217C", "search", "IN")
    assert part.success is True
    assert part.mpn == "TPS65217CRSLR"


def test_digikey_mock_response_parsing():
    fixture_path = FIXTURES_DIR / "digikey" / "digikey_search.json"
    assert fixture_path.is_file()
    data = json.loads(fixture_path.read_text(encoding="utf-8"))

    provider = DigiKeyProvider()
    part = provider._map_payload(data, "TPS65217C", "search", "IN")
    assert part.success is True
    assert part.mpn == "TPS65217C"
    assert part.manufacturer == "Texas Instruments"
    assert part.package == "48-VQFN"


def test_nexar_mock_response_parsing():
    fixture_path = FIXTURES_DIR / "nexar" / "nexar_query.json"
    assert fixture_path.is_file()
    data = json.loads(fixture_path.read_text(encoding="utf-8"))

    provider = NexarProvider()
    part = provider._from_body(data, "TPS65217C", "search", "IN")
    assert part.success is True
    assert part.mpn == "TPS65217C"
    assert len(part.offers) > 0
    assert part.offers[0].stock_quantity == 12500


def test_nexar_quota_error_is_not_reported_as_no_match():
    payload = {"errors": [{"message": "You have exceeded your part limit of 0. Please upgrade your plan."}]}

    part = NexarProvider()._from_body(payload, "TPS65217C", "details", "IN")

    assert part.success is False
    assert part.error_code == "QUOTA_EXHAUSTED"


def test_cache_key_isolated_by_query_manufacturer_and_region(tmp_path):
    cache = ApiCache("digikey", ttl_seconds=60, root=tmp_path)
    cache.set("details", "TPS65217C", "Texas Instruments", "IN", {"id": "in"})

    cached = cache.get("details", "TPS65217C", "Texas Instruments", "IN")
    assert cached is not None and cached["id"] == "in"
    assert "_sentinel_cache_stored_at" in cached
    assert cache.get("details", "TPS65217C", "Texas Instruments", "US") is None
    assert cache.get("details", "TPS65217C", "Other Manufacturer", "IN") is None
    assert cache.get("pricing", "TPS65217C", "Texas Instruments", "IN") is None


def test_digikey_retries_once_after_401_and_does_not_cache_failed_response(tmp_path):
    settings = replace(get_settings(), digikey_client_id="id", digikey_client_secret="secret")
    auth = MagicMock(spec=DigiKeyAuthManager)
    auth.configured.return_value = True
    cache = ApiCache("digikey", ttl_seconds=60, root=tmp_path)
    raw_store = MagicMock()
    provider = DigiKeyProvider(settings=settings, auth=auth, cache=cache, raw_store=raw_store)
    fixture = json.loads((FIXTURES_DIR / "digikey" / "digikey_search.json").read_text(encoding="utf-8"))
    provider._keyword_search = MagicMock(side_effect=[{"_http_status": 401}, {"_http_status": 200, "Products": [{"DigiKeyProductNumber": "296-TEST-ND"}]}])
    provider._product_details = MagicMock(return_value={"_http_status": 200, **fixture["details"]})

    part = provider.get_part_details("TPS65217C", "Texas Instruments", "IN")

    assert part.success is True
    assert provider._keyword_search.call_count == 2
    assert provider._product_details.call_count == 1
    assert cache.get("details", "TPS65217C", "Texas Instruments", "IN") is not None


def test_nexar_refreshes_client_credentials_and_retries_once_after_401():
    settings = replace(get_settings(), nexar_client_id="id", nexar_client_secret="secret", nexar_access_token="")
    transport = MagicMock()
    transport.request.side_effect = [
        FakeResponse(200, {"access_token": "token-one", "expires_in": 3600}),
        FakeResponse(401, {"error": "expired"}),
        FakeResponse(200, {"access_token": "token-two", "expires_in": 3600}),
        FakeResponse(200, {"data": {"ok": True}}),
    ]
    client = NexarClient(settings=settings, transport=transport)

    body = client.query_graphql("query { supSearchMpn { results { part { mpn } } } }", {"q": "TPS65217C"}, mpn="TPS65217C")

    assert body == {"data": {"ok": True}, "_http_status": 200}
    assert transport.request.call_count == 4
    graphql_calls = [call for call in transport.request.call_args_list if "api.nexar.com/graphql" in call.args[1]]
    assert graphql_calls[0].kwargs["headers"]["Authorization"] == "Bearer token-one"
    assert graphql_calls[1].kwargs["headers"]["Authorization"] == "Bearer token-two"


def test_http_transport_retries_rate_limit_response_once():
    settings = replace(get_settings(), max_retries=1, backoff_factor=1.0, request_delay_ms=0)
    client = MagicMock()
    client.request.side_effect = [FakeResponse(429, {"error": "rate_limited"}), FakeResponse(200, {"ok": True})]
    context = MagicMock()
    context.__enter__.return_value = client
    context.__exit__.return_value = False
    with patch("src.providers.http.httpx.Client", return_value=context), patch("src.providers.http.time.sleep"):
        response = HttpTransport(settings).request("GET", "https://example.test", provider="test", mpn="TPS65217C")

    assert response.status_code == 200
    assert client.request.call_count == 2


def test_enrichment_continues_when_first_provider_fails_and_second_succeeds(monkeypatch, tmp_path):
    class FailingProvider:
        name = "digikey"

        def get_part_details(self, *_args):
            return ProviderPart(provider=self.name, mpn="TPS65217C", success=False, error_code="HTTP_503")

    class WorkingProvider:
        name = "nexar"

        def get_part_details(self, *_args):
            return ProviderPart(provider=self.name, mpn="TPS65217C", manufacturer="Texas Instruments", success=True)

    monkeypatch.setattr(enrichment_service, "_providers", lambda _names: [FailingProvider(), WorkingProvider()])
    monkeypatch.setattr(enrichment_service, "ROOT", tmp_path)
    monkeypatch.setattr(enrichment_service, "SourceRegistry", lambda: MagicMock(register=lambda **_kwargs: "src_test"))
    monkeypatch.setattr(enrichment_service, "ProvenanceStore", MagicMock)
    monkeypatch.setattr(enrichment_service, "persist_part", lambda *_args, **_kwargs: {"vendor_records": 0, "specs": 0, "lifecycle": 0, "conflicts": 0})
    monkeypatch.setattr(enrichment_service, "detect_conflicts", lambda _model_id: 0)

    report = enrichment_service.run_enrichment(mpns=["TPS65217C"])

    assert report["resolved"] == 1
    assert report["digikey_matches"] == 0
    assert report["nexar_matches"] == 1
    assert report["mouser_matches"] == 0
    assert report["errors"] == 1
