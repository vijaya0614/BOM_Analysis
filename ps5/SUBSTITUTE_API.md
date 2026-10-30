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
- `classification`: one of `DROP_IN_CANDIDATE`, `REQUIRES_REDESIGN`, `INCOMPATIBLE`, `INSUFFICIENT_EVIDENCE`.
- `drop_in_evidence`: source references and per-side status for package, pinout, and applicable ratings.
- `checks`: per-parameter match/mismatch/unknown results with impact and weight.
- `evidence_summary`: matched/mismatched/unknown counts and parameter lists.
- `insufficient_evidence`: `true` when important specs were missing.
- `matched_parameters`, `mismatched_parameters`, `unknown_parameters`.
- `explanation`: generated only from verified structured checks.
- `advisory_warning`: validation reminder for engineers.
- `llm_used`: currently `false`.
- `vector_search_used`: currently `false`.

## Drop-in Evidence Gate

Matching catalog values alone do not establish a drop-in. Both the original and candidate need exact-part source references for package, pinout, and each applicable electrical rating. Each reference must include a source identifier or title, a URL or document/page locator, `HIGH` or `MEDIUM` confidence, and a summary that cites the compared value. Demo fixture data and missing values remain `INSUFFICIENT_DATA`; recommendations expose them in `drop_in_evidence.unknown_parameters` and are not classified as drop-ins.

For `POST /api/substitutes/evaluate-gates`, attach an `evidence` object separately to `original_spec` and each candidate. Its shape is:

```json
{
  "evidence": {
    "package": {
      "source_id": "SRC-PART-PACKAGE",
      "source_title": "Manufacturer package drawing",
      "source_url": "https://manufacturer.example/package.pdf",
      "source_page": "4",
      "confidence": "HIGH",
      "source_type": "MANUFACTURER_DATASHEET",
      "evidence_summary": "SOIC-8 package"
    },
    "pinout": {
      "source_id": "SRC-PART-PINOUT",
      "source_title": "Manufacturer datasheet",
      "source_url": "https://manufacturer.example/datasheet.pdf",
      "source_page": "5",
      "confidence": "HIGH",
      "source_type": "MANUFACTURER_DATASHEET",
      "evidence_summary": "Pin 1 VIN; pin 2 GND"
    },
    "ratings": {
      "voltage_rating": {
        "source_id": "SRC-PART-VOLTAGE",
        "source_title": "Manufacturer datasheet",
        "source_url": "https://manufacturer.example/datasheet.pdf",
        "source_page": "6",
        "confidence": "HIGH",
        "source_type": "MANUFACTURER_DATASHEET",
        "evidence_summary": "30 V maximum input rating"
      }
    }
  }
}
```

The gate checks that a reference is present and cites the value supplied to the comparison; it does not fetch or independently authenticate external documents. Review the linked source before engineering approval.

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

- `REG_DROPIN_5V_3A`: matching demo specifications, but `INSUFFICIENT_EVIDENCE` until exact-part package, pinout, and rating sources are supplied.
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
