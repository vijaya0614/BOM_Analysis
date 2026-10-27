import math

from src.reliability_stress import (
    CapacitorStyle,
    Environment,
    Quality,
    SemiconductorStyle,
    StressConditions,
    analyze_part_stress,
    aging_guardband,
    linear_mtbf_scale,
    part_stress_capacitor,
    part_stress_semiconductor,
    thermal_derating_factor,
)


def _ceramic(temp_c: float, **overrides) -> StressConditions:
    data = dict(
        ambient_c=temp_c,
        voltage_applied=12.0,
        voltage_rated=50.0,
        capacitance_uf=0.1,
        environment=Environment.GB,
        quality=Quality.COMMERCIAL,
        temp_rated_max_c=125.0,
        duty_cycle=0.2,
        switching_hz=0.0,
        recovery_fraction=0.0,
        calendar_age_years=0.0,
    )
    data.update(overrides)
    return StressConditions(**data)


def _mosfet(temp_c: float, **overrides) -> StressConditions:
    data = dict(
        ambient_c=25.0,
        junction_c=temp_c,
        voltage_applied=12.0,
        voltage_rated=30.0,
        power_w=0.4,
        rated_power_w=1.5,
        environment=Environment.GB,
        quality=Quality.COMMERCIAL,
        temp_rated_max_c=150.0,
        duty_cycle=0.6,
        switching_hz=20_000,
        recovery_fraction=0.1,
        calendar_age_years=1.0,
    )
    data.update(overrides)
    return StressConditions(**data)


def test_part_stress_is_not_linear_mtbf_scaling():
    cool = part_stress_semiconductor(SemiconductorStyle.MOSFET, _mosfet(40.0))
    hot = part_stress_semiconductor(SemiconductorStyle.MOSFET, _mosfet(110.0))
    assert hot.lambda_per_million_hours > cool.lambda_per_million_hours
    naive = linear_mtbf_scale(cool.mtbf_hours, 40.0, 110.0)
    assert not math.isclose(hot.mtbf_hours, naive, rel_tol=0.15)


def test_capacitor_voltage_and_temperature_raise_failure_rate():
    base = part_stress_capacitor(CapacitorStyle.CERAMIC, _ceramic(40.0, voltage_applied=10.0))
    stressed = part_stress_capacitor(CapacitorStyle.CERAMIC, _ceramic(85.0, voltage_applied=40.0))
    assert stressed.lambda_per_million_hours > 5 * base.lambda_per_million_hours
    assert "Linear MTBF" in stressed.notes[0]


def test_environment_and_thermal_derating_corrections():
    benign = part_stress_semiconductor(SemiconductorStyle.BJT, _mosfet(70.0, environment=Environment.GB, quality=Quality.JANTX))
    fighter = part_stress_semiconductor(SemiconductorStyle.BJT, _mosfet(70.0, environment=Environment.AUF, quality=Quality.JANTX))
    assert fighter.pi_factors["pi_E"] > benign.pi_factors["pi_E"]
    assert fighter.lambda_per_million_hours > benign.lambda_per_million_hours
    assert thermal_derating_factor(140.0, 150.0, 30.0) > thermal_derating_factor(90.0, 150.0, 30.0)


def test_switching_activity_and_recovery_guardbands():
    heavy = aging_guardband(
        duty_cycle=0.9,
        switching_hz=50_000,
        recovery_fraction=0.0,
        calendar_age_years=4.0,
        reference_switching_hz=10_000,
    )
    recovered = aging_guardband(
        duty_cycle=0.2,
        switching_hz=100,
        recovery_fraction=0.8,
        calendar_age_years=0.5,
        reference_switching_hz=10_000,
    )
    assert heavy["pi_guardband"] > recovered["pi_guardband"]
    assert recovered["pi_recovery"] < 1.0
    assert heavy["pi_switching"] > recovered["pi_switching"]

    switching = part_stress_semiconductor(SemiconductorStyle.MOSFET, _mosfet(85.0, duty_cycle=0.95, switching_hz=80_000, recovery_fraction=0.0))
    rested = part_stress_semiconductor(SemiconductorStyle.MOSFET, _mosfet(85.0, duty_cycle=0.1, switching_hz=100, recovery_fraction=0.85))
    assert switching.lambda_per_million_hours > rested.lambda_per_million_hours


def test_analyze_part_stress_dispatch():
    cap = analyze_part_stress("capacitor", "CERAMIC", _ceramic(55.0))
    fet = analyze_part_stress("semiconductor", "MOSFET", _mosfet(90.0))
    assert cap.family == "capacitor"
    assert fet.style == "MOSFET"
    assert cap.fit == cap.lambda_per_million_hours * 1000.0
    assert fet.mtbf_hours == 1.0e6 / fet.lambda_per_million_hours
