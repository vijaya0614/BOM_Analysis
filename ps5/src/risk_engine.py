"""Hybrid BOM risk engine: Fuzzy AHP weights plus Weibull 5-year obsolescence."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from src.models import PartRiskProfile

TFN = Tuple[float, float, float]
CRITERIA = (
    "obsolescence",
    "second_source",
    "lead_time",
    "stock",
    "criticality",
)
HORIZON_YEARS = 5.0

# Linguistic triangular fuzzy scale (l, m, u) for Fuzzy AHP pairwise judgments.
_EQUAL: TFN = (1.0, 1.0, 1.0)
_EQ_MOD: TFN = (1.0, 2.0, 3.0)
_MODERATE: TFN = (2.0, 3.0, 4.0)
_MOD_STRONG: TFN = (3.0, 4.0, 5.0)
_STRONG: TFN = (4.0, 5.0, 6.0)
_VERY_STRONG: TFN = (6.0, 7.0, 8.0)


def _tfn_mul(a: TFN, b: TFN) -> TFN:
    return (a[0] * b[0], a[1] * b[1], a[2] * b[2])


def _tfn_inv(a: TFN) -> TFN:
    return (1.0 / a[2], 1.0 / a[1], 1.0 / a[0])


def _tfn_pow(a: TFN, power: float) -> TFN:
    return (a[0] ** power, a[1] ** power, a[2] ** power)


def _tfn_sum(values: Sequence[TFN]) -> TFN:
    return (
        sum(item[0] for item in values),
        sum(item[1] for item in values),
        sum(item[2] for item in values),
    )


def _defuzzify(a: TFN) -> float:
    return (a[0] + a[1] + a[2]) / 3.0


def build_fuzzy_pairwise_matrix() -> List[List[TFN]]:
    """
    Expert pairwise TFNs. Rank order matches the former static model:
    obsolescence > second-source > lead time > stock > criticality.
    """
    upper = {
        (0, 1): _EQ_MOD,
        (0, 2): _MODERATE,
        (0, 3): _MOD_STRONG,
        (0, 4): _VERY_STRONG,
        (1, 2): _EQ_MOD,
        (1, 3): _MODERATE,
        (1, 4): _STRONG,
        (2, 3): _EQ_MOD,
        (2, 4): _STRONG,
        (3, 4): _MODERATE,
    }
    n = len(CRITERIA)
    matrix = [[_EQUAL for _ in range(n)] for _ in range(n)]
    for (i, j), value in upper.items():
        matrix[i][j] = value
        matrix[j][i] = _tfn_inv(value)
    return matrix


def fuzzy_ahp_weights(matrix: Optional[List[List[TFN]]] = None) -> Dict[str, float]:
    """
    Buckley geometric-mean Fuzzy AHP. Returns crisp, normalized criterion weights.
    """
    pairwise = matrix or build_fuzzy_pairwise_matrix()
    n = len(pairwise)
    row_means = []
    for row in pairwise:
        product = (1.0, 1.0, 1.0)
        for cell in row:
            product = _tfn_mul(product, cell)
        row_means.append(_tfn_pow(product, 1.0 / n))

    total = _tfn_sum(row_means)
    inv_total = _tfn_inv(total)
    fuzzy_weights = [_tfn_mul(mean, inv_total) for mean in row_means]
    crisp = [_defuzzify(weight) for weight in fuzzy_weights]
    denom = sum(crisp) or 1.0
    return {name: value / denom for name, value in zip(CRITERIA, crisp)}


AHP_WEIGHTS: Dict[str, float] = fuzzy_ahp_weights()


@dataclass
class HistoricalPartData:
    """Observed production age and/or peer EOL ages used to fit Weibull parameters."""

    years_in_production: Optional[float] = None
    observed_obsolescence_ages: List[float] = field(default_factory=list)
    weibull_shape: Optional[float] = None
    weibull_scale: Optional[float] = None
    category: Optional[str] = None

    @classmethod
    def from_mapping(cls, data: Optional[Mapping[str, Any]]) -> Optional["HistoricalPartData"]:
        if data is None:
            return None
        if isinstance(data, HistoricalPartData):
            return data
        ages = data.get("observed_obsolescence_ages") or data.get("eol_ages") or []
        return cls(
            years_in_production=data.get("years_in_production", data.get("age_years")),
            observed_obsolescence_ages=[float(age) for age in ages],
            weibull_shape=data.get("weibull_shape", data.get("shape")),
            weibull_scale=data.get("weibull_scale", data.get("scale")),
            category=data.get("category"),
        )


# Lifecycle-conditioned Weibull priors (shape β, scale η in years, current age t0).
_WEIBULL_PRIORS = {
    "Active": {"shape": 2.4, "scale": 16.0, "age": 2.0},
    "NRND": {"shape": 2.2, "scale": 7.0, "age": 5.0},
    "Obsolete": {"shape": 1.8, "scale": 4.0, "age": 12.0},
}
_WEIBULL_UNKNOWN = {"shape": 2.0, "scale": 10.0, "age": 4.0}


def _median_ranks(n: int) -> List[float]:
    return [(i - 0.3) / (n + 0.4) for i in range(1, n + 1)]


def fit_weibull_from_ages(ages: Sequence[float]) -> Tuple[float, float]:
    """Least-squares Weibull fit on median-rank plotting paper: ln(-ln(1-F)) vs ln(t)."""
    samples = sorted(age for age in ages if age and age > 0)
    if len(samples) < 2:
        raise ValueError("At least two positive obsolescence ages are required to fit Weibull.")

    ranks = _median_ranks(len(samples))
    xs = [math.log(age) for age in samples]
    ys = [math.log(-math.log(1.0 - rank)) for rank in ranks]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x <= 1e-12:
        return 2.2, float(samples[-1])
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / var_x
    intercept = mean_y - slope * mean_x
    shape = min(6.0, max(0.8, slope))
    scale = math.exp(-intercept / shape)
    scale = min(40.0, max(1.0, scale))
    return shape, scale


def weibull_conditional_probability(
    age_years: float,
    horizon_years: float,
    shape: float,
    scale: float,
) -> float:
    """
    P(obsolescence by age+horizon | survived to age) for Weibull(shape, scale).
    1 - S(t0+T) / S(t0) = 1 - exp(-((t0+T)/η)^β + (t0/η)^β)
    """
    if scale <= 0 or shape <= 0:
        raise ValueError("Weibull shape and scale must be positive.")
    t0 = max(0.0, float(age_years))
    horizon = max(0.0, float(horizon_years))
    cumulative_now = (t0 / scale) ** shape
    cumulative_future = ((t0 + horizon) / scale) ** shape
    probability = 1.0 - math.exp(-(cumulative_future - cumulative_now))
    return min(1.0, max(0.0, probability))


def _resolve_weibull_params(
    lifecycle_status: Optional[str],
    historical: Optional[HistoricalPartData],
) -> Tuple[float, float, float]:
    prior = _WEIBULL_PRIORS.get(lifecycle_status or "", _WEIBULL_UNKNOWN)
    shape = prior["shape"]
    scale = prior["scale"]
    age = prior["age"]

    if historical is not None:
        if historical.observed_obsolescence_ages and len(historical.observed_obsolescence_ages) >= 2:
            shape, scale = fit_weibull_from_ages(historical.observed_obsolescence_ages)
        if historical.weibull_shape:
            shape = float(historical.weibull_shape)
        if historical.weibull_scale:
            scale = float(historical.weibull_scale)
        if historical.years_in_production is not None:
            age = float(historical.years_in_production)
    return shape, scale, age


def weibull_obsolescence_probability(
    lifecycle_status: Optional[str],
    historical_part_data: Optional[Union[HistoricalPartData, Mapping[str, Any]]] = None,
    horizon_years: float = HORIZON_YEARS,
) -> float:
    """
    Five-year (default) conditional obsolescence probability given lifecycle
    status and optional historical part / peer-EOL data.
    """
    if lifecycle_status == "Obsolete":
        return 1.0

    historical = HistoricalPartData.from_mapping(
        historical_part_data if isinstance(historical_part_data, Mapping) else None
    )
    if isinstance(historical_part_data, HistoricalPartData):
        historical = historical_part_data

    shape, scale, age = _resolve_weibull_params(lifecycle_status, historical)
    probability = weibull_conditional_probability(age, horizon_years, shape, scale)
    if lifecycle_status == "NRND":
        probability = max(probability, 0.45)
    return min(1.0, probability)


def lifecycle_norm(p: PartRiskProfile) -> float:
    if p.lifecycle_status == "Active":
        return 0.0
    if p.lifecycle_status == "NRND":
        return 0.6
    if p.lifecycle_status == "Obsolete":
        return 1.0
    return 0.5


def second_source_norm(p: PartRiskProfile) -> float:
    if p.has_second_source is True:
        return 0.0
    if p.has_second_source is False:
        return 1.0
    return 0.5


def lead_time_norm(p: PartRiskProfile) -> float:
    if p.lead_time_weeks is None:
        return 0.5
    return min(float(p.lead_time_weeks) / 26.0, 1.0)


def stock_norm(p: PartRiskProfile) -> float:
    if p.stock is None:
        return 0.5
    return max(0.0, 1.0 - min(float(p.stock) / 1000.0, 1.0))


def criticality_norm(p: PartRiskProfile) -> float:
    crit = p.criticality.capitalize() if p.criticality else "Medium"
    if crit == "Low":
        return 0.0
    if crit == "Medium":
        return 0.5
    if crit == "High":
        return 1.0
    return 0.5


def obsolescence_norm(p: PartRiskProfile, historical: Optional[Union[HistoricalPartData, Mapping[str, Any]]] = None) -> float:
    """Hybrid obsolescence feature: Weibull 5-year forecast, floored by discrete lifecycle."""
    history = historical if historical is not None else p.historical_data
    forecast = weibull_obsolescence_probability(p.lifecycle_status, history)
    return max(lifecycle_norm(p), forecast)


def compute_base_score(
    p: PartRiskProfile,
    historical: Optional[Union[HistoricalPartData, Mapping[str, Any]]] = None,
    weights: Optional[Mapping[str, float]] = None,
) -> float:
    """Fuzzy-AHP weighted sum of the five normalized risk dimensions."""
    resolved = weights or AHP_WEIGHTS
    features = {
        "obsolescence": obsolescence_norm(p, historical),
        "second_source": second_source_norm(p),
        "lead_time": lead_time_norm(p),
        "stock": stock_norm(p),
        "criticality": criticality_norm(p),
    }
    return sum(resolved[name] * features[name] for name in CRITERIA)


OVERRIDE_RULES: List[Tuple[Callable[[PartRiskProfile], bool], float, str]] = [
    (
        lambda p: p.lifecycle_status == "Obsolete" and p.has_second_source is False,
        0.90,
        "Obsolete + single-sourced (catastrophic supply bottleneck)",
    ),
    (
        lambda p: p.lifecycle_status == "NRND" and p.has_second_source is False,
        0.80,
        "NRND + single-sourced (imminent obsolescence vulnerability)",
    ),
    (
        lambda p: (p.stock is not None and p.stock == 0) and (p.lead_time_weeks is not None and p.lead_time_weeks > 20),
        0.85,
        "Zero stock + long lead time (>20 weeks)",
    ),
    (
        lambda p: p.part_number is None,
        0.75,
        "Unassigned part number (TBD design placeholder)",
    ),
]


def band_from_score(score: float) -> str:
    """Maps continuous risk score (0.0 - 1.0) to actionable risk bands."""
    if score >= 0.85:
        return "Critical"
    if score >= 0.60:
        return "High"
    if score >= 0.30:
        return "Medium"
    return "Low"


def compute_risk(
    p: PartRiskProfile,
    historical_part_data: Optional[Union[HistoricalPartData, Mapping[str, Any]]] = None,
) -> PartRiskProfile:
    """
    Hybrid score: Fuzzy AHP weights on supply-chain features, Weibull 5-year
    obsolescence probability, then compounding override floors.
    """
    if str(getattr(p, "evidence_status", "") or "").upper() == "INSUFFICIENT_DATA":
        p.risk_score = None
        p.risk_band = "INSUFFICIENT_DATA"
        p.obsolescence_probability_5y = None
        if "INSUFFICIENT_DATA" not in p.risk_reasons:
            p.risk_reasons = list(p.risk_reasons) + [
                "INSUFFICIENT_DATA: no measured lifecycle, stock, lead-time, or second-source evidence"
            ]
        return p
    reasons: List[str] = list(p.risk_reasons)
    history = historical_part_data if historical_part_data is not None else p.historical_data
    obs_prob = weibull_obsolescence_probability(p.lifecycle_status, history)
    p.obsolescence_probability_5y = round(obs_prob, 4)

    score = compute_base_score(p, history)

    if p.missing_fields:
        reasons.append("Data Completeness Warning: incomplete supply-chain attributes")

    if p.lifecycle_status == "Obsolete":
        reasons.append("Lifecycle: Obsolete part status")
    elif p.lifecycle_status == "NRND":
        reasons.append("Lifecycle: Not Recommended for New Designs (NRND)")

    reasons.append(
        f"Obsolescence: Weibull 5-year conditional probability {obs_prob:.1%} (Fuzzy AHP hybrid)"
    )

    if p.has_second_source is False:
        reasons.append("Sourcing: Single-sourced component (no second source)")

    if p.lead_time_weeks and p.lead_time_weeks >= 26:
        reasons.append(f"Lead Time: Extended lead time ({p.lead_time_weeks} weeks)")

    if p.stock is not None and p.stock == 0:
        reasons.append("Inventory: Zero stock available in supply chain")
    elif p.stock is not None and p.stock < 100:
        reasons.append(f"Inventory: Low stock level ({p.stock} units)")

    if p.criticality == "High":
        reasons.append("Criticality: High business/system impact")

    for rule_fn, floor, override_reason in OVERRIDE_RULES:
        if rule_fn(p):
            if score < floor:
                score = floor
            if f"OVERRIDE: {override_reason}" not in reasons:
                reasons.append(f"OVERRIDE: {override_reason}")

    p.risk_score = round(score, 3)
    p.risk_band = band_from_score(score)
    p.risk_reasons = reasons
    p.exposure_score = round(score * p.qty, 3)
    if p.unit_cost_usd is None:
        p.financial_exposure_usd = None
    else:
        p.financial_exposure_usd = round(p.unit_cost_usd * p.qty * score, 2)
    return p
