# PS5 — BOM Risk Analysis & Component Substitution Platform
## Verification & Demonstration Walkthrough

This document guides you through the end-to-end verification and expo demonstration of the **PS5 BOM Risk Analysis and Intelligent Component Substitution Platform**.

---

## 1. System Verification Summary

| Component | Status | Test / Verification Command | Result |
|---|---|---|---|
| **Engineering Calculation Modules** | COMPLETED | `python -m pytest tests/test_ps5_engineering_modules.py` | 17/17 Passed (0.7s) |
| **Unified API Endpoints** | COMPLETED | `python -m pytest tests/test_ps5_api_endpoints.py` | 15/15 Passed (2.0s) |
| **Comprehensive Regression Suite** | COMPLETED | `python -m pytest tests/` | 204/204 Passed (22.3s) |
| **Alembic Database Migration** | COMPLETED | `python -m alembic upgrade head` | Head `f44764334dbb` Applied |
| **Frontend Production Build** | COMPLETED | `cd web && npm run build` | Clean `dist/` Generated (0 Errors) |
| **Frontend Code Quality** | COMPLETED | `cd web && npm run lint` | 0 Errors across 35 files |
| **UI Theme & Layout Preservation** | COMPLETED | Visual & CSS Variable Audit | 100% Preserved |

---

## 2. 10-Step Realistic Expo Demonstration Flow

Follow these exact steps to demonstrate all capabilities required by **Part 15** of the specification:

### Step 1: Upload or Load Synthetic BOM (Part 4)
- Navigate to **BOM Upload** (`/upload`).
- Click **Download CSV Template** to demonstrate the downloadable engineering CSV format with all required columns (MPN, Description, Category, Qty, Unit Cost, Available Stock, Lead Time, Voltage Max, Package).
- Click **Load Realistic 15-Part BOM**. The system ingests 15 realistic components including active, NRND, and EOL parts (e.g., `TPS5402DGQR`, `TPS65217C`, `STM32F407VGT6`, `TPS65218D0RSLR`).

### Step 2: Identify an EOL or NRND Component (Part 4 & 5)
- Open the **Dashboard** (`/dashboard`).
- View the **Product-Level Risk Aggregation** card (Part 13) displaying Single Points of Failure (SPOF count: 2), unhedged lines, and estimated financial disruption exposure ($162,000).
- Locate the critical power regulator **TPS5402DGQR** or **TPS65217C**.

### Step 3: Inspect Obsolescence Survival & Horizon Forecasting (Part 5)
- Click into the component to open **Component Detail** (`/detail`).
- Review the **Weibull Obsolescence Survival** card:
  - 1-Year Unavailability: $P_{1y}$
  - 3-Year Unavailability: $P_{3y}$
  - 5-Year Unavailability: $P_{5y}$
  - Parameters: $\beta = 2.8$, $\eta = 10.5$ years.
  - Interactive 10-year Weibull survival curve $S(t) = \exp[-(t/\eta)^\beta]$.
  - Recommended mitigation action.

### Step 4: Inspect Market Supply Pressure & Tolerances (Part 6)
- Review the **Market Supply Risk** card:
  - Inventory coverage in weeks: $\text{Available Usable Stock} / \text{Weekly Demand}$.
  - Lead-time margin: Procurement Window vs Lead Time (+/- weeks).
  - Supplier Concentration HHI ($\sum s_i^2$).
  - Supply Pressure Index (SPI: 0–100 score).
  - Configured availability tolerance checklist with `PASS`, `FAIL`, and `UNKNOWN` badges.

### Step 5: Mission Profile & Operating Conditions (Part 9)
- Review the **Mission Profile Analysis** card:
  - Operating phases: Normal Load (45°C ambient, 4000h) and Peak Load (65°C ambient, 1000h).
  - Component thermal rise: $\Delta T = P \cdot R_\theta$.
  - Peak junction temperature: $T_j = T_a + \Delta T$.
  - Arrhenius acceleration factor: $AF = \exp[(E_a/k)(1/T_{use} - 1/T_{ref})]$.
  - Annual cumulative damage $D$ using Miner's rule.
  - Side-by-side trade-offs: Baseline vs. Improved Cooling (35% $R_\theta$ reduction) vs. Electrical Derating (25% power reduction).

### Step 6: Electrical Tolerance & Monte Carlo Simulation (Part 8)
- Review the **Electrical Tolerance & Monte Carlo** card:
  - Worst-Case Circuit Analysis (WCCA) Min, Nominal, Max output limits.
  - Root-Sum-Square (RSS) statistical tolerance ($\sigma_y \approx \sqrt{\sum (\partial f/\partial x_i \cdot \sigma_i)^2}$).
  - 15-bin Monte Carlo distribution histogram ($N = 1000$ trials, seed `#42`) showing exact violation rates.
  - Circuit parameter sensitivity ranking (identifying top contributors to output drift).

### Step 7: Form-Fit-Function & Hard Gate Substitute Screening (Part 7 & 10)
- In the **Substitutes** carousel and hard gates evaluation:
  - Observe how candidate parts failing mounting type (SMD vs THT) or exceeding package height clearance are classified as `INCOMPATIBLE` and eliminated before ranking.
  - Candidates requiring layout adjustments are tagged as `REQUIRES_REDESIGN` (Conditional).
  - Clean candidates with matching pin count, pitch, and voltage headroom are tagged as `DROP_IN_CANDIDATE`.

### Step 8: Component FMEA & Action Priority (Part 11)
- Review the **Component FMEA** table:
  - Failure modes (Thermal degradation, Overvoltage breakdown, Open-circuit, Parameter drift).
  - Severity (S), Occurrence (O), and Detection (D) scoring.
  - Risk Priority Number ($\text{RPN} = S \times O \times D$).
  - Action Priority (`HIGH`, `MEDIUM`, `LOW`) and recommended prevention/detection controls.
  - Residual RPN after mitigation.

### Step 9: 4-Strategy Lifecycle Economics (Part 12)
- Click **View Decision** (`/decision`) to view the engineering decision and economics:
  - Strategy A: Continue using current component & monitor.
  - Strategy B: Purchase and hold inventory in advance (Last-Time Buy).
  - Strategy C: Qualify and use an alternative component.
  - Strategy D: Redesign affected subsystem.
  - Live cost breakdown: Parts cost, NRE / qualification, inventory holding, disruption risk.
  - Net savings ($) and break-even production volume (units).

### Step 10: Interactive What-If Scenario Sandbox (Part 14)
- Adjust the sliders in the **What-If Scenario Sandbox**:
  - Increase ambient temperature from 25°C to 70°C.
  - Adjust cooling thermal resistance $R_\theta$ from 42 °C/W down to 25 °C/W.
  - Adjust production volume.
  - Observe immediate differential updates: thermal margin delta (°C), SPI delta, life consumption delta (%), and net lifecycle cost delta ($).

### Step 11: Inspect Vendor Ecosystem, Geological Availability & Market Saturation (Part 19)
- On the Component Detail page (`/detail`):
  - **Distributor Stock Donut Chart**: Hover over the interactive Recharts Donut Chart to see stock quantities and market shares across 6 authorized distributors (Digi-Key, Mouser, Arrow, Avnet, Farnell, LCSC).
  - **Geological Availability & Fab Hazard**: Inspect the primary silicon wafer fabrication facility (e.g. Sherman TX, Crolles France, Hsinchu Taiwan), secondary assembly site, natural hazard meters (seismic risk score, water stress, tsunami zone), and rare-earth dependence rating.
  - **12-Month Historical Volatility Trends**: Review dual interactive charts tracking 12-month unit price ($) contract vs spot trends and procurement lead time (weeks) vs target thresholds.
  - **6-Factor Resilience Radar Chart**: Inspect the multi-disciplinary radar chart evaluating Sourcing Security, Lead Time Resilience, Price Stability, Lifecycle Longevity, Geopolitical Safety, and Geological Hardiness.
  - **Visual Lifecycle & Obsolescence Horizon**: Review the visual progression track showing milestone transitions (Introduction -> Volume Maturity -> NRND Notice -> LTB Date -> EOL) with explicit LTB purchase deadline alerts.

### Export Audit Report (Part 15)
- Open **Reports** (`/report`).
- Click **PS5 Full Audit** to download the comprehensive JSON engineering audit report containing all mathematical model results, assumptions, and validation metrics.

