"""Mission Profile and Operating-Condition Analysis Engine.

Implements:
9.1 Thermal analysis: Delta T = P * R_theta, T_junction = T_ambient + Delta T
9.2 Arrhenius acceleration factor:
    AF = exp((E_a / k) * (1 / T_ref - 1 / T_use))
    using absolute temperature in Kelvin and k = 8.617333e-5 eV/K.
9.3 Linear damage accumulation (Miner's rule): D = sum(Delta t_j / L_j)
9.4 Side-by-side before-and-after hypothetical mitigation modeling.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Physical constants
BOLTZMANN_K_EV = 8.617333262145e-5  # eV/K
KELVIN_OFFSET = 273.15
DEFAULT_REFERENCE_TEMP_C = 40.0
DEFAULT_ACTIVATION_ENERGY_EV = 0.70
DEFAULT_LIFE_HOURS_AT_REFERENCE = 100000.0
DEFAULT_TARGET_SERVICE_YEARS = 10
DEFAULT_RATED_TEMP_MAX_C = 125.0
DEFAULT_THERMAL_RESISTANCE_C_PER_W = 42.0


@dataclass
class MissionProfilePhase:
    name: str
    annual_hours: float  # e.g. 2000 hours/year
    ambient_temp_c: float
    power_dissipation_watts: float
    operating_voltage: float
    operating_current: float
    duty_cycle: float = 1.0  # 0.0 to 1.0
    relative_humidity_pct: float = 45.0
    vibration_g_rms: float = 0.5
    thermal_cycles_per_year: int = 250
    cycle_delta_t_c: float = 30.0


@dataclass
class PhaseAnalysisResult:
    phase_name: str
    annual_hours: float
    ambient_temp_c: float
    power_watts: float
    temp_rise_delta_c: float
    junction_temp_c: float
    junction_temp_k: float
    arrhenius_af: float
    phase_damage_fraction: float
    thermal_margin_c: float
    is_junction_temp_exceeded: bool


@dataclass
class MissionProfileEvaluation:
    component_name: str
    part_number: str
    rated_temp_max_c: float
    thermal_resistance_c_per_w: float  # R_theta_JA
    nominal_life_hours_at_ref: float   # e.g. 100,000 hrs at 40 C
    activation_energy_ev: float       # e.g. 0.70 eV
    total_operating_hours_per_year: float
    target_service_years: int
    phases: List[PhaseAnalysisResult]
    peak_junction_temp_c: float
    worst_thermal_margin_c: float
    annual_cumulative_damage_d: float
    projected_life_years: float
    life_consumption_over_target_pct: float
    is_service_life_adequate: bool
    mitigation_comparisons: List[Dict[str, Any]]
    assumptions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["phases"] = [asdict(p) for p in self.phases]
        res["model_metadata"] = {
            "arrhenius_reference_temp_c": DEFAULT_REFERENCE_TEMP_C,
            "activation_energy_ev": self.activation_energy_ev,
            "nominal_life_hours_at_ref": self.nominal_life_hours_at_ref,
            "linear_miner_damage_model": True,
            "thermal_model": "one_dimensional_junction_to_ambient_resistance",
            "parameter_calibration_status": "USER_OR_DEFAULT_ASSUMPTIONS_NOT_COMPONENT_CALIBRATED",
            "life_projection_is_not_a_qualified_reliability_prediction": True,
        }
        return res


def arrhenius_acceleration_factor(
    t_use_c: float,
    t_ref_c: float = DEFAULT_REFERENCE_TEMP_C,
    activation_energy_ev: float = DEFAULT_ACTIVATION_ENERGY_EV,
) -> float:
    """
    Compute Arrhenius thermal acceleration factor:
    AF = exp((Ea / k) * (1 / T_ref_K - 1 / T_use_K))
    AF > 1.0 indicates accelerated aging due to elevated temperature.
    """
    t_use_k = t_use_c + KELVIN_OFFSET
    t_ref_k = t_ref_c + KELVIN_OFFSET

    if t_use_k <= 0 or t_ref_k <= 0:
        return 1.0

    exponent = (activation_energy_ev / BOLTZMANN_K_EV) * (1.0 / t_ref_k - 1.0 / t_use_k)
    # Clip exponent to prevent overflow in extreme theoretical tests
    exponent = max(-20.0, min(20.0, exponent))
    return round(math.exp(exponent), 3)


def evaluate_mission_profile(
    component_name: str,
    part_number: str,
    phases: List[MissionProfilePhase],
    rated_temp_max_c: float = DEFAULT_RATED_TEMP_MAX_C,
    thermal_resistance_c_per_w: float = DEFAULT_THERMAL_RESISTANCE_C_PER_W,
    nominal_life_hours_at_ref: float = DEFAULT_LIFE_HOURS_AT_REFERENCE,
    activation_energy_ev: float = DEFAULT_ACTIVATION_ENERGY_EV,
    target_service_years: int = DEFAULT_TARGET_SERVICE_YEARS,
    apply_mitigation: Optional[str] = None,  # "IMPROVED_COOLING" | "ELECTRICAL_DERATING" | None
) -> MissionProfileEvaluation:
    """
    Comprehensive mission profile evaluation combining 1D thermal resistance,
    Arrhenius acceleration, and Miner's cumulative damage accumulation.
    """
    r_theta = thermal_resistance_c_per_w
    p_multiplier = 1.0

    if apply_mitigation == "IMPROVED_COOLING":
        r_theta = thermal_resistance_c_per_w * 0.65  # 35% thermal resistance improvement (fan/heatsink)
    elif apply_mitigation == "ELECTRICAL_DERATING":
        p_multiplier = 0.75  # 25% lower power dissipation

    phase_results: List[PhaseAnalysisResult] = []
    total_annual_hours = sum(p.annual_hours for p in phases)
    annual_damage = 0.0
    peak_tj = -273.15
    worst_margin = 999.0

    for phase in phases:
        effective_power = phase.power_dissipation_watts * phase.duty_cycle * p_multiplier
        delta_t = effective_power * r_theta
        tj = phase.ambient_temp_c + delta_t
        tj_k = tj + KELVIN_OFFSET
        af = arrhenius_acceleration_factor(t_use_c=tj, t_ref_c=DEFAULT_REFERENCE_TEMP_C, activation_energy_ev=activation_energy_ev)

        # Life at this phase condition: L_j = L_nominal / AF
        life_phase_hours = nominal_life_hours_at_ref / max(0.01, af)
        damage_phase = phase.annual_hours / max(1.0, life_phase_hours)
        annual_damage += damage_phase

        thermal_margin = rated_temp_max_c - tj
        peak_tj = max(peak_tj, tj)
        worst_margin = min(worst_margin, thermal_margin)

        phase_results.append(PhaseAnalysisResult(
            phase_name=phase.name,
            annual_hours=phase.annual_hours,
            ambient_temp_c=phase.ambient_temp_c,
            power_watts=round(effective_power, 3),
            temp_rise_delta_c=round(delta_t, 1),
            junction_temp_c=round(tj, 1),
            junction_temp_k=round(tj_k, 1),
            arrhenius_af=af,
            phase_damage_fraction=round(damage_phase, 6),
            thermal_margin_c=round(thermal_margin, 1),
            is_junction_temp_exceeded=(tj > rated_temp_max_c),
        ))

    # Total lifetime projection
    total_target_hours = total_annual_hours * target_service_years
    life_years = (1.0 / annual_damage) if annual_damage > 0 else 50.0
    total_target_damage = annual_damage * target_service_years
    life_consumption_pct = round(total_target_damage * 100.0, 1)

    # Mitigations comparison (Side-by-Side)
    mitigations = []
    if not apply_mitigation:
        # Calculate baseline vs improved cooling vs electrical derating
        eval_cooling = evaluate_mission_profile(
            component_name, part_number, phases, rated_temp_max_c,
            thermal_resistance_c_per_w, nominal_life_hours_at_ref,
            activation_energy_ev, target_service_years,
            apply_mitigation="IMPROVED_COOLING",
        )
        eval_derating = evaluate_mission_profile(
            component_name, part_number, phases, rated_temp_max_c,
            thermal_resistance_c_per_w, nominal_life_hours_at_ref,
            activation_energy_ev, target_service_years,
            apply_mitigation="ELECTRICAL_DERATING",
        )

        mitigations.append({
            "strategy": "Baseline (Current Operation)",
            "peak_junction_temp_c": round(peak_tj, 1),
            "thermal_margin_c": round(worst_margin, 1),
            "projected_life_years": round(life_years, 1),
            "life_consumption_pct": life_consumption_pct,
            "adequate_for_target": life_consumption_pct <= 100.0,
        })
        mitigations.append({
            "strategy": "Mitigation A: Improved Cooling (35% R_theta reduction)",
            "peak_junction_temp_c": round(eval_cooling.peak_junction_temp_c, 1),
            "thermal_margin_c": round(eval_cooling.worst_thermal_margin_c, 1),
            "projected_life_years": round(eval_cooling.projected_life_years, 1),
            "life_consumption_pct": eval_cooling.life_consumption_over_target_pct,
            "adequate_for_target": eval_cooling.life_consumption_over_target_pct <= 100.0,
        })
        mitigations.append({
            "strategy": "Mitigation B: Electrical Derating (25% power reduction)",
            "peak_junction_temp_c": round(eval_derating.peak_junction_temp_c, 1),
            "thermal_margin_c": round(eval_derating.worst_thermal_margin_c, 1),
            "projected_life_years": round(eval_derating.projected_life_years, 1),
            "life_consumption_pct": eval_derating.life_consumption_over_target_pct,
            "adequate_for_target": eval_derating.life_consumption_over_target_pct <= 100.0,
        })

    assumptions = [
        f"Thermal rise Delta T = P * R_theta with R_theta={r_theta:.1f} °C/W.",
        f"Arrhenius model uses activation energy Ea = {activation_energy_ev:.2f} eV and reference {DEFAULT_REFERENCE_TEMP_C:.1f} °C.",
        "Linear damage accumulation assumes Miner's rule across independent operational phases.",
        "Damage D > 1.0 (or > 100%) represents consumption exceeding nominal rated life expectancy.",
    ]

    return MissionProfileEvaluation(
        component_name=component_name,
        part_number=part_number,
        rated_temp_max_c=rated_temp_max_c,
        thermal_resistance_c_per_w=r_theta,
        nominal_life_hours_at_ref=nominal_life_hours_at_ref,
        activation_energy_ev=activation_energy_ev,
        total_operating_hours_per_year=round(total_annual_hours, 1),
        target_service_years=target_service_years,
        phases=phase_results,
        peak_junction_temp_c=round(peak_tj, 1),
        worst_thermal_margin_c=round(worst_margin, 1),
        annual_cumulative_damage_d=round(annual_damage, 6),
        projected_life_years=round(life_years, 1),
        life_consumption_over_target_pct=life_consumption_pct,
        is_service_life_adequate=(life_consumption_pct <= 100.0 and worst_margin > 0.0),
        mitigation_comparisons=mitigations,
        assumptions=assumptions,
    )


# Standard canonical mission profiles for demonstration
def get_standard_mission_profiles() -> Dict[str, List[MissionProfilePhase]]:
    """Library of standard industrial mission profiles."""
    return {
        "Normal Office / Lab": [
            MissionProfilePhase(name="Active Operation", annual_hours=3000.0, ambient_temp_c=25.0, power_dissipation_watts=1.2, operating_voltage=5.0, operating_current=0.24, duty_cycle=0.8),
            MissionProfilePhase(name="Standby", annual_hours=5760.0, ambient_temp_c=22.0, power_dissipation_watts=0.15, operating_voltage=5.0, operating_current=0.03, duty_cycle=0.1),
        ],
        "High-Temperature Industrial Enclosure": [
            MissionProfilePhase(name="Summer Peak Production", annual_hours=2500.0, ambient_temp_c=65.0, power_dissipation_watts=1.8, operating_voltage=5.2, operating_current=0.35, duty_cycle=1.0, relative_humidity_pct=75.0),
            MissionProfilePhase(name="Standard Production", annual_hours=4500.0, ambient_temp_c=50.0, power_dissipation_watts=1.4, operating_voltage=5.0, operating_current=0.28, duty_cycle=0.9, relative_humidity_pct=60.0),
            MissionProfilePhase(name="Idle Heat Soak", annual_hours=1760.0, ambient_temp_c=45.0, power_dissipation_watts=0.3, operating_voltage=5.0, operating_current=0.06, duty_cycle=0.2),
        ],
        "Harsh Outdoor / Automotive Under-Hood": [
            MissionProfilePhase(name="High Ambient Summer Drive", annual_hours=1200.0, ambient_temp_c=85.0, power_dissipation_watts=2.1, operating_voltage=5.25, operating_current=0.40, duty_cycle=1.0, vibration_g_rms=2.5),
            MissionProfilePhase(name="Moderate Drive", annual_hours=2000.0, ambient_temp_c=55.0, power_dissipation_watts=1.5, operating_voltage=5.0, operating_current=0.30, duty_cycle=0.85, vibration_g_rms=1.5),
            MissionProfilePhase(name="Cold Start Winter", annual_hours=800.0, ambient_temp_c=-20.0, power_dissipation_watts=1.8, operating_voltage=4.8, operating_current=0.38, duty_cycle=0.9),
            MissionProfilePhase(name="Parked Soak", annual_hours=4760.0, ambient_temp_c=35.0, power_dissipation_watts=0.05, operating_voltage=5.0, operating_current=0.01, duty_cycle=0.05),
        ],
    }
