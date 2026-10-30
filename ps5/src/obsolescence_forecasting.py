"""Component Obsolescence Forecasting Engine.

Implements mathematical survival analysis using a 2-parameter Weibull model
and explainable heuristic fallbacks for 1-, 3-, and 5-year planning horizons.

Procurement obsolescence probability is strictly distinguished from physical
reliability and wear-out failure.

Formulas:
    S(t) = exp(-(t / eta)^beta)
    P(T <= t + Delta | T > t) = 1 - S(t + Delta) / S(t)
                              = 1 - exp((t / eta)^beta - ((t + Delta) / eta)^beta)
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# Prototype Weibull priors (shape beta, characteristic life eta in years).
# These defaults are not calibrated against a labeled lifecycle dataset.
WEIBULL_TECH_PARAMS: Dict[str, Tuple[float, float]] = {
    "microcontroller": (2.6, 11.0),
    "microprocessor": (2.8, 9.0),
    "memory": (2.7, 8.5),
    "power management": (2.2, 14.0),
    "regulator": (2.2, 14.0),
    "interface": (2.1, 13.5),
    "sensor": (2.0, 12.0),
    "discrete": (1.9, 18.0),
    "transistor": (1.9, 18.0),
    "diode": (1.8, 22.0),
    "passive": (1.7, 24.0),
    "resistor": (1.6, 25.0),
    "capacitor": (1.8, 20.0),
    "connector": (1.9, 15.0),
    "generic": (2.0, 15.0),
}
PARAMETER_CALIBRATION_STATUS = "ILLUSTRATIVE_UNVALIDATED_PRIORS"
RISK_TIER_THRESHOLDS = {"MODERATE_MIN": 0.15, "HIGH_MIN": 0.40, "CRITICAL_MIN": 0.70}
NRND_RISK_FLOORS = {1: 0.45, 3: 0.80, 5: 0.95}
MISSING_AGE_FRACTION_OF_ETA = 0.40
SECOND_SOURCE_RISK_MULTIPLIER_KNOWN_AGE = 1.25
SECOND_SOURCE_RISK_MULTIPLIER_HEURISTIC_AGE = 1.20


def get_weibull_params(category: Optional[str]) -> Tuple[float, float]:
    """Retrieve shape (beta) and scale (eta) for a component category."""
    cat = (category or "").strip().lower()
    for key, params in WEIBULL_TECH_PARAMS.items():
        if key in cat:
            return params
    return WEIBULL_TECH_PARAMS["generic"]


def weibull_survival(t: float, beta: float, eta: float) -> float:
    """Compute Weibull survival function S(t) = exp(-(t / eta)^beta)."""
    if t <= 0:
        return 1.0
    if eta <= 0:
        return 0.0
    return math.exp(-((t / eta) ** beta))


def conditional_unavailability_probability(
    current_age_years: float,
    horizon_years: float,
    beta: float,
    eta: float,
) -> float:
    """
    Compute conditional probability of obsolescence within horizon Delta given survival to t:
    P(T <= t + Delta | T > t) = 1 - S(t + Delta) / S(t)
    """
    if current_age_years < 0 or horizon_years <= 0:
        return 0.0
    s_t = weibull_survival(current_age_years, beta, eta)
    if s_t <= 1e-9:
        return 1.0
    s_t_plus_delta = weibull_survival(current_age_years + horizon_years, beta, eta)
    prob = 1.0 - (s_t_plus_delta / s_t)
    return max(0.0, min(1.0, prob))


def classify_risk_tier(probability: float) -> str:
    """Map probability to standardized explainable risk tiers."""
    if probability >= RISK_TIER_THRESHOLDS["CRITICAL_MIN"]:
        return "CRITICAL"
    if probability >= RISK_TIER_THRESHOLDS["HIGH_MIN"]:
        return "HIGH"
    if probability >= RISK_TIER_THRESHOLDS["MODERATE_MIN"]:
        return "MODERATE"
    return "LOW"


@dataclass
class HorizonForecast:
    horizon_years: int
    unavailability_probability: float
    risk_tier: str
    survival_fraction: float


@dataclass
class ComponentObsolescenceReport:
    part_number: str
    category: str
    lifecycle_status: str
    current_age_years: Optional[float]
    model_used: str  # "WEIBULL_SURVIVAL_MODEL" | "HEURISTIC_STATUS_BASED"
    weibull_beta: Optional[float]
    weibull_eta_years: Optional[float]
    horizons: Dict[str, HorizonForecast]
    contributing_factors: List[str]
    mitigation_recommendations: List[str]
    evidence_quality: str
    data_freshness_date: str
    assumptions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["horizons"] = {k: asdict(v) for k, v in self.horizons.items()}
        res["model_metadata"] = {
            "parameter_calibration_status": PARAMETER_CALIBRATION_STATUS,
            "risk_tier_thresholds": RISK_TIER_THRESHOLDS,
            "nrnd_probability_floors": NRND_RISK_FLOORS,
            "missing_age_fraction_of_eta": MISSING_AGE_FRACTION_OF_ETA,
            "second_source_multipliers": {
                "age_known": SECOND_SOURCE_RISK_MULTIPLIER_KNOWN_AGE,
                "age_heuristic": SECOND_SOURCE_RISK_MULTIPLIER_HEURISTIC_AGE,
            },
            "forecast_scope": "procurement unavailability, not physical component failure",
        }
        return res


def forecast_component_obsolescence(
    part_number: str,
    category: Optional[str] = None,
    lifecycle_status: Optional[str] = None,
    introduction_year: Optional[int] = None,
    estimated_age_years: Optional[float] = None,
    has_second_source: Optional[bool] = None,
    market_supplier_count: Optional[int] = None,
) -> ComponentObsolescenceReport:
    """
    Generate an obsolescence forecast across 1-, 3-, and 5-year planning horizons.
    Handles known ages via Weibull survival and provides transparent heuristic fallbacks
    when historical age is unrecorded.
    """
    status_clean = (lifecycle_status or "UNKNOWN").strip().upper()
    cat_clean = (category or "generic").strip()

    # Determine component age
    current_year = datetime.now().year
    age = estimated_age_years
    if age is None and introduction_year is not None:
        age = max(0.0, float(current_year - introduction_year))

    beta, eta = get_weibull_params(cat_clean)
    factors: List[str] = []
    mitigations: List[str] = []
    assumptions: List[str] = []

    horizons: Dict[str, HorizonForecast] = {}
    model_used = "WEIBULL_SURVIVAL_MODEL"
    evidence_quality = "HIGH" if age is not None and introduction_year is not None else "MEDIUM"

    if status_clean in {"EOL", "OBSOLETE", "DISCONTINUED"}:
        # Hard deterministic procurement obsolescence
        model_used = "STATUS_DETERMINISTIC"
        evidence_quality = "HIGH"
        factors.append(f"Component is officially designated as {status_clean} by manufacturer.")
        mitigations.append("Immediate Last-Time Buy (LTB) buffer calculation.")
        mitigations.append("Screen drop-in pin-compatible replacements.")
        mitigations.append("Initiate redesign feasibility review.")
        for h in (1, 3, 5):
            prob = 1.0 if h >= 1 else 0.95
            horizons[f"{h}_year"] = HorizonForecast(
                horizon_years=h,
                unavailability_probability=prob,
                risk_tier=classify_risk_tier(prob),
                survival_fraction=0.0,
            )
        assumptions.append("Discontinued components face near-zero future production replenishment.")

    elif status_clean in {"NRND", "NOT_RECOMMENDED"}:
        # Not Recommended for New Designs: Weibull shifted or accelerated
        factors.append("Manufacturer marked part as Not Recommended for New Designs (NRND).")
        effective_age = age if age is not None else (eta * 0.85)
        assumptions.append(f"NRND indicates part is in late maturity (effective age modeled at {effective_age:.1f} yr).")
        mitigations.append("Qualify an active second source before formal EOL announcement.")
        mitigations.append("Audit annual production usage against remaining distributor inventory.")

        for h in (1, 3, 5):
            base_p = conditional_unavailability_probability(effective_age, float(h), beta, eta)
            # NRND floor assumptions are explicit and returned in model_metadata.
            p = max(base_p, NRND_RISK_FLOORS[h])
            surv = max(0.0, 1.0 - p)
            horizons[f"{h}_year"] = HorizonForecast(
                horizon_years=h,
                unavailability_probability=round(p, 4),
                risk_tier=classify_risk_tier(p),
                survival_fraction=round(surv, 4),
            )

    elif age is not None:
        # Full Weibull model with known age
        model_used = "WEIBULL_SURVIVAL_MODEL"
        factors.append(f"Active part with recorded technology age of {age:.1f} years.")
        factors.append(f"Category '{cat_clean}' modeled with Weibull beta={beta:.2f}, eta={eta:.1f} yr.")
        assumptions.append("Survival model represents procurement availability over time, not physical semiconductor wearout.")

        for h in (1, 3, 5):
            p = conditional_unavailability_probability(age, float(h), beta, eta)
            if has_second_source is False:
                # Lack of second source amplifies procurement risk
                p = min(1.0, p * SECOND_SOURCE_RISK_MULTIPLIER_KNOWN_AGE)
            surv = max(0.0, 1.0 - p)
            horizons[f"{h}_year"] = HorizonForecast(
                horizon_years=h,
                unavailability_probability=round(p, 4),
                risk_tier=classify_risk_tier(p),
                survival_fraction=round(surv, 4),
            )
        if horizons["5_year"].unavailability_probability >= 0.40:
            mitigations.append("Identify drop-in second source to hedge 5-year availability exposure.")
    else:
        # Heuristic fallback for sparse records
        model_used = "HEURISTIC_STATUS_BASED"
        evidence_quality = "ESTIMATED_HEURISTIC"
        assumptions.append("Component age unrecorded; applying baseline category survival estimates.")
        nominal_age = eta * MISSING_AGE_FRACTION_OF_ETA

        for h in (1, 3, 5):
            p = conditional_unavailability_probability(nominal_age, float(h), beta, eta)
            if has_second_source is False:
                p = min(1.0, p * SECOND_SOURCE_RISK_MULTIPLIER_HEURISTIC_AGE)
            horizons[f"{h}_year"] = HorizonForecast(
                horizon_years=h,
                unavailability_probability=round(p, 4),
                risk_tier=classify_risk_tier(p),
                survival_fraction=round(1.0 - p, 4),
            )

    if has_second_source is False:
        factors.append("Single-source component with no independently verified second source.")
        mitigations.append("Seek pin-compatible second source to remove sole-source vulnerability.")
    elif has_second_source is True:
        factors.append("Dual-sourced component with confirmed secondary supplier.")

    return ComponentObsolescenceReport(
        part_number=part_number,
        category=cat_clean,
        lifecycle_status=status_clean,
        current_age_years=round(age, 1) if age is not None else None,
        model_used=model_used,
        weibull_beta=beta,
        weibull_eta_years=eta,
        horizons=horizons,
        contributing_factors=factors,
        mitigation_recommendations=mitigations,
        evidence_quality=evidence_quality,
        data_freshness_date=datetime.now().strftime("%Y-%m-%d"),
        assumptions=assumptions,
    )
