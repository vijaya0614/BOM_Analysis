# SENTINEL Enrichment Service & API Integration

## Overview

SENTINEL enriches normalized component models using distributor and manufacturer API providers: **DigiKey Product Information V4** and **Nexar GraphQL API**.

## Architecture & Providers

- **DigiKey Provider** (`src/providers/digikey_provider.py`, `digikey_auth.py`):
  - Uses 2-legged OAuth2 authentication.
  - Keyword search via `/products/v4/search/keyword` and product details via `/products/v4/search/{dkpn}/productdetails`.
- **Nexar Provider** (`src/providers/nexar_provider.py`, `client.py`):
  - Uses OAuth2 client credentials against `https://identity.nexar.com/connect/token`.
  - Executes GraphQL queries against `https://api.nexar.com/graphql/`.

## Enrichment Orchestrator

Command:
```bash
python -m src.industry_data.enrichment_service --mpn TPS65217C
python -m src.industry_data.enrichment_service --product beaglebone-black
python -m src.industry_data.enrichment_service --all
```

Flow:
1. **Deduplication**: Extracts unique MPNs across target BOM lines.
2. **Cache Check**: Checks `data/api_cache/<provider>/` for non-expired responses.
3. **API Query**: On cache miss, queries active providers with exponential backoff on HTTP 429/5xx. An HTTP 401 invalidates the in-memory OAuth token and retries once with a refreshed client-credential token where available.
4. **Raw Response Storage**: Stores original HTTP JSON payloads in `data/api_raw/<provider>/`.
5. **Normalization & Provenance**: Maps provider response fields and records provenance in `field_provenance.csv`.
6. **Conflict Logging**: Discrepancies between providers are recorded in `data_conflicts.csv`.

## Provider Health & API Routes

- `GET /api/providers/health`: Returns safe status metadata (`configured`, `authentication_status`, `last_success`, `last_error`).
- `GET /api/providers/conflicts`: Returns logged provider discrepancies.
- `POST /api/enrichment/run`: Triggers enrichment jobs with optional `product_ids` and `region`.

For a controlled on-demand lookup, provide a bounded MPN list (maximum 10):

```text
POST /api/enrichment/run
{"mpns":["TPS65217C"],"providers":["digikey","nexar"],"region":"IN","force_refresh":true}
```

The Vendor Comparison page uses this one-MPN path for its **Refresh live data** button. It never launches an uncontrolled batch request. Returned stock, price, lifecycle, specification, and datasheet evidence is stored with provider provenance. Missing provider fields remain unavailable.

## Freshness and provider state

Every persisted vendor offer records its provider, retrieval timestamp, expiry timestamp (when cached), and `LIVE`, `CACHED`, or `STALE` retrieval state. The Vendor Comparison UI shows those labels without converting currencies or estimating supplier values.

`GET /api/industry/providers` is credential-safe and exposes configuration, last request, last success, safe failure category, and HTTP status. `QUOTA_EXHAUSTED`, `NO_SUPPLY_ENTITLEMENT`, `AUTHENTICATION_FAILURE`, and `NO_RESULT` remain distinct; a quota or access error is never presented as a part no-match.

## Security & Offline Mode

- Real API credentials must be stored strictly in `.env` (gitignored).
- If credentials are not configured, SENTINEL operates seamlessly in **offline mode**, keeping provider fields as `UNKNOWN` / `MISSING` without throwing fatal errors.
- DigiKey and Nexar are queried independently. A failure from one provider does not prevent evidence from the other provider from being preserved. If both cannot supply evidence, the component remains unresolved; SENTINEL never creates supplier facts as a fallback.
