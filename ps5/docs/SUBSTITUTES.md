# SENTINEL Substitute Recommendation Engine

## Overview

The SENTINEL Substitute Engine recommends drop-in candidates and redesign alternatives for at-risk electronic components through a multi-stage evaluation pipeline combining hard engineering rules, parametric compatibility scoring, and supply-chain feasibility.

## Evaluation Pipeline

```
Candidate Selection (Same Category)
       ↓
Hard Constraint Evaluation (Package, Pin Count, Electrical Ratings)
       ↓
Parametric Compatibility Scoring (0–100)
       ↓
Evidence Confidence Scoring (0–100)
       ↓
Supply-Chain Feasibility Scoring
       ↓
Candidate Classification (DROP_IN, REQUIRES_REDESIGN, INCOMPATIBLE)
       ↓
Final Explanatory Ranking
```

## Hard Constraints & Immunity

- **Electrical Ratings**: Candidates operating outside required voltage or current limits are flagged as `INCOMPATIBLE`.
- **Physical Package & Footprint**: Incompatible pin counts or mismatched packages are flagged as `INCOMPATIBLE`.
- **Engineering Failure Priority**: Technical incompatibilities apply severe classification penalties (35 points) and **cannot** be overridden by strong supplier stock or low prices.
- **Ranking safety**: Results are ordered so compatible drop-in and redesign candidates appear before `INCOMPATIBLE` candidates. Incompatible candidates may still be shown for engineering review, but never lead the recommendation.

## Candidate Classifications

1. **`DROP_IN_CANDIDATE`**: Direct pin-to-pin, electrical, and package match requiring no PCB alterations.
2. **`REQUIRES_REDESIGN`**: Mechanically or electrically viable candidate requiring minor schematic, layout, or firmware modifications.
3. **`INCOMPATIBLE`**: Fails essential operating or physical constraints.

## Explainable Output

Every recommendation payload returns explicit matching parameters, mismatched parameters, unknown evidence parameters, reliability outlook comparisons, redesign cost estimates, and risk mitigation explanations.
