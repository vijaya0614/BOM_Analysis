# SENTINEL Risk Analysis Model

## Overview

The SENTINEL Risk Engine evaluates supply-chain vulnerability and technical criticality for electronic components using an explainable, multi-factor scoring model based on Analytic Hierarchy Process (AHP) weights and Weibull obsolescence modeling.

## Risk Factors & Scoring

Composite risk score $R \in [0.0, 1.0]$ is computed from five core dimensions:

1. **Lifecycle Risk**:
   - `Active` = 0.0, `NRND` / `LTB` = 0.6, `Obsolete` / `EOL` = 1.0.
   - Includes 5-year conditional Weibull obsolescence probability.
2. **Supply / Sourcing Risk**:
   - Dual/multi-sourced = 0.0, single-sourced = 1.0.
3. **Lead Time Risk**:
   - Normalized lead-time factor based on standard thresholds (26+ weeks = 1.0).
4. **Stock Level Risk**:
   - Inventory depth score derived from available distributor stock.
5. **Technical Criticality**:
   - Inferred or assigned component criticality (`Low`, `Medium`, `High`).

## Risk Bands & Classifications

- **CRITICAL**: Risk score $\ge 0.75$ or compounding override triggers (e.g. Obsolete + Single Source).
- **HIGH**: Risk score $\ge 0.55$.
- **MEDIUM**: Risk score $\ge 0.35$.
- **LOW**: Risk score $< 0.35$.

## Explainability & Data Confidence

- **Risk Reasons**: Every component risk assessment includes explicit human-readable trigger reasons.
- **Data Confidence Score**: Independent score $[0.0, 1.0]$ reflecting the proportion of verified vs inferred fields. Low data confidence does NOT artificially suppress high risk scores.
- **Evidence precedence**: Imported BOM provenance and real provider evidence are retained separately. Real distributor lifecycle, supply, and lead-time data take precedence when present; absent evidence remains unknown and is not replaced with invented supplier values.
