from src.models import PartRiskProfile
from src.risk_engine import (
    AHP_WEIGHTS,
    CRITERIA,
    HistoricalPartData,
    band_from_score,
    compute_risk,
    fit_weibull_from_ages,
    fuzzy_ahp_weights,
    weibull_conditional_probability,
    weibull_obsolescence_probability,
)

def test_band_from_score():
    assert band_from_score(0.90) == "Critical"
    assert band_from_score(0.70) == "High"
    assert band_from_score(0.45) == "Medium"
    assert band_from_score(0.15) == "Low"

def test_reed_switch_compounding_override():
    # Reed switch: Obsolete + Single-sourced (should trigger 0.90 Critical floor override)
    p = PartRiskProfile(
        part_number="REED-SW-14MM",
        qty=1,
        lifecycle_status="Obsolete",
        lead_time_weeks=52,
        stock=0,
        has_second_source=False,
        criticality="High"
    )
    
    scored = compute_risk(p)
    assert scored.risk_score >= 0.90
    assert scored.risk_band == "Critical"
    assert any("Obsolete + single-sourced" in reason for reason in scored.risk_reasons)

def test_low_risk_active_resistor():
    p = PartRiskProfile(
        part_number="RES-1K-0805",
        qty=6,
        lifecycle_status="Active",
        lead_time_weeks=1,
        stock=750000,
        has_second_source=True,
        criticality="Low"
    )
    
    scored = compute_risk(p)
    assert scored.risk_score < 0.20
    assert scored.risk_band == "Low"

def test_missing_data_transparency_reason():
    p = PartRiskProfile(
        part_number=None,
        qty=1,
        missing_fields=["lifecycle_status", "lead_time_weeks", "stock", "has_second_source", "criticality"],
        confidence_score=0.0
    )
    
    scored = compute_risk(p)
    assert scored.risk_band in ["High", "Critical"]
    assert any("Data Completeness Warning" in r or "TBD design placeholder" in r for r in scored.risk_reasons)


def test_fuzzy_ahp_weights_replace_static_priorities():
    weights = fuzzy_ahp_weights()
    assert set(weights) == set(CRITERIA)
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert all(value > 0 for value in weights.values())
    assert weights["obsolescence"] > weights["second_source"] > weights["stock"] > weights["criticality"]
    assert AHP_WEIGHTS["obsolescence"] == weights["obsolescence"]


def test_weibull_conditional_probability_increases_with_horizon():
    p3 = weibull_conditional_probability(age_years=2.0, horizon_years=3.0, shape=2.4, scale=16.0)
    p5 = weibull_conditional_probability(age_years=2.0, horizon_years=5.0, shape=2.4, scale=16.0)
    p8 = weibull_conditional_probability(age_years=2.0, horizon_years=8.0, shape=2.4, scale=16.0)
    assert 0.0 <= p3 < p5 < p8 <= 1.0


def test_weibull_obsolescence_uses_lifecycle_and_history():
    active = weibull_obsolescence_probability("Active")
    nrnd = weibull_obsolescence_probability("NRND")
    obsolete = weibull_obsolescence_probability("Obsolete")
    assert obsolete == 1.0
    assert active < nrnd < obsolete
    assert active < 0.25

    youthful = HistoricalPartData(years_in_production=1.0, weibull_shape=2.4, weibull_scale=20.0)
    aged = HistoricalPartData(years_in_production=10.0, weibull_shape=2.4, weibull_scale=20.0)
    assert weibull_obsolescence_probability("Active", youthful) < weibull_obsolescence_probability("Active", aged)

    fitted_shape, fitted_scale = fit_weibull_from_ages([6, 8, 9, 11, 13])
    from_samples = weibull_obsolescence_probability(
        "Active",
        {"years_in_production": 7.0, "observed_obsolescence_ages": [6, 8, 9, 11, 13]},
    )
    from_params = weibull_obsolescence_probability(
        "Active",
        HistoricalPartData(years_in_production=7.0, weibull_shape=fitted_shape, weibull_scale=fitted_scale),
    )
    assert abs(from_samples - from_params) < 1e-9


def test_compute_risk_records_five_year_obsolescence_probability():
    scored = compute_risk(
        PartRiskProfile(
            part_number="STM32F411CEU6",
            lifecycle_status="NRND",
            has_second_source=True,
            lead_time_weeks=16,
            stock=400,
            criticality="Medium",
            historical_data={"years_in_production": 6.0, "observed_obsolescence_ages": [7, 8, 10, 12]},
        )
    )
    assert scored.obsolescence_probability_5y is not None
    assert scored.obsolescence_probability_5y >= 0.45
    assert any("Weibull 5-year" in reason for reason in scored.risk_reasons)

