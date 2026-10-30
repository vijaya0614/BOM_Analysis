"""Unit tests for PS5 Engineering Calculation Modules.

Covers:
- Weibull obsolescence probabilities and heuristic fallbacks
- Market supply pressure index, HHI, and availability tolerances
- Physical dimensionality, package matching, and hard constraints
- Worst-case, RSS, and Monte Carlo tolerance simulation
- Mission profile, thermal rise, Arrhenius AF, and cumulative damage
- Substitute hard gates and multi-criteria ranking
- FMEA RPN and Action Priority ratings
- 4-strategy lifecycle economics and break-even analysis
- Product-level risk aggregation.
"""

import pytest
from src.obsolescence_forecasting import (
    forecast_component_obsolescence,
    weibull_survival,
    conditional_unavailability_probability,
    classify_risk_tier,
)
from src.market_supply_risk import (
    evaluate_market_supply_risk,
    compute_inventory_coverage,
    compute_hhi,
    compute_supply_pressure_index,
    AvailabilityTolerances,
    SupplierShare,
)
from src.physical_compatibility import evaluate_physical_compatibility
from src.tolerance_analysis import (
    CircuitParameter,
    run_circuit_tolerance_analysis,
    voltage_divider_analysis,
    buck_regulator_vout_analysis,
    calculate_engineering_margins,
)
from src.mission_profile_engine import (
    arrhenius_acceleration_factor,
    evaluate_mission_profile,
    MissionProfilePhase,
    get_standard_mission_profiles,
)
from src.substitute_hard_gate import (
    evaluate_hard_gates,
    evaluate_candidate_substitutes,
)
from src.fmea_engine import generate_component_fmea, calculate_action_priority
from src.cost_scenarios import evaluate_cost_scenarios
from src.product_risk_aggregation import aggregate_product_risk
from src.synthetic_bom_generator import (
    validate_uploaded_bom_csv,
    generate_realistic_synthetic_bom_csv,
    generate_bom_csv_template,
)


# ── Test 1: Obsolescence Forecasting ──────────────────────────────────────────
def test_weibull_survival_properties():
    # S(0) = 1.0, S(inf) -> 0.0, monotonic decreasing
    beta = 2.0
    eta = 10.0
    assert weibull_survival(0, beta, eta) == 1.0
    s_5 = weibull_survival(5, beta, eta)
    s_10 = weibull_survival(10, beta, eta)
    s_15 = weibull_survival(15, beta, eta)
    assert 1.0 > s_5 > s_10 > s_15 > 0.0

    # Conditional probability P(T <= t+Delta | T > t) = 1 - S(t+Delta)/S(t)
    p_cond = conditional_unavailability_probability(5.0, 3.0, beta, eta)
    assert 0.0 < p_cond < 1.0
    expected = 1.0 - (weibull_survival(8.0, beta, eta) / weibull_survival(5.0, beta, eta))
    assert abs(p_cond - expected) < 1e-6


def test_obsolescence_forecast_active_vs_eol():
    # Active part forecast
    active_rep = forecast_component_obsolescence(
        part_number="TPS5402DGQR",
        category="Power Management",
        lifecycle_status="ACTIVE",
        estimated_age_years=4.0,
        has_second_source=True,
    )
    assert active_rep.model_used == "WEIBULL_SURVIVAL_MODEL"
    assert active_rep.horizons["1_year"].unavailability_probability < active_rep.horizons["5_year"].unavailability_probability
    assert active_rep.horizons["1_year"].risk_tier in {"LOW", "MODERATE"}

    # EOL part forecast
    eol_rep = forecast_component_obsolescence(
        part_number="DS1307Z+",
        category="Timing",
        lifecycle_status="EOL",
    )
    assert eol_rep.model_used == "STATUS_DETERMINISTIC"
    assert eol_rep.horizons["1_year"].unavailability_probability == 1.0
    assert eol_rep.horizons["1_year"].risk_tier == "CRITICAL"


def test_obsolescence_threshold_boundaries_and_metadata():
    assert classify_risk_tier(0.1499) == "LOW"
    assert classify_risk_tier(0.15) == "MODERATE"
    assert classify_risk_tier(0.40) == "HIGH"
    assert classify_risk_tier(0.70) == "CRITICAL"
    report = forecast_component_obsolescence("X", lifecycle_status="ACTIVE")
    metadata = report.to_dict()["model_metadata"]
    assert metadata["risk_tier_thresholds"] == {
        "MODERATE_MIN": 0.15, "HIGH_MIN": 0.40, "CRITICAL_MIN": 0.70
    }
    assert "UNVALIDATED" in metadata["parameter_calibration_status"]


# ── Test 2: Market & Supply Pressure ──────────────────────────────────────────
def test_inventory_coverage():
    # Coverage = Stock / Weekly demand
    assert compute_inventory_coverage(1000, 100.0) == 10.0
    # Zero demand -> infinity if stock exists
    assert compute_inventory_coverage(500, 0.0) == float("inf")
    # Unknown stock -> None
    assert compute_inventory_coverage(None, 50.0) is None


def test_hhi_concentration():
    # 2 equal suppliers -> HHI = 0.5^2 + 0.5^2 = 0.50
    shares = [SupplierShare("DigiKey", 0.5), SupplierShare("Mouser", 0.5)]
    hhi, tier = compute_hhi(shares)
    assert abs(hhi - 0.50) < 1e-3
    assert tier == "HIGH_CONCENTRATION"

    # Single source monopoly -> HHI = 1.0
    hhi_single, tier_single = compute_hhi(supplier_count=1)
    assert hhi_single == 1.0
    assert tier_single == "SOLE_SOURCE_MONOPOLY"
    assert compute_hhi() == (None, "UNKNOWN")


def test_spi_metadata_matches_missing_input_behavior():
    from src.market_supply_risk import SPI_WEIGHTS, SPI_TIER_THRESHOLDS
    assert sum(SPI_WEIGHTS.values()) == pytest.approx(1.0)
    assert SPI_TIER_THRESHOLDS == {"MODERATE_MIN": 25.0, "HIGH_MIN": 50.0, "CRITICAL_MIN": 75.0}
    report = evaluate_market_supply_risk("UNKNOWN")
    data = report.to_dict()
    assert data["hhi_tier"] == "UNKNOWN"
    assert data["hhi_concentration"] is None
    assert data["model_metadata"]["missing_input_proxies"]["supplier_concentration_risk"] == 0.5


def test_market_supply_risk_tolerances():
    tol = AvailabilityTolerances(
        min_required_stock=500,
        max_lead_time_weeks=12.0,
        min_inventory_coverage_weeks=4.0,
    )
    # Part with sufficient stock and acceptable lead time
    rep = evaluate_market_supply_risk(
        part_number="TPS5402",
        available_stock=5000,
        weekly_demand=100.0,
        estimated_lead_time_weeks=8.0,
        supplier_count=2,
        tolerances=tol,
    )
    assert rep.inventory_coverage_weeks == 50.0
    assert rep.supply_pressure_index < 40.0
    check_stock = next(c for c in rep.tolerance_checks if c.parameter == "minimum_required_stock")
    assert check_stock.status == "PASS"


# ── Test 3: Physical Dimensionality ───────────────────────────────────────────
def test_physical_compatibility_drop_in():
    res = evaluate_physical_compatibility(
        original_part="ORIG_IC",
        candidate_part="CAND_IC",
        orig_package="SOIC-8",
        cand_package="SOIC-8",
        orig_mounting="SMD",
        cand_mounting="SMD",
        orig_pin_count=8,
        cand_pin_count=8,
        orig_pin_pitch_mm=1.27,
        cand_pin_pitch_mm=1.27,
    )
    assert res.classification == "DROP_IN_CANDIDATE"
    assert res.is_drop_in is True
    assert len(res.hard_violations) == 0


def test_physical_compatibility_mounting_mismatch():
    res = evaluate_physical_compatibility(
        original_part="ORIG_IC",
        candidate_part="CAND_IC",
        orig_package="DIP-8",
        cand_package="SOIC-8",
        orig_mounting="THT",
        cand_mounting="SMD",
        orig_pin_count=8,
        cand_pin_count=8,
    )
    assert res.classification == "INCOMPATIBLE"
    assert res.is_drop_in is False
    assert any("Mounting technology mismatch" in v for v in res.hard_violations)


def test_physical_compatibility_requires_redesign():
    res = evaluate_physical_compatibility(
        original_part="ORIG_IC",
        candidate_part="CAND_IC",
        orig_package="SOIC-8",
        cand_package="TSSOP-8",
        orig_mounting="SMD",
        cand_mounting="SMD",
        orig_pin_count=8,
        cand_pin_count=8,
        orig_pin_pitch_mm=1.27,
        cand_pin_pitch_mm=0.65,
    )
    assert res.classification == "INCOMPATIBLE"  # Pin pitch delta is a hard violation for drop-in


# ── Test 4: Tolerance Analysis & Engineering Margins ──────────────────────────
def test_engineering_margins_calculation():
    # V_max = 28V, V_op = 12V -> margin = (28 - 12) / 28 = 57.1%
    margins = calculate_engineering_margins(
        v_op=12.0, v_max=28.0,
        i_op=1.0, i_max=2.0,
        p_op=1.5, p_max=3.0,
        t_op=75.0, t_max=125.0,
    )
    assert margins.voltage_margin_pct == 57.1
    assert margins.current_margin_pct == 50.0
    assert margins.power_margin_pct == 50.0
    assert margins.thermal_margin_c == 50.0
    assert margins.derating_compliant is True


def test_voltage_divider_monte_carlo():
    res = voltage_divider_analysis(
        r1_ohms=10000.0, r1_tol_pct=1.0,
        r2_ohms=10000.0, r2_tol_pct=1.0,
        vin_volts=5.0, vin_tol_pct=1.0,
        samples=1000,
    )
    assert abs(res.nominal_output - 2.50) < 1e-3
    assert res.worst_case_min < res.nominal_output < res.worst_case_max
    assert res.rss_3sigma_min < res.nominal_output < res.rss_3sigma_max
    assert len(res.histogram_bins) == 15
    assert res.monte_carlo_samples == 1000


# ── Test 5: Mission Profile & Thermal ─────────────────────────────────────────
def test_arrhenius_acceleration():
    # At reference temp (40 C), AF = 1.0
    af_ref = arrhenius_acceleration_factor(t_use_c=40.0, t_ref_c=40.0, activation_energy_ev=0.7)
    assert abs(af_ref - 1.0) < 1e-2

    # Higher temp -> accelerated aging (AF > 1)
    af_hot = arrhenius_acceleration_factor(t_use_c=85.0, t_ref_c=40.0, activation_energy_ev=0.7)
    assert af_hot > 10.0


def test_mission_profile_evaluation():
    phases = [
        MissionProfilePhase(
            name="Normal Load", annual_hours=4000.0, ambient_temp_c=45.0,
            power_dissipation_watts=1.0, operating_voltage=5.0, operating_current=0.20,
        ),
        MissionProfilePhase(
            name="Peak Load", annual_hours=1000.0, ambient_temp_c=65.0,
            power_dissipation_watts=1.5, operating_voltage=5.0, operating_current=0.30,
        ),
    ]
    eval_res = evaluate_mission_profile(
        component_name="Buck IC",
        part_number="TPS5402",
        phases=phases,
        rated_temp_max_c=125.0,
        thermal_resistance_c_per_w=40.0,
    )
    assert eval_res.peak_junction_temp_c > 65.0
    assert eval_res.worst_thermal_margin_c >= 0.0
    assert len(eval_res.phases) == 2
    assert len(eval_res.mitigation_comparisons) == 3
    assert eval_res.to_dict()["model_metadata"]["activation_energy_ev"] == 0.70


# ── Test 6: Intelligent Substitution Hard Gates ───────────────────────────────
def test_substitute_hard_gates_filtering():
    def citation(value):
        return {
            "source_id": f"SRC-{value}",
            "source_title": "Manufacturer datasheet",
            "source_url": "https://manufacturer.example/datasheet.pdf",
            "source_page": "4",
            "confidence": "HIGH",
            "source_type": "MANUFACTURER_DATASHEET",
            "evidence_summary": str(value),
        }

    def evidence(package, pinout, voltage, current, temperature):
        return {
            "package": citation(package),
            "pinout": citation(pinout),
            "ratings": {
                "voltage_rating": citation(voltage),
                "current_rating": citation(current),
                "temperature_rating": citation(temperature),
            },
        }

    orig = {
        "part_number": "ORIG_5V",
        "category": "Power Management",
        "operating_voltage_max": 28.0,
        "operating_current_max": 2.0,
        "operating_temperature_max": 125.0,
        "package": "SOIC-8",
        "mounting": "SMD",
        "pinout": "1=VIN,2=GND",
        "evidence": evidence("SOIC-8", "1=VIN,2=GND", 28.0, 2.0, 125.0),
    }
    candidates = [
        # Candidate 1: Perfect drop-in
        {
            "part_number": "DROPIN_PART",
            "category": "Power Management",
            "operating_voltage_max": 30.0,
            "operating_current_max": 2.5,
            "operating_temperature_max": 125.0,
            "package": "SOIC-8",
            "mounting": "SMD",
            "pinout": "1=VIN,2=GND",
            "evidence": evidence("SOIC-8", "1=VIN,2=GND", 30.0, 2.5, 125.0),
        },
        # Candidate 2: Voltage too low (hard violation)
        {
            "part_number": "WEAK_VOLTAGE",
            "category": "Power Management",
            "operating_voltage_max": 18.0,  # Fails 28V requirement
            "operating_current_max": 2.5,
            "operating_temperature_max": 125.0,
            "package": "SOIC-8",
            "mounting": "SMD",
        },
        # Candidate 3: Package mismatch (requires redesign)
        {
            "part_number": "REDESIGN_PART",
            "category": "Power Management",
            "operating_voltage_max": 30.0,
            "operating_current_max": 2.5,
            "operating_temperature_max": 125.0,
            "package": "DFN-8",
            "mounting": "SMD",
        },
    ]

    res = evaluate_candidate_substitutes(orig, candidates)
    dropins = [c for c in res if c.classification == "DROP_IN_CANDIDATE"]
    redesigns = [c for c in res if c.classification == "REQUIRES_REDESIGN"]
    incompatibles = [c for c in res if c.classification == "INCOMPATIBLE"]
    insufficient = [c for c in res if c.classification == "INSUFFICIENT_EVIDENCE"]

    assert len(dropins) == 1
    assert dropins[0].candidate_mpn == "DROPIN_PART"
    assert dropins[0].drop_in_evidence["status"] == "SUPPORTED"
    assert not insufficient
    assert len(incompatibles) == 1
    assert incompatibles[0].candidate_mpn == "WEAK_VOLTAGE"
    assert len(redesigns) == 1
    assert redesigns[0].candidate_mpn == "REDESIGN_PART"


# ── Test 7: FMEA Generation & Scoring ─────────────────────────────────────────
def test_fmea_rpn_calculation():
    entries = generate_component_fmea("TPS5402", "Buck Converter", "regulator")
    assert len(entries) >= 2
    for e in entries:
        assert e.rpn == e.severity * e.occurrence * e.detection
        assert e.residual_rpn < e.rpn
        assert e.action_priority in {"HIGH", "MEDIUM", "LOW"}
    assert calculate_action_priority(7, 5, 1) == "HIGH"
    assert calculate_action_priority(5, 1, 1) == "MEDIUM"
    assert calculate_action_priority(4, 4, 4) == "LOW"


# ── Test 8: Lifecycle Cost Scenarios ──────────────────────────────────────────
def test_cost_scenarios_comparison():
    rep = evaluate_cost_scenarios(
        part_number="TEST_IC",
        annual_volume=5000,
        horizon_years=5,
        current_unit_price=2.00,
        substitute_unit_price=1.80,
        substitute_qualification_cost=3000.0,
    )
    assert len(rep.strategies) == 4
    strat_a = rep.strategies["STRATEGY_A"]
    strat_c = rep.strategies["STRATEGY_C"]
    assert strat_a.total_cost > 0
    # Drop in alternative saves money over 25,000 units
    assert strat_c.net_savings_vs_baseline > 0
    assert strat_c.break_even_volume_units is not None
    assumptions = " ".join(rep.assumptions)
    assert "placeholders, not market quotes" in assumptions


# ── Test 9: Product Risk Aggregation ──────────────────────────────────────────
def test_product_risk_aggregation():
    comps = [
        {"pn": "IC1", "ref": "U1", "qty": 1, "score": 0.85, "band": "CRITICAL", "lifecycle_status": "EOL", "has_second_source": False},
        {"pn": "IC2", "ref": "U2", "qty": 1, "score": 0.20, "band": "LOW", "lifecycle_status": "ACTIVE", "has_second_source": True},
    ]
    summary = aggregate_product_risk("Test Device", comps)
    assert summary.total_components_count == 2
    assert summary.eol_count == 1
    assert summary.single_points_of_failure_count == 1
    assert len(summary.highest_risk_lines) == 2


# ── Test 10: Synthetic BOM Generation & CSV Validation ────────────────────────
def test_synthetic_bom_csv_validation():
    csv_text = generate_realistic_synthetic_bom_csv()
    val = validate_uploaded_bom_csv(csv_text)
    assert val.is_valid is True
    assert val.valid_rows_count >= 15
    assert val.error_count == 0
