# SENTINEL

Industry BOM intelligence: normalized public BOMs, engineering compatibility, and honest `INSUFFICIENT_DATA` when vendor, lifecycle, reliability, or operating-point evidence is missing.

This repository is **demoable for BeagleBone Black U2 (TPS65217C)** with real datasheet electrical parameters. It is **not** a complete industry product: distributor stock, lifecycle, FIT/MTBF, board operating points, and most model specifications remain empty on purpose.

## What is actually proven

| Path | Result |
|---|---|
| BeagleBone Black `U2` | `TPS65217C` / `mdl_48134fac2009` |
| Demo catalog `U2` | ESP32 (demo only) |
| Industry request for `U2` | never returns ESP32 |
| Vendor / lifecycle for TPS65217C | `INSUFFICIENT_DATA` / `UNKNOWN` |
| Manufacturer VIN max without a board operating point | `INSUFFICIENT_DATA`, never `SAFE_MARGIN` |

## Run tests

```bash
python -m pytest tests
```

## Start the demo

From the repository root, in three terminals:

```bash
python -m src.risk_api
python -m src.substitute_api
```

```bash
cd web
npm install
npm run dev
```

- Risk / industry API: `http://127.0.0.1:8001`
- Substitute / decision API: `http://127.0.0.1:8000`
- React UI: Vite default, typically `http://127.0.0.1:5173`

Do not put API keys in the ZIP or in git. Copy `web/.env.example` locally if you need to override API origins.

## Exact industry demo flow

1. Open the React app.
2. Go to **BOM Upload**.
3. Under **Industry BOMs**, load **BeagleBone Black** (do not load a demo sample project).
4. Open **Dashboard**. Expect overall band `INSUFFICIENT_DATA` — empty vendor tables are not converted into Active / stock / lead time.
5. Open **Components**, find **U2 / TPS65217C**.
6. Open **Component Detail**. Electrical fields come from the TPS65217C datasheet rows. Lifecycle timeline stays `INSUFFICIENT_DATA`, not Active.
7. Open **Substitutes**. The industry pool is `TPS65218D0RSLR` (`mdl_*`), not ESP32.
8. Open **Decision**. Product id is `beaglebone-black`, target is `U2`. VIN max 5.8 V vs candidate 5.5 V is a real mismatch.
9. Open **Vendor**. Feasibility is `INSUFFICIENT_DATA` unless a live provider actually returned offers.
10. Open **Evidence**. Trace VIN / Iout / Tmax to the normalized CSV provenance, not to a fabricated source.

## Components that should be demonstrated

- **Must show:** BeagleBone Black `U2` = `TPS65217C` (`mdl_48134fac2009`)
- **Optional contrast:** BeagleBone Black `U2` candidate `TPS65218D0RSLR` (real VIN-max mismatch)
- **Must not present as industry:** demo catalog `U2` = ESP32

## Known limitations that must not be hidden

- Vendor supply, stock, lead time, MOQ, and authorized-channel data are empty.
- Lifecycle is `UNKNOWN` and must stay `UNKNOWN` / `INSUFFICIENT_DATA`.
- Board operating points are not present; manufacturer ratings are not operating points.
- Reliability (FIT/MTBF) and degradation are not present for industry MPNs.
- Only two industry models currently have useful electrical specifications.
- TIDEP lines without a designator stay unresolved. TIDA has no archive BOM.

See `outputs/DEMO_READINESS_REPORT.md` and `outputs/DEMO_VALIDATION_RESULTS.json`.
