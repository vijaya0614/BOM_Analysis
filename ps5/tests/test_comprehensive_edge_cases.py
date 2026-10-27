"""Comprehensive unit & edge case tests for risk_engine, redesign_decision, and reliability_stress."""

import math
import pytest
from src.models import PartRiskProfile
from src.schemas import BomComponent, RedesignCost
from src.risk_engine import (
    AHP_WEIGHTS,
    CRITERIA,
    HistoricalPartData,
    band_from_score,
    build_fuzzy_pairwise_matrix,
    compute_base_score,
    compute_risk,
    criticality_norm,
    fit_weibull_from_ages,
    fuzzy_ahp_weights,
    lead_time_norm,
    lifecycle_norm,
    obsolescence_norm,
    second_source_norm,
    stock_norm,
    weibull_conditional_probability,
    weibull_obsolescence_probability,
)
from src.redesign_decision import (
    DESIGN_REFRESH,
    DROP_IN,
    LTB,
    MitigationPart,
    OptimizationResult,
    StrategyCost,
    annuity_pv,
    compare_strategies,
    design_refresh_cost,
    drop_in_cost,
    holding_npv_coefficient,
    optimize_from_bom,
    optimize_obsolescence_plan,
    pv,
    recommend_strategy,
)
from src.reliability_stress import (
    CapacitorStyle,
    Environment,
    Quality,
    ReliabilityModelError,
    SemiconductorStyle,
    StressConditions,
    aging_guardband,
    analyze_part_stress,
    capacitor_base_rate,
    environmental_stress_factor,
    junction_temperature_c,
    linear_mtbf_scale,
    part_stress_capacitor,
    part_stress_semiconductor,
    pi_application_switching,
    pi_power_rating,
    pi_series_resistance,
    pi_temperature_semiconductor,
    pi_voltage_stress_semiconductor,
    quality_factor,
    semiconductor_base_rate,
    stress_ratio,
    thermal_derating_factor,
)


# =====================================================================
# 1. RISK ENGINE EDGE CASES & MULTI-ATTRIBUTE CONFLICTS
# =====================================================================

def test_risk_engine_zero_stock_edge_case():
    """Edge Case: Zero stock available in supply chain."""
    p_zero_stock = PartRiskProfile(
        part_number="ZERO-STOCK-PART",
        qty=10,
        stock=0,
        lead_time_weeks=12,
        lifecycle_status="Active",
        has_second_source=True,
        criticality="Medium",
    )
    scored = compute_risk(p_zero_stock)
    assert stock_norm(p_zero_stock) == 1.0
    assert any("Inventory: Zero stock available" in reason for reason in scored.risk_reasons)
    assert math.isclose(scored.exposure_score, scored.risk_score * 10, rel_tol=0.01)

def test_risk_engine_infinite_and_missing_lead_time_edge_cases():
    """Edge Case: Infinite, missing, or extreme lead times."""
    p_missing_lead = PartRiskProfile(part_number="NO-LT", lead_time_weeks=None)
    assert lead_time_norm(p_missing_lead) == 0.5

    p_long_lead = PartRiskProfile(part_number="LONG-LT", lead_time_weeks=52)
    assert lead_time_norm(p_long_lead) == 1.0
    scored_long = compute_risk(p_long_lead)
    assert any("Lead Time: Extended lead time (52 weeks)" in r for r in scored_long.risk_reasons)

    # Edge Case: Zero stock + Lead time > 20 weeks triggers OVERRIDE
    p_zero_stock_long_lead = PartRiskProfile(
        part_number="CRIT-COMBO",
        stock=0,
        lead_time_weeks=22,
        lifecycle_status="Active",
        has_second_source=True,
        criticality="Low",
    )
    scored_combo = compute_risk(p_zero_stock_long_lead)
    assert scored_combo.risk_score >= 0.85
    assert scored_combo.risk_band == "Critical"
    assert any("OVERRIDE: Zero stock + long lead time (>20 weeks)" in r for r in scored_combo.risk_reasons)

def test_risk_engine_conflicting_multi_attribute_scores():
    """Edge Case: Conflicting multi-attribute risk factors.
    Low criticality part but Obsolete + single-sourced must be overridden to Critical.
    """
    p_conflict = PartRiskProfile(
        part_number="LOW-CRIT-OBSOLETE",
        criticality="Low",  # Norm = 0.0
        lifecycle_status="Obsolete",  # Norm = 1.0
        has_second_source=False,  # Norm = 1.0
        stock=50000,  # High stock (Norm = 0.0)
        lead_time_weeks=1,  # Fast lead time (Norm = 0.04)
    )
    scored = compute_risk(p_conflict)
    # Without override, score might be ~0.40 (Medium), but override floors it at 0.90 (Critical)
    assert scored.risk_score >= 0.90
    assert scored.risk_band == "Critical"

    # Conflicting: NRND + Single source (Floor 0.80)
    p_nrnd_single = PartRiskProfile(
        part_number="NRND-SINGLE",
        criticality="Low",
        lifecycle_status="NRND",
        has_second_source=False,
        stock=10000,
        lead_time_weeks=2,
    )
    scored_nrnd = compute_risk(p_nrnd_single)
    assert scored_nrnd.risk_score >= 0.80
    assert scored_nrnd.risk_band in ["High", "Critical"]

def test_risk_engine_historical_data_mapping_and_fitting():
    """HistoricalPartData mapping and Weibull fitting edge cases."""
    data_map = {
        "years_in_production": 3.5,
        "eol_ages": [5.0, 7.0, 8.5],
        "shape": 2.1,
        "scale": 12.0,
        "category": "MCU",
    }
    hist = HistoricalPartData.from_mapping(data_map)
    assert hist is not None
    assert hist.years_in_production == 3.5
    assert hist.observed_obsolescence_ages == [5.0, 7.0, 8.5]
    assert hist.weibull_shape == 2.1
    assert hist.weibull_scale == 12.0

    assert HistoricalPartData.from_mapping(None) is None
    assert HistoricalPartData.from_mapping(hist) is hist

    # Weibull fit error with < 2 ages
    with pytest.raises(ValueError, match="At least two positive obsolescence ages"):
        fit_weibull_from_ages([5.0])

    # Weibull fit zero variance case
    shape, scale = fit_weibull_from_ages([10.0, 10.0])
    assert shape == 2.2
    assert scale == 10.0

    # Weibull probability error with non-positive scale or shape
    with pytest.raises(ValueError, match="Weibull shape and scale must be positive"):
        weibull_conditional_probability(age_years=2.0, horizon_years=5.0, shape=-1.0, scale=10.0)

def test_risk_engine_normalization_functions():
    """Comprehensive check of individual norm functions."""
    p_active = PartRiskProfile("P1", lifecycle_status="Active", has_second_source=True, stock=1000, criticality="Low")
    p_nrnd = PartRiskProfile("P2", lifecycle_status="NRND", has_second_source=False, stock=500, criticality="Medium")
    p_obs = PartRiskProfile("P3", lifecycle_status="Obsolete", has_second_source=None, stock=None, criticality="High")
    p_unknown = PartRiskProfile("P4", lifecycle_status="Unknown", criticality="Unknown")

    assert lifecycle_norm(p_active) == 0.0
    assert lifecycle_norm(p_nrnd) == 0.6
    assert lifecycle_norm(p_obs) == 1.0
    assert lifecycle_norm(p_unknown) == 0.5

    assert second_source_norm(p_active) == 0.0
    assert second_source_norm(p_nrnd) == 1.0
    assert second_source_norm(p_obs) == 0.5

    assert stock_norm(p_active) == 0.0
    assert abs(stock_norm(p_nrnd) - 0.5) < 1e-6
    assert stock_norm(p_obs) == 0.5

    assert criticality_norm(p_active) == 0.0
    assert criticality_norm(p_nrnd) == 0.5
    assert criticality_norm(p_obs) == 1.0
    assert criticality_norm(p_unknown) == 0.5


# =====================================================================
# 2. REDESIGN DECISION EDGE CASES & STRATEGY SELECTION
# =====================================================================

def test_redesign_decision_pv_and_annuity_edge_cases():
    """Test present value calculations and edge cases."""
    assert pv(100.0, 0.08, 0) == 100.0
    assert pv(100.0, 0.08, -1) == 100.0
    assert annuity_pv(100.0, 0.08, 3, 2) == 0.0
    assert holding_npv_coefficient(0, 0.18, 0.08) == 0.0
    assert holding_npv_coefficient(5, 0.0, 0.08) == 0.0

def test_redesign_decision_mitigation_part_validations():
    """Test validation errors in MitigationPart."""
    with pytest.raises(ValueError, match="demand_per_year must be >= 0"):
        MitigationPart(part_number="P1", demand_per_year=-5, unit_cost=10.0, holding_rate=0.1, discount_rate=0.08)

    with pytest.raises(ValueError, match="horizon_years must be >= 1"):
        MitigationPart(part_number="P1", demand_per_year=10, unit_cost=10.0, holding_rate=0.1, discount_rate=0.08, horizon_years=0)

    with pytest.raises(ValueError, match="refresh_year must be >= 1"):
        MitigationPart(part_number="P1", demand_per_year=10, unit_cost=10.0, holding_rate=0.1, discount_rate=0.08, refresh_year=0)

def test_redesign_decision_unfeasible_strategy_edge_cases():
    """Edge Case: When drop-in and refresh strategies are unavailable."""
    unavailable = MitigationPart(
        part_number="NO-STRATEGY",
        demand_per_year=10,
        unit_cost=100.0,
        holding_rate=0.2,
        discount_rate=0.08,
        dropin_available=False,
        refresh_available=False,
    )
    strategies = compare_strategies(unavailable)
    dropin_cost = next(s for s in strategies if s.strategy == DROP_IN)
    refresh_cost = next(s for s in strategies if s.strategy == DESIGN_REFRESH)
    assert not dropin_cost.feasible
    assert math.isinf(dropin_cost.total_npv)
    assert not refresh_cost.feasible
    assert math.isinf(refresh_cost.total_npv)

    # recommend_strategy returns LTB as the only feasible strategy
    best = recommend_strategy(unavailable)
    assert best.strategy == LTB

def test_redesign_decision_optimization_edge_cases():
    """Test optimization error handling and serialization."""
    with pytest.raises(ValueError, match="At least one part is required"):
        optimize_obsolescence_plan([])

    p = MitigationPart(
        part_number="RES-10K",
        demand_per_year=100,
        unit_cost=0.05,
        holding_rate=0.1,
        discount_rate=0.08,
    )
    result = optimize_obsolescence_plan([p], shared_refresh_nre=500.0)
    assert result.status == "Optimal"
    res_dict = result.as_dict()
    assert res_dict["status"] == "Optimal"
    assert "RES-10K" in res_dict["assignments"]

def test_redesign_decision_optimize_from_bom_roundtrip():
    """Test optimize_from_bom end-to-end wrapper."""
    bom_comps = [
        BomComponent(
            part_number="IC-GATE-1",
            category="Interface",
            package="SOIC-14",
            criticality="Medium",
            qty=5,
            unit_cost=2.50,
            second_source=False,
            lead_time_weeks=12,
            lifecycle_status="NRND",
            distributor_stock=50,
        )
    ]
    redesign_costs = {
        "IC-GATE-1": RedesignCost(
            original_part_number="IC-GATE-1",
            substitute_part_number="IC-GATE-1A",
            requalification_expense=500.0,
            holding_cost=50.0,
            engineering_hours=10,
            hourly_rate=75.0,
            last_time_buy_qty=25,
            holding_cost_per_unit_per_week=0.01,
            holding_weeks=52,
        )
    }
    opt = optimize_from_bom(bom_comps, redesign_costs)
    assert opt.status == "Optimal"
    assert "IC-GATE-1" in opt.assignments


# =====================================================================
# 3. RELIABILITY STRESS EDGE CASES
# =====================================================================

def test_reliability_stress_temperature_and_stress_errors():
    """Edge cases for linear_mtbf_scale, stress_ratio, and invalid parameters."""
    with pytest.raises(ReliabilityModelError, match="Use temperature must be above absolute zero"):
        linear_mtbf_scale(100000.0, 25.0, -274.0)

    with pytest.raises(ReliabilityModelError, match="Rated stress must be positive"):
        stress_ratio(10.0, 0.0)

    with pytest.raises(ReliabilityModelError, match="Unsupported environment"):
        environmental_stress_factor("INVALID_ENV", "capacitor")

    with pytest.raises(ReliabilityModelError, match="Unsupported quality"):
        quality_factor("INVALID_QUAL", "semiconductor")

    with pytest.raises(ReliabilityModelError, match="Capacitance in μF is required"):
        part_stress_capacitor(CapacitorStyle.CERAMIC, StressConditions(capacitance_uf=None))

    with pytest.raises(ReliabilityModelError, match="Unsupported part family"):
        analyze_part_stress("unknown_family", "BJT", StressConditions())

def test_reliability_stress_junction_temp_variations():
    """Test junction temperature calculation with junction_c, case_c, and ambient_c."""
    assert junction_temperature_c(25.0, junction_c=85.0) == 85.0
    assert junction_temperature_c(25.0, power_w=2.0, theta_ja_c_per_w=10.0, case_c=45.0) == 45.0 + 2.0 * 10.0 * 0.25
    assert junction_temperature_c(25.0, power_w=2.0, theta_ja_c_per_w=10.0) == 45.0

def test_reliability_stress_capacitor_styles_and_series_resistance():
    """Test Tantalum and Aluminum capacitor part stress and series resistance factors."""
    cond_tant = StressConditions(
        ambient_c=30.0,
        voltage_applied=10.0,
        voltage_rated=20.0,
        capacitance_uf=10.0,
        series_resistance_ohm=10.0,  # CR = 1.0 >= 0.8 -> pi_SR = 0.66
        environment=Environment.GB,
        quality=Quality.COMMERCIAL,
    )
    res_tant = part_stress_capacitor(CapacitorStyle.TANTALUM, cond_tant)
    assert res_tant.pi_factors["pi_SR"] == 0.66

    cond_tant_low_sr = StressConditions(
        ambient_c=30.0,
        voltage_applied=10.0,
        voltage_rated=20.0,
        capacitance_uf=10.0,
        series_resistance_ohm=0.5,  # CR = 0.05 < 0.1 -> pi_SR = 2.0
        environment=Environment.GB,
        quality=Quality.COMMERCIAL,
    )
    res_tant_low_sr = part_stress_capacitor(CapacitorStyle.TANTALUM, cond_tant_low_sr)
    assert res_tant_low_sr.pi_factors["pi_SR"] == 2.0

    cond_alum = StressConditions(
        ambient_c=40.0,
        voltage_applied=25.0,
        voltage_rated=50.0,
        capacitance_uf=100.0,
        environment=Environment.GF,
        quality=Quality.COMMERCIAL,
    )
    res_alum = part_stress_capacitor(CapacitorStyle.ALUMINUM, cond_alum)
    assert res_alum.family == "capacitor"
    assert res_alum.style == "ALUMINUM"

def test_reliability_stress_semiconductor_styles_and_ratings():
    """Test JFET, Diode, and BJT semiconductor part stress and ratings."""
    cond_jfet = StressConditions(
        ambient_c=25.0,
        junction_c=50.0,
        voltage_applied=5.0,
        voltage_rated=15.0,
        environment=Environment.GB,
        quality=Quality.JANTXV,
    )
    res_jfet = part_stress_semiconductor(SemiconductorStyle.JFET, cond_jfet)
    assert res_jfet.style == "JFET"

    cond_diode = StressConditions(
        ambient_c=25.0,
        junction_c=60.0,
        voltage_applied=10.0,
        voltage_rated=100.0,
        rated_power_w=5.0,  # pi_R = 5^0.37
        duty_cycle=0.5,
        environment=Environment.GB,
        quality=Quality.JAN,
    )
    res_diode = part_stress_semiconductor(SemiconductorStyle.DIODE, cond_diode)
    assert res_diode.style == "DIODE"
    assert res_diode.pi_factors["pi_R"] > 1.5

def test_reliability_stress_as_dict_serialization():
    """Test PartStressResult as_dict method."""
    cond = StressConditions(capacitance_uf=1.0, voltage_applied=5.0, voltage_rated=25.0)
    res = part_stress_capacitor(CapacitorStyle.CERAMIC, cond)
    d = res.as_dict()
    assert d["family"] == "capacitor"
    assert d["style"] == "CERAMIC"
    assert "lambda_per_million_hours" in d
    assert "fit" in d
