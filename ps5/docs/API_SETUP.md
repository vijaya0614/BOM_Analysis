# DigiKey, Nexar, and Mouser API setup

SENTINEL talks to DigiKey Product Information V4, the Nexar GraphQL API, and the Mouser Search API from the **Python backend only**. Credentials never belong in React, Vite (`VITE_*`), HTML, CSV, or Git. Paste IDs, secrets, and the Mouser Search API key into local `.env`, then restart the Python APIs.

## 1. DigiKey developer credentials

1. Create an account at [https://developer.digikey.com](https://developer.digikey.com).
2. Register an application and subscribe it to **Product Information V4** (not deprecated Product Search v3).
3. Copy the **Client ID** into `DIGIKEY_CLIENT_ID`.
4. Copy the **Client Secret** into `DIGIKEY_CLIENT_SECRET`.
5. Add the DigiKey **Account ID** as `DIGIKEY_ACCOUNT_ID`. DigiKey requires `X-DIGIKEY-Account-Id` for successful Product Information V4 calls made with 2-legged OAuth. SENTINEL sends this official header; `DIGIKEY_CUSTOMER_ID` remains only as a legacy compatibility fallback.
6. For Product Information V4, DigiKey documents a **2-legged (client credentials)** OAuth flow. SENTINEL uses that by default.
7. Optional: if your org uses 3-legged OAuth, you may also set `DIGIKEY_REFRESH_TOKEN` after completing [OAuth 2.0: 3 Legged Flow](https://developer.digikey.com/tutorials-and-resources/oauth-20-3-legged-flow).
8. Sandbox vs production: set `DIGIKEY_API_BASE=https://sandbox-api.digikey.com` and `DIGIKEY_SANDBOX=true` for sandbox.

Authorization URL (3-legged only): `https://api.digikey.com/v1/oauth2/authorize`  
Token URL: `https://api.digikey.com/v1/oauth2/token`

## 2. Nexar application

1. Create a Nexar / Altium 365 developer application with **supply** access.
2. Copy Client ID → `NEXAR_CLIENT_ID`.
3. Copy Client Secret → `NEXAR_CLIENT_SECRET`.
4. SENTINEL requests tokens from `https://identity.nexar.com/connect/token` with `grant_type=client_credentials` and `scope=supply.domain`.
5. Development shortcut: you may set `NEXAR_ACCESS_TOKEN` to a short-lived token. Prefer client ID/secret in any shared environment.

GraphQL endpoint: `https://api.nexar.com/graphql/`

## 3. Mouser Search API

1. Create a Mouser API account at [https://www.mouser.com/api-hub/](https://www.mouser.com/api-hub/).
2. Subscribe to **Search API** (Part Number search).
3. Copy the API key into `MOUSER_API_KEY`.
4. Optional: `MOUSER_API_BASE=https://api.mouser.com/api/v1` (default) or `.../api/v2` if your key is issued for v2.

SENTINEL calls `POST /search/partnumber?apiKey=...` only. It does not scrape mouser.com.

## 4. Local `.env`

```text
copy .env.example .env
```

Fill in values in `.env` only. Do not put real secrets in `.env.example`.

Credentials belong in:

- process environment
- local `.env` (gitignored)

Credentials must **never** appear in:

- `web/` source
- `localStorage` / `sessionStorage`
- committed CSV/JSON
- logs or API responses

## 5. Test provider health

Start the substitute HTTP API (port 8000) or FastAPI (`src.find_substitutes_api`).

```text
GET http://127.0.0.1:8000/api/providers/health
```

or

```text
GET http://127.0.0.1:8001/api/providers/health
```

The payload reports `configured` and `authentication_status`. It never returns client secrets or access tokens.

## 6. Test one MPN

`TPS65217C` is present in the currently imported local BeagleBone BOM data. This command makes live requests only when the relevant provider credentials have been configured; otherwise it writes an explicit unresolved/offline result.

```text
python -m src.industry_data.enrichment_service --mpn TPS65217C --region IN
```

## 7. Import industry BOMs then enrich a product

Place downloaded source files under `incoming_industry_data/`. The importer copies originals into
`data/industry/raw/`, records SHA-256 provenance, safely extracts supported archive members, and
does not call providers unless `--enrich` is explicitly requested.

```text
python -m src.industry_data.importer --dry-run
python -m src.industry_data.importer
python -m src.industry_data.importer --enrich
python -m src.industry_data.enrichment_service --product beaglebone-black
python -m src.industry_data.enrichment_service --all
```

HTTP:

```text
POST /api/enrichment/run
{"product_ids": ["beaglebone-black"], "providers": ["digikey", "nexar"], "region": "IN", "force_refresh": false}
```

## 8. Caching

1. Check normalized industry CSVs.
2. Check `data/api_cache/<provider>/` for a non-expired key (`provider + query_type + mpn + manufacturer + region`).
3. On miss, call the API.
4. Store the raw JSON under `data/api_raw/<provider>/`.
5. Normalize and write provenance + vendor rows.

TTL: `API_CACHE_TTL_SECONDS` (default 86400).

Safe cache commands (never wipe everything automatically):

```text
python -m src.industry_data.api_cache --clear-expired
python -m src.industry_data.api_cache --clear-provider nexar
python -m src.industry_data.api_cache --clear-mpn TPS5402DGQ
python -m src.industry_data.enrichment_service --mpn TPS65217C --force-refresh
```

## 9. Rate limits

`API_BATCH_SIZE`, `API_REQUEST_DELAY_MS`, `API_MAX_RETRIES`, and `API_BACKOFF_FACTOR` control batching and exponential backoff on 429 / 5xx. A 401 invalidates the current OAuth token and performs one fresh-token retry when client credentials are available. One failed provider or MPN does not stop the job: the other configured provider is still attempted.

## 10. Rotate or revoke credentials

1. Rotate the secret in the DigiKey / Nexar developer portal.
2. Update `.env`.
3. Restart the backend process (in-memory tokens are discarded).
4. Optionally delete gitignored token files under `data/api_cache/` if present.

## 11. What must never be committed

- `.env` and any real client secrets
- Access tokens / refresh tokens
- `data/api_cache/` and `data/api_raw/` payloads from live accounts
- `VITE_DIGIKEY_*` or `VITE_NEXAR_*` secrets (these prefixes must not be used)

## 12. Unit vs live tests

Unit tests use sanitized fixtures under `tests/fixtures/providers/` and must not call live APIs.

Opt-in live checks:

```text
set RUN_LIVE_PROVIDER_TESTS=true
pytest tests/providers/test_live_providers.py
```
