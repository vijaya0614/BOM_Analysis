# SENTINEL demo readiness report

**Status: CONDITIONALLY DEMOABLE — not fully industry demo-ready.**

Tests pass. That is not the same as demo-ready. The BeagleBone Black `U2` path has a real join from BOM to engine to API. Vendor, lifecycle, operating-point, reliability, and most model specifications remain empty and must be shown as `INSUFFICIENT_DATA`.

Validation date: 2026-08-24  
Source of truth: this repository (`data/industry/normalized/`, `src/`, `web/`, `tests/`)  
Machine-readable companion: `outputs/DEMO_VALIDATION_RESULTS.json`

---

## Test suite

Command: `python -m pytest tests`

| Metric | Count |
|---|---|
| Total | 168 |
| Passed | 168 |
| Failed | 0 |
| Skipped | 0 |
| Errors | 0 |

---

## A. Passing features

These links are real for **BeagleBone Black `U2`**:

1. **BOM identity.** `product_id=beaglebone-black`, `reference_designator=U2`, `original_mpn=TPS65217C`, `component_model_id=mdl_48134fac2009`.
2. **Industry vs demo isolation.** Industry `U2` is `TPS65217C`. Demo catalog `U2` is `ESP32-WROOM-32U`. An industry request for `U2` never returns ESP32.
3. **Candidate pool isolation.** Industry generation source is `normalized_industry_models` (candidate `TPS65218D0RSLR`). Demo generation source is `deterministic_rules` (ESP32 / STM32 pool).
4. **Electrical specs reach the compatibility engine.** Names used by `compatibility_rules.regulator_checks`:
   - `input_voltage_min_v` = 2.7 V (aliased to `supply_voltage_min_v`)
   - `input_voltage_max_v` = 5.8 V (aliased to `supply_voltage_max_v`)
   - `output_current_a` = 1.2 A
   - `operating_temperature_max_c` = 105 C
   - `package` = `48-VQFN` via `ComponentSpec.package` / `get_spec("package")` (not an EAV row)
5. **Real engineering mismatch is visible.** Candidate `TPS65218D0RSLR` VIN max 5.5 V does not cover original 5.8 V → `MISMATCH` / `INCOMPATIBLE`. This gate was not weakened.
6. **Manufacturer rating is not an operating point.** Limit present, operating value missing → `INSUFFICIENT_DATA`, never `SAFE_MARGIN`.
7. **Empty vendor tables.** `evaluate_vendor_feasibility(TPS65217C)` → `INSUFFICIENT_DATA`. No fabricated 25000 stock, 6-week lead, 70% confidence, or `FEASIBLE`.
8. **UNKNOWN lifecycle stays unknown.** Model lifecycle `UNKNOWN`. Risk merge does not convert it to `ACTIVE`. Dashboard maps it to `INSUFFICIENT_DATA`.
9. **Frontend APIs keep identifiers.** Exercised in-process:
   - `GET /risk/projects` 200
   - `GET /risk/analyze?project=beaglebone_black` 200 — U2 `pn=TPS65217C`, `component_id=null` (no demo catalog id)
   - `GET /api/industry/boms` 200
   - `GET /api/industry/components?product_id=beaglebone-black` 200
   - `GET /api/industry/component/TPS65217C` 200 — model `mdl_48134fac2009`
   - `GET /api/vendor-feasibility?mpn=TPS65217C` → `INSUFFICIENT_DATA`
   - `GET /decision/beaglebone-black/U2` 200 — `product_id=beaglebone-black`, target `U2`, no ESP32
   - `GET /industry/beaglebone-black/U2/substitutes` — industry pool
   - `GET /components/U2/substitutes` — demo pool only
10. **BOM identity columns are no longer stored as electrical specs.** `Item` / `Embest P/N` / `Part Type` were removed from `component_specs.csv`.

---

## B. Partially working features

- **Component specifications coverage.** 8 engineering rows, 2 of 526 models (0.38%). Only the two PMICs (`TPS65217C`, `TPS65218D0`) feed `compatibility_rules.py` with electrical parameters. Every other industry model has identity only.
- **`output_voltage_v` and `pinout`.** Required by regulator checks; both `UNKNOWN` / `REVIEW_REQUIRED` because those EAV rows do not exist.
- **Duplicate BeagleBone Black `U2` BOM lines.** One line is `TPS65217C` / `mdl_48134fac2009`; another is `TPS65217CRSLR` / `mdl_957ebaaabb96` from a second source file. The resolver returns `TPS65217C`. Both rows are left as imported; designators were not invented or collapsed.
- **UI live click-through.** No browser automation was available in this environment. Honesty was verified from API payloads plus React source (`ComponentDetailPage`, `DashboardPage`, `ComponentTablePage`, `App.tsx`). Run the Vite app locally to confirm layout.
- **Industry `operating_limits.csv` / `tolerance_records.csv`.** Still contain manufacturer-limit-only rows for demo-catalog MPNs (`BSS138`, `2N3904`, …). They do **not** join to `TPS65217C`. They are not BeagleBone board operating points.

---

## C. Honest INSUFFICIENT_DATA features

Do not fill these in a demo. Show the label.

| Feature | Actual state |
|---|---|
| Vendor stock / lead / price / MOQ / authorized channel | Empty tables → `INSUFFICIENT_DATA` |
| Lifecycle | `UNKNOWN` → UI `INSUFFICIENT_DATA`, not `ACTIVE` |
| Second source | `null` → UI `INSUFFICIENT_DATA`, not `No` |
| Risk score / band for industry MPNs | `null` / `INSUFFICIENT_DATA` |
| Sparkline / factor bars / health gauge | Empty or `INSUFFICIENT_DATA` when band is insufficient |
| Board operating point for U2 | Missing → `INSUFFICIENT_DATA` (VIN 5.8 V is a datasheet rating) |
| Reliability / FIT / MTBF / degradation | Industry MPN does not consult the demo reliability catalog |
| Subsystems / redesign NRE | Empty |
| Provider enrichment | Not configured in this package; must not be simulated |

---

## D. Remaining pipeline bugs

After this validation pass:

- **No demonstrated join bug** on the BBB `U2` path (BOM → model → specs → compatibility → decision API → React routing).
- **Live UI was not clicked** in a browser here. Source now refuses to draw fabricated sparklines, factor bars, Active lifecycle, or numeric risk when the engine returned `INSUFFICIENT_DATA`.
- **Package is not in `component_specs.csv`.** It reaches the engine from `component_models.package` through `get_spec("package")`. That is documented, not a silent rename.

Do not treat empty vendor APIs as a pipeline bug.

---

## E. Remaining data gaps

- 524 / 526 industry models have no useful electrical EAV rows.
- No distributor feed (Nexar / DigiKey) is included; vendor tables have 0 rows.
- No lifecycle records.
- No board-level operating points for BeagleBone rails.
- TIDEP lines without a designator remain unresolved (not invented).
- TIDA archive has no BOM.
- `output_voltage_v` and `pinout` are absent for both PMICs.

---

## F. Exact demo flow to use

1. `python -m src.risk_api` (port 8001)
2. `python -m src.substitute_api` (port 8000)
3. `cd web && npm install && npm run dev`
4. BOM Upload → **Industry BOMs** → **Load BOM** on **BeagleBone Black**
5. Dashboard → Components → **U2 / TPS65217C** → Component Detail → Substitutes → Decision → Vendor → Evidence

Do **not** start from a demo sample project (`smart_cooling` / Mini Smart Cooling). That path is the synthetic catalog, including ESP32 as `U2`.

---

## G. Exact components that should be demonstrated

| Role | Value |
|---|---|
| Industry original | BeagleBone Black `U2` = `TPS65217C` (`mdl_48134fac2009`) |
| Industry candidate | `TPS65218D0RSLR` (`mdl_4ba7e403dcf9`) — show the VIN-max mismatch |
| Demo contrast only | Demo catalog `U2` = `ESP32-WROOM-32U` — never as an industry result |

Do not demo “full vendor feasibility” or “lifecycle Active” for this MPN.

---

## H. Known limitations that must not be hidden

- This is not a complete digital-thread product. It is a provenance-honest slice around one PMIC.
- `SAFE` / `PASS` / `SAFE_MARGIN` require a real operating point. A datasheet max is not one.
- `UNKNOWN` lifecycle is not `ACTIVE`.
- Missing second source is not `No`.
- Missing vendor evidence is not 25000 stock / 6 weeks / 70% confidence.
- Missing reliability is not measured FIT data.
- Synthetic demo catalog values must never be labeled `REAL_PUBLIC_SOURCE`.
- Compatibility score on `TPS65218D0RSLR` can still look “high” while VIN max is `INCOMPATIBLE`. Show the check list, not only the score.

---

## Spec classification (`component_specs.csv`)

| Class | Rows |
|---|---|
| A. Engineering electrical | 8 |
| B. Mechanical/package | 0 (package lives on `component_models`) |
| C. Identity/BOM metadata | 0 (removed; previously 321) |
| D. Other | 0 |
| **Total** | **8** |

Useful engineering models: **2 / 526 = 0.38%**

Parameters that actually reach `compatibility_rules.py` for this PMIC:

`input_voltage_min_v`, `input_voltage_max_v`, `output_current_a`, `operating_temperature_max_c`, `package` (via `get_spec`), plus documented aliases `supply_voltage_min_v` / `supply_voltage_max_v`.

`output_voltage_v` does not exist → `UNKNOWN`.

Parameter names were not renamed except the documented aliases in `src/industry_data/identity.py`.

---

## TPS65217C provenance chain

| Parameter | UI / API | Engine | CSV | Source |
|---|---|---|---|---|
| VIN min 2.7 V | `/api/industry/component/TPS65217C` technical_specs | `specs.input_voltage_min_v` | `spc_tps65217_dcdc3_vin_min` | TPS65217x SLVSB64I Rev. I p.10, electrical-characteristics table |
| VIN max 5.8 V | same | `specs.input_voltage_max_v` | `spc_tps65217_dcdc3_vin_max` | same, p.10 |
| Iout 1.2 A | same | `specs.output_current_a` | `spc_tps65217_dcdc3_iout` | same, p.10 |
| Tmax 105 C | same | `specs.operating_temperature_max_c` | `spc_tps65217_temp_max` | same, p.84 ordering table |
| Package 48-VQFN | model.package | `ComponentSpec.package` | `component_models.csv` `mdl_48134fac2009` | BOM-normalized package field |
| `output_voltage_v` | not displayed as a measured value | `null` / `UNKNOWN` | **no row** | **untraced — missing** |
| Lifecycle | `INSUFFICIENT_DATA` | `UNKNOWN` | empty `lifecycle_records.csv` | **untraced — missing** |
| Vendor stock | `INSUFFICIENT_DATA` | empty vendor tables | 0 rows | **untraced — missing** |

Electrical provenance is stored on the spec CSV columns (`source_document`, `source_page`, `provenance`). `field_provenance.csv` records BOM identity for `mdl_48134fac2009`, not the datasheet electrical cells.

---

## Engineering gates (repository data)

| Case | Result |
|---|---|
| Compatible quantities (VIN min, Iout, Tmax, package) vs `TPS65218D0RSLR` | `MATCH` |
| Incompatible VIN max 5.8 vs 5.5 | `MISMATCH` / `INCOMPATIBLE` |
| Missing `output_voltage_v` / `pinout` | `UNKNOWN` |
| Operating limit without operating value | `INSUFFICIENT_DATA` |
| Tolerance without bounds | `INSUFFICIENT_DATA` |
| A caller-supplied operating value (12 V vs 28 V) | function *can* return `SAFE_MARGIN` — those 12/28 numbers are **not** BeagleBone measurements |

---

## Final criterion

`REAL DATA → CORRECT JOIN → CORRECT ENGINE → CORRECT API → CORRECT UI → CORRECT EVIDENCE`

For TPS65217C electrical VIN / Iout / Tmax / package, this chain holds.

For vendor, lifecycle, operating point, reliability, and 524 other models, the honest result is `INSUFFICIENT_DATA`.

**Do not present this ZIP as an unrestricted industry demo.** Present BeagleBone Black `U2` and say what is missing.
