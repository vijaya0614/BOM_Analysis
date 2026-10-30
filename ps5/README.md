# PS5 — BOM Risk Analysis & Intelligent Component Substitution Platform

An expo-ready electronics reliability engineering prototype that combines component obsolescence forecasting, supply-chain pressure analysis, mission profile thermal life consumption, electrical/physical tolerance checks, failure modes (FMEA), and lifecycle economics into a unified, explainable decision-support platform.

---

## 1. System Architecture & Engineering Principles

PS5 operates on a hard-gate-first philosophy: a substitute with available stock or low price is never deemed viable if it violates physical, electrical, or thermal operating boundaries.

```
BOM Ingestion & Validation
   ↓
Weibull Obsolescence Survival & Horizon Forecasting (1y, 3y, 5y)
   ↓
Market Supply Risk (Inventory Coverage, Lead-Time Margin, HHI, SPI)
   ↓
Mission Profile Stress & Thermal Life (ΔT = P·R_θ, Arrhenius AF, Miner's Rule D)
   ↓
Physical Compatibility & Hard Gates (Drop-in vs Redesign vs Incompatible)
   ↓
Electrical Compatibility & Tolerance (WCCA, RSS σ, Monte Carlo Histogram)
   ↓
Component & Subsystem FMEA (Severity, Occurrence, Detection, RPN, Action Priority)
   ↓
4-Strategy Lifecycle Economics (Continue, Last-Time Buy, Substitute, Redesign)
   ↓
Product-Level Risk Posture (SPOF, Unhedged Lines, Disruption Exposure $)
   ↓
Interactive What-If Scenario Sandbox & Exportable Audit Report
```

---

## 2. Mathematical Models & Formulas Implemented

### 2.1 Obsolescence Survival (Weibull Distribution)
- **Survival Function**:
  $$S(t) = \exp\left[-\left(\frac{t}{\eta}\right)^\beta\right]$$
  where $\beta$ is the shape parameter and $\eta$ is the characteristic scale in years. This models procurement unavailability, not physical wear-out. Category parameters are illustrative priors and have not been calibrated against a labeled lifecycle dataset.
- **Conditional Unavailability Probability** over horizon $\Delta \in \{1, 3, 5\}$ years given current component age $t$:
  $$P(T \le t + \Delta \mid T > t) = 1 - \frac{S(t + \Delta)}{S(t)}$$
- Categorized with code-aligned thresholds: `LOW` (< 15%), `MODERATE` (15%–< 40%), `HIGH` (40%–< 70%), and `CRITICAL` (≥ 70%). NRND probability floors are 45%, 80%, and 95% at 1, 3, and 5 years. When age is missing, the fallback assumes 40% of category $\eta$; these priors are not outcome-calibrated.

### 2.2 Market Supply Risk & Supply Pressure Index (SPI)
- **Inventory Coverage**:
  $$\text{Coverage (weeks)} = \frac{\text{Available Usable Stock}}{\text{Weekly Demand}}$$
- **Lead-Time Margin**:
  $$\text{Margin (weeks)} = \text{Available Procurement Window} - \text{Estimated Lead Time}$$
- **Supplier Concentration (Herfindahl-Hirschman Index)**:
  $$\text{HHI} = \sum_{i} s_i^2 \quad (s_i \in [0, 1])$$
- **Supply Pressure Index (SPI, 0–100)**:
  $$\text{SPI} = 100 \sum_{i} w_i x_i$$
  with code weights: stock coverage 25%, lead time 20%, allocation/backorder 15%, supplier concentration 15%, price change 10%, and lifecycle 15%. Tiers: `LOW` (< 25), `MODERATE` (25–< 50), `HIGH` (50–< 75), `CRITICAL` (≥ 75). Missing stock, lead time, concentration, and lifecycle use neutral risk proxies of 0.50; missing price change uses 0.20. If supplier shares/count are absent, HHI is unknown rather than assuming a sole source; its SPI proxy is 0.50. These are heuristic scores, not calibrated probabilities.

### 2.3 Thermal & Mission Profile Life Consumption
- **Component Temperature Rise**:
  $$\Delta T = P \cdot R_\theta, \quad T_j \approx T_{ambient} + \Delta T$$
- **Arrhenius Acceleration Factor ($AF$)**:
  $$AF = \exp\left[\frac{E_a}{k}\left(\frac{1}{T_{ref}} - \frac{1}{T_{use}}\right)\right]$$
  with Boltzmann constant $k = 8.617 \times 10^{-5}\text{ eV/K}$, activation energy $E_a = 0.70\text{ eV}$, and temperatures in Kelvin ($T_K = T_C + 273.15$).
  The API defaults to a 40 °C reference, 100,000 reference life hours, 125 °C rated maximum, 42 °C/W junction-to-ambient thermal resistance, and a 10-year target; these are assumptions unless replaced with component-specific qualified data. If no phases are supplied, it evaluates the `High-Temperature Industrial Enclosure` profile.
- **Linear Damage Accumulation (Miner's Rule)**:
  $$D = \sum_{j} \frac{\Delta t_j}{L_j}$$
  where $\Delta t_j$ is operating hours in phase $j$ and $L_j = \frac{L_{rated}}{AF_j}$.
- **Side-by-Side Mitigations**: Evaluates baseline vs. improved cooling (35% $R_\theta$ reduction) vs. electrical derating (25% power reduction).

### 2.4 Electrical Tolerance & Monte Carlo Simulation
- **Worst-Case Circuit Analysis (WCCA)**:
  Evaluates circuit output $V_{out} = V_{ref} (1 + R_1 / R_2)$ at parameter boundary extremes ($\pm \text{tolerance}$).
- **Root-Sum-Square (RSS) Statistical Tolerance**:
  $$\sigma_y \approx \sqrt{\sum_i \left(\frac{\partial f}{\partial x_i} \cdot \sigma_i\right)^2}$$
- **Monte Carlo Simulation**:
  Deterministic seed (`42`), configurable trials ($N = 2000$ default), generates a 15-bin distribution histogram and boundary violation rate. Normal tolerance treats the tolerance interval as ±3σ; uniform tolerance uses the same min/max interval.
- **Sensitivity Ranking**:
  Parameters are ranked by their contribution to output variance:
  $$S_i = \frac{(\partial f / \partial x_i \cdot \sigma_i)^2}{\sum_k (\partial f / \partial x_k \cdot \sigma_k)^2} \times 100\%$$

### 2.5 Failure Mode and Effects Analysis (FMEA)
- Traditional Risk Priority Number:
  $$\text{RPN} = S \times O \times D \quad (S, O, D \in [1, 10])$$
- Action Priority (AP): `HIGH` when severity ≥ 9, or severity ≥ 7 and occurrence ≥ 5, or RPN ≥ 150; otherwise `MEDIUM` when severity ≥ 5, occurrence ≥ 5, or RPN ≥ 75; else `LOW`. The UI colors RPN by AP. This category-template assessment is heuristic and not calibrated against field failures.
- Models residual RPN after prevention and detection mitigations.

### 2.6 Lifecycle Economics (4 Strategies)
- Strategy A: Continue using current component & monitor.
- Strategy B: Purchase and hold inventory in advance (Last-Time Buy).
- Strategy C: Qualify and use an alternative component.
- Strategy D: Redesign affected subsystem.
- Total cost equation:
  $$C_{total} = C_{parts} + C_{redesign} + C_{qualification} + C_{inventory} + C_{delay} + C_{disruption}$$
- Net savings & savings percentage:
  $$\text{Net Savings} = C_{baseline} - C_{alternative}, \quad \text{Savings \%} = 100 \times \frac{C_{baseline} - C_{alternative}}{C_{baseline}}$$
- Break-even volume calculation for substitute qualification amortization:
  $$V_{break\_even} = \frac{C_{qual\_nre}}{P_{orig} - P_{sub}}$$

---

## 3. Setup and Execution

The application uses one backend: the unified FastAPI service at `src.api.main:app` on port `8000`. The Vite development server and the Docker Nginx frontend proxy all API requests to that service.

### 3.1 Local Development

In PowerShell, install the backend dependencies and run the migration from the `ps5` directory:

```powershell
cd ps5
python -m pip install -r requirements.txt
python -m alembic upgrade head
```

The default install covers the unified API, migrations, and local substitution paths. To enable optional semantic retrieval with sentence-transformers and Pinecone, install `requirements-optional-search.txt` as well.

While rotating previously exposed provider credentials, start the API with provider `.env` loading disabled:

```powershell
$env:PS5_DISABLE_PROVIDER_DOTENV = "1"
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```

After replacing the exposed credentials in `ps5/.env`, remove the `PS5_DISABLE_PROVIDER_DOTENV` override to enable provider integrations.

In a second terminal, start the frontend:

```powershell
cd ps5/web
npm ci
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`. Vite forwards `/api`, `/risk`, `/components`, `/industry`, `/substitutes`, `/decision`, `/evidence`, and `/risk-report` to the API on port `8000`.

### 3.2 Docker Compose

From the repository root, build and start the unified API and frontend:

```powershell
docker compose up --build
```

Open `http://127.0.0.1:5173`. The API is also available at `http://127.0.0.1:8000`. Stop the services with `docker compose down`.

### 3.3 Free Render Demo Deployment

The repository includes a single-container deployment: the Docker image builds the React frontend, serves it from the unified FastAPI service, runs database migrations, and listens on Render's port 10000. This keeps browser API calls same-origin and uses no provider credentials by default.

1. Push this project to a GitHub repository you control. Do not include `.env`, local databases, or credential archives.
2. In Render, choose **New → Blueprint**, connect that repository, and select the `ps5/render.yaml` file if prompted. Review the Blueprint; it creates one free web service named `ps5-bom-demo`.
3. Deploy and wait for the `/health` check to pass. Render will show the public `onrender.com` URL.

This app intentionally has no sign-in, so anyone with the public URL can use its API and upload endpoint. Share it only as a demo and do not upload confidential BOMs. Free Render services sleep after 15 minutes without traffic, may take about a minute to wake, and lose runtime filesystem changes on sleep/redeploy; uploaded or imported data is temporary. Provider integrations remain unconfigured unless separately supplied as server-side Render environment secrets.

To check the same container locally before pushing:

```powershell
docker build -t ps5-bom-demo .
docker run --rm -p 10000:10000 ps5-bom-demo
```

Open `http://localhost:10000`; verify `/health` returns `status: ok`.

### 3.4 Running Tests
```bash
# Run the backend test suite
python -m pytest tests/

# Run frontend production build & linter
cd web
npm run build
npm run lint
```

---

## 4. Key Endpoints Exposed by Unified API (`:8000`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | System and database health status |
| `/metrics` | GET | Prometheus plaintext metrics |
| `/api/bom/template` | GET | Official CSV BOM schema template download |
| `/api/bom/synthetic` | GET | Realistic 15-part prototype BOM with real datasheets |
| `/api/bom/validate` | POST | Row-level CSV validation with unit and schema checks |
| `/api/obsolescence/forecast` | POST | Weibull survival & 1y/3y/5y horizon forecasting |
| `/api/market/supply-pressure` | POST | Inventory coverage, lead-time margin, HHI, and SPI |
| `/api/physical/compatibility` | POST | Dimensional compatibility & form-fit-function gating |
| `/api/tolerances/analyze` | POST | WCCA, RSS statistical tolerance, and Monte Carlo histogram |
| `/api/mission-profile/evaluate` | POST | Thermal rise, Arrhenius acceleration, Miner's rule damage |
| `/api/substitutes/evaluate-gates` | POST | Hard-gate-first candidate filtering and ranking |
| `/api/fmea/analyze` | POST | Suggested failure modes, S/O/D ratings, RPN, Action Priority |
| `/api/cost/scenarios` | POST | 4-strategy economic comparison and break-even volume |
| `/api/product/risk-summary` | POST | Product-level SPOF, unhedged lines, disruption exposure |
| `/api/scenarios/compare` | POST | Side-by-side what-if parameter delta analysis |
| `/api/reports/full-engineering-audit` | GET | Comprehensive exportable JSON engineering audit report |

---

## 5. Engineering Integrity & Data Provenance Rules

1. **No Synthetic Facts**: Synthetic supplier prices, inventory counts, and lead-time observations are never presented as live distributor facts. All synthetic records carry explicit provenance markers (`SYNTHETIC DEMO DATA`).
2. **Deterministic Reproducibility**: Monte Carlo simulations and random generators use deterministic seeds (`seed=42`) so test runs and UI demonstrations are reproducible.
3. **Hard Gates vs Ranking**: Incompatible physical packages or electrical violations are rejected at the gate rather than blended into a weighted average score.
4. **Drop-in Evidence Gate**: A drop-in requires traceable package, pinout, and applicable rating evidence for both parts. Missing or unreferenced values remain `INSUFFICIENT_DATA` and are not promoted to a pass.
5. **Thermal Model Validity**: $\Delta T = P \cdot R_\theta$ is documented as a 1D junction-to-ambient thermal resistance model and requires CFD/thermocouple physical measurement for dense PCB layouts.
6. **BOM Risk Bands**: `LOW` < 0.30, `MEDIUM` ≥ 0.30, `HIGH` ≥ 0.60, and `CRITICAL` ≥ 0.85 on the normalized 0–1 score. The UI uses the same boundaries. Fuzzy AHP weights are expert-judgment priors, not outcome-calibrated probabilities.

## 6. API Access and Request Limits

The unified demo API does not require sign-in or user credentials. CORS accepts only configured explicit origins, and requests are limited to 70 MiB; industry uploads have a 50 MiB decoded-file limit. Because routes are unauthenticated, run the demo on a trusted local/private network and do not expose the API directly to the public internet.

## 7. Data Ownership and Freshness

The normalized industry CSV catalog is the current source of truth for imported BOM and evidence data; the SQL database is reserved for transactional workflow state and is not currently authoritative for the industry catalog. Distributor offers expire after 24 hours, lifecycle evidence is reviewed after 180 days, unresolved or undated evidence is withheld from numeric/current overlays, and reports expose excluded records and conflicts. See [DATA_GOVERNANCE.md](DATA_GOVERNANCE.md) for storage ownership, update behavior, revision selection, and status definitions.

## 8. Demo Archive Contents

Create the demo package with `python scripts/package_demo_zip.py`. It collects the runtime source, docs, tests, and demo datasets while omitting local environments and credentials, caches, raw and extracted source packages, SQLite databases, generated analysis outputs, build products, and API response logs. Packaging scans candidate file contents for common credential signatures and verifies required files after extraction before replacing the release ZIP.
