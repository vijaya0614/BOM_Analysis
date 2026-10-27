# Substitute Recommendation API

This project currently uses a dependency-free Python API facade so Person 3 can
integrate without waiting for a framework decision. The same functions can be
wrapped later in Flask/FastAPI.

## Run Local HTTP API

```bash
python -m src.substitute_api
```

Default URL: `http://127.0.0.1:8000`

## Endpoints

### GET /components/{component_id}

Example:

```bash
curl http://127.0.0.1:8000/components/U1
```

Returns the component spec, supply-chain fields, and physical hardware mapping.

### GET /components/{component_id}/substitutes

Example:

```bash
curl http://127.0.0.1:8000/components/U1/substitutes
```

Optional query:

```bash
curl "http://127.0.0.1:8000/components/U1/substitutes?include_incompatible=false"
```

### POST /substitutes/search

Example body:

```json
{
  "component_id": "U1",
  "include_incompatible": true
}
```

### GET /substitutes/{original_id}/{candidate_id}

Example:

```bash
curl http://127.0.0.1:8000/substitutes/U1/REG_DROPIN_5V_3A
```

### GET /substitutes/{original_id}/{candidate_id}/comparison

Alias for the comparison route expected by the UI / Person 3 contract:

```bash
curl http://127.0.0.1:8000/substitutes/U1/REG_DROPIN_5V_3A/comparison
```

### GET /risk-report/substitutes

Maps a generated Person 1 risk report into substitute recommendations where
catalog specs exist:

```bash
curl "http://127.0.0.1:8000/risk-report/substitutes?path=outputs/risk_analysis_mini_smart_cooling_controller.json"
```

## Response Contract

Substitute responses contain:

- `original`: selected component details.
- `candidates`: ranked substitute list.
- `compatibility_score`: transparent 0-100 score from deterministic checks.
- `confidence_score`: 0-100 score for evidence completeness, separate from compatibility.
- `supply_chain_score`: 0-100 health score derived through Person 1's risk engine.
- `ranking_score`: compatibility plus supply-chain ranking.
- `classification`: one of `DROP_IN_CANDIDATE`, `REQUIRES_REDESIGN`, `INCOMPATIBLE`.
- `checks`: per-parameter match/mismatch/unknown results with impact and weight.
- `evidence_summary`: matched/mismatched/unknown counts and parameter lists.
- `insufficient_evidence`: `true` when important specs were missing.
- `matched_parameters`, `mismatched_parameters`, `unknown_parameters`.
- `explanation`: generated only from verified structured checks.
- `advisory_warning`: validation reminder for engineers.
- `llm_used`: currently `false`.
- `vector_search_used`: currently `false`.

## UI Integration

The static dashboard in `web/index.html` now opens a Substitute Intelligence
side panel when a component row is selected. The panel calls:

```text
GET http://127.0.0.1:8000/components/{part_number_or_refdes}/substitutes
```

For the demo, start the API before using the panel:

```bash
python -m src.substitute_api
```

If the API is not running, the UI shows a clear connection message instead of
fabricating recommendations.

## Demo Component IDs

- `U1`: 12V-to-5V buck regulator, physical location `REGULATOR_1`.
- `U2`: ESP32 module, physical location `MCU_1`.
- `U3`: temperature sensor, physical location `TEMP_SENSOR_1`.
- `Q1`: fan MOSFET, physical location `MOSFET_1`.
- `R1`: 10k resistor, physical location `RESISTOR_1`.
- `C1`: 100 nF capacitor, physical location `CAPACITOR_1`.

For `U1`, demo candidates include:

- `REG_DROPIN_5V_3A`: drop-in candidate.
- `REG_REDESIGN_5V_3A`: electrically compatible but package/pinout redesign.
- `REG_BAD_3V3_1A`: incompatible voltage/current.
- `REG_EOL_COMPAT`: technically compatible but bad supply-chain health.

All catalog claims in `data/component_specs.csv` are synthetic hackathon demo data.

## AI Boundary

Compatibility decisions are made by deterministic rules only. The current API
does not call an LLM, train a model, fine-tune a model, or use embeddings. A
future LLM layer may summarize the already-computed `checks`,
`evidence_summary`, scores, and supply-chain fields, but it must not invent
specifications or override the rule-based classification.
