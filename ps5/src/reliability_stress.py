"""Part-stress reliability (MIL-HDBK-217F) replacing linear MTBF scaling.

Failure rate λ_p is assembled from handbook π-factors, not from
MTBF_use = MTBF_ref * T_ref / T_use. Thermal, environment, quality,
voltage/current stress, switching activity, and recovery/aging guardbands
are applied as multiplicative corrections on λ (failures per 10^6 hours).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

# Boltzmann constant in eV/K (used only for optional Arrhenius checks).
K_EV = 8.617333262145e-5
T_REF_K = 298.15  # 25 °C, 217F reference temperature

# 217F empirical temperature exponents (Notice 2, semiconductor π_T).
BJT_TEMP_CONST_K = 2114.0  # §6.4 silicon bipolar
FET_TEMP_CONST_K = 1925.0  # §6.6 / §6.7 FET / MOSFET


class Environment(str, Enum):
    GB = "GB"  # Ground, Benign
    GF = "GF"  # Ground, Fixed
    GM = "GM"  # Ground, Mobile
    NS = "NS"  # Naval, Sheltered
    NU = "NU"  # Naval, Unsheltered
    AIC = "AIC"  # Airborne, Inhabited Cargo
    AIF = "AIF"  # Airborne, Inhabited Fighter
    AUC = "AUC"  # Airborne, Uninhabited Cargo
    AUF = "AUF"  # Airborne, Uninhabited Fighter
    ARW = "ARW"  # Airborne, Rotary Winged
    SF = "SF"  # Space, Flight
    MF = "MF"  # Missile, Flight
    ML = "ML"  # Missile, Launch
    CL = "CL"  # Cannon, Launch


class Quality(str, Enum):
    JANTXV = "JANTXV"
    JANTX = "JANTX"
    JAN = "JAN"
    LOWER = "LOWER"
    COMMERCIAL = "COMMERCIAL"
    ER_D = "ER_D"
    ER_R = "ER_R"
    ER_P = "ER_P"
    MIL = "MIL"


class CapacitorStyle(str, Enum):
    CERAMIC = "CERAMIC"
    TANTALUM = "TANTALUM"
    ALUMINUM = "ALUMINUM"


class SemiconductorStyle(str, Enum):
    BJT = "BJT"
    MOSFET = "MOSFET"
    JFET = "JFET"
    DIODE = "DIODE"


# π_E — MIL-HDBK-217F Notice 2 environmental factors.
PI_E_SEMICONDUCTOR = {
    Environment.GB: 1.0,
    Environment.GF: 2.0,
    Environment.GM: 4.0,
    Environment.NS: 4.0,
    Environment.NU: 6.0,
    Environment.AIC: 4.0,
    Environment.AIF: 7.0,
    Environment.AUC: 6.0,
    Environment.AUF: 10.0,
    Environment.ARW: 12.0,
    Environment.SF: 0.50,
    Environment.MF: 9.0,
    Environment.ML: 17.0,
    Environment.CL: 220.0,
}

PI_E_CAPACITOR = {
    Environment.GB: 1.0,
    Environment.GF: 2.0,
    Environment.GM: 10.0,
    Environment.NS: 5.0,
    Environment.NU: 12.0,
    Environment.AIC: 4.0,
    Environment.AIF: 8.0,
    Environment.AUC: 6.0,
    Environment.AUF: 17.0,
    Environment.ARW: 19.0,
    Environment.SF: 0.50,
    Environment.MF: 13.0,
    Environment.ML: 24.0,
    Environment.CL: 450.0,
}

PI_Q_SEMICONDUCTOR = {
    Quality.JANTXV: 0.70,
    Quality.JANTX: 1.00,
    Quality.JAN: 2.40,
    Quality.LOWER: 5.50,
    Quality.COMMERCIAL: 8.00,
    Quality.MIL: 2.40,
    Quality.ER_D: 0.70,
    Quality.ER_R: 1.00,
    Quality.ER_P: 3.00,
}

PI_Q_CAPACITOR = {
    Quality.ER_D: 0.030,
    Quality.ER_R: 0.10,
    Quality.ER_P: 0.30,
    Quality.MIL: 1.00,
    Quality.JAN: 1.00,
    Quality.JANTX: 0.30,
    Quality.JANTXV: 0.10,
    Quality.LOWER: 3.00,
    Quality.COMMERCIAL: 10.00,
}


class ReliabilityModelError(ValueError):
    pass


def linear_mtbf_scale(mtbf_ref_hours: float, t_ref_c: float, t_use_c: float) -> float:
    """
    Naive linear (or inverse-kelvin) MTBF scaling. Kept only as a contrast:
    part-stress analysis must not use this relationship.
    """
    if t_use_c <= -273.15:
        raise ReliabilityModelError("Use temperature must be above absolute zero.")
    return mtbf_ref_hours * ((t_ref_c + 273.15) / (t_use_c + 273.15))


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _kelvin(temp_c: float) -> float:
    return temp_c + 273.15


def stress_ratio(applied: float, rated: float) -> float:
    if rated <= 0:
        raise ReliabilityModelError("Rated stress must be positive.")
    return max(0.0, applied / rated)


def junction_temperature_c(
    ambient_c: float,
    power_w: float = 0.0,
    theta_ja_c_per_w: float = 0.0,
    case_c: Optional[float] = None,
    junction_c: Optional[float] = None,
) -> float:
    if junction_c is not None:
        return junction_c
    if case_c is not None:
        return case_c + max(0.0, power_w) * max(0.0, theta_ja_c_per_w) * 0.25
    return ambient_c + max(0.0, power_w) * max(0.0, theta_ja_c_per_w)


def environmental_stress_factor(environment: Environment, family: str) -> float:
    table = PI_E_CAPACITOR if family == "capacitor" else PI_E_SEMICONDUCTOR
    try:
        return table[environment]
    except KeyError as exc:
        raise ReliabilityModelError(f"Unsupported environment {environment}") from exc


def quality_factor(quality: Quality, family: str) -> float:
    table = PI_Q_CAPACITOR if family == "capacitor" else PI_Q_SEMICONDUCTOR
    try:
        return table[quality]
    except KeyError as exc:
        raise ReliabilityModelError(f"Unsupported quality {quality}") from exc


def thermal_derating_factor(
    temp_c: float,
    temp_rated_max_c: float,
    recommended_margin_c: float = 30.0,
) -> float:
    """
    Correction on λ for operating relative to a derating envelope
    (typically 30 °C below T_jmax or capacitor T_max). Extra margin reduces
    λ modestly; violating the envelope increases λ. This is not linear MTBF scaling.
    """
    headroom = temp_rated_max_c - temp_c
    if headroom >= recommended_margin_c:
        extra = headroom - recommended_margin_c
        return max(0.70, 1.0 - 0.008 * extra)
    shortage = recommended_margin_c - headroom
    return 1.0 + 0.04 * shortage + 0.002 * max(0.0, -headroom) ** 2


def aging_guardband(
    *,
    duty_cycle: float,
    switching_hz: float,
    recovery_fraction: float,
    calendar_age_years: float,
    reference_switching_hz: float,
) -> Dict[str, float]:
    """
    Switching activity raises wear (hot-carrier / dielectric cycling).
    Recovery_fraction is calendar time at negligible stress (off / cool),
    which partially anneals NBTI/PBTI and capacitor dielectric absorption.
    Calendar age applies a power-law wear-out guardband on λ, not on MTBF.
    """
    duty = _clamp(duty_cycle, 0.0, 1.0)
    recovery = _clamp(recovery_fraction, 0.0, 1.0)
    age = max(0.0, calendar_age_years)
    f_norm = min(max(0.0, switching_hz) / max(reference_switching_hz, 1e-6), 8.0)

    switching = 1.0 + 0.40 * duty * math.sqrt(f_norm)
    recovery_credit = 1.0 - 0.30 * recovery * (1.0 - 0.5 * duty)
    aging = 1.0 + 0.06 * age + 0.01 * age * duty
    combined = switching * recovery_credit * aging
    return {
        "pi_switching": switching,
        "pi_recovery": recovery_credit,
        "pi_aging": aging,
        "pi_guardband": combined,
    }


@dataclass
class StressConditions:
    ambient_c: float = 25.0
    case_c: Optional[float] = None
    junction_c: Optional[float] = None
    theta_ja_c_per_w: float = 0.0
    power_w: float = 0.0
    voltage_applied: float = 0.0
    voltage_rated: float = 1.0
    current_applied: Optional[float] = None
    current_rated: Optional[float] = None
    environment: Environment = Environment.GB
    quality: Quality = Quality.COMMERCIAL
    duty_cycle: float = 0.5
    switching_hz: float = 0.0
    recovery_fraction: float = 0.0
    calendar_age_years: float = 0.0
    temp_rated_max_c: float = 125.0
    capacitance_uf: Optional[float] = None
    series_resistance_ohm: Optional[float] = None
    rated_power_w: Optional[float] = None


@dataclass
class PartStressResult:
    family: str
    style: str
    lambda_base: float
    pi_factors: Dict[str, float]
    lambda_per_million_hours: float
    fit: float
    mtbf_hours: float
    junction_or_case_c: float
    model: str
    notes: list = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        return {
            "family": self.family,
            "style": self.style,
            "lambda_base": self.lambda_base,
            "pi_factors": self.pi_factors,
            "lambda_per_million_hours": self.lambda_per_million_hours,
            "fit": self.fit,
            "mtbf_hours": None if math.isinf(self.mtbf_hours) else self.mtbf_hours,
            "junction_or_case_c": self.junction_or_case_c,
            "model": self.model,
            "notes": self.notes,
        }


def _finalize(lambda_p: float, **kwargs) -> PartStressResult:
    lam = max(lambda_p, 0.0)
    mtbf = math.inf if lam == 0 else 1.0e6 / lam
    return PartStressResult(lambda_per_million_hours=lam, fit=lam * 1000.0, mtbf_hours=mtbf, **kwargs)


def pi_temperature_semiconductor(temp_c: float, const_k: float) -> float:
    """217F π_T = exp(-A (1/Tj - 1/298))."""
    t_k = _kelvin(temp_c)
    if t_k <= 0:
        raise ReliabilityModelError("Temperature must be above 0 K.")
    return math.exp(-const_k * (1.0 / t_k - 1.0 / T_REF_K))


def capacitor_base_rate(style: CapacitorStyle, temp_c: float, voltage_ratio: float, capacitance_uf: float) -> float:
    """
    Style-specific λ_b including 217F voltage/temperature construction.
    Ceramic/tantalum/aluminum forms follow Notice 2 §10.
    """
    s = max(0.0, voltage_ratio)
    t_k = _kelvin(temp_c)
    c = max(capacitance_uf, 1e-6)

    if style is CapacitorStyle.CERAMIC:
        # §10.1 / 10.2 ceramic: λ_b · (S^n + 1) · strong temperature exponential.
        return 0.00032 * ((s / 0.6) ** 5 + 1.0) * math.exp(((t_k / 358.0) ** 9.0) - 1.0) * (c ** 0.09)
    if style is CapacitorStyle.TANTALUM:
        # §10.8 solid tantalum.
        return 0.00012 * ((s ** 3) + 1.0) * math.exp(0.15 * ((t_k / 398.0) ** 6.0)) * (c ** 0.12)
    if style is CapacitorStyle.ALUMINUM:
        # §10.15 aluminum electrolytic.
        return 0.0028 * ((s ** 3) + 1.0) * math.exp(0.44 * ((t_k / 358.0) ** 5.9)) * (c ** 0.23)
    raise ReliabilityModelError(f"Unsupported capacitor style {style}")


def pi_series_resistance(style: CapacitorStyle, rs_ohm: Optional[float], voltage_applied: float) -> float:
    """π_SR circuit-resistance factor (tantalum); 1.0 for ceramic/aluminum unless specified."""
    if style is not CapacitorStyle.TANTALUM or rs_ohm is None or voltage_applied <= 0:
        return 1.0
    cr = rs_ohm / voltage_applied
    if cr >= 0.8:
        return 0.66
    if cr >= 0.3:
        return 1.0
    if cr >= 0.1:
        return 1.3
    return 2.0


def part_stress_capacitor(
    style: CapacitorStyle,
    conditions: StressConditions,
) -> PartStressResult:
    if conditions.capacitance_uf is None or conditions.capacitance_uf <= 0:
        raise ReliabilityModelError("Capacitance in μF is required for capacitor part-stress analysis.")

    temp_c = junction_temperature_c(
        conditions.ambient_c,
        conditions.power_w,
        conditions.theta_ja_c_per_w,
        conditions.case_c,
        conditions.junction_c,
    )
    s = stress_ratio(conditions.voltage_applied, conditions.voltage_rated)
    lam_b = capacitor_base_rate(style, temp_c, s, conditions.capacitance_uf)
    pi_sr = pi_series_resistance(style, conditions.series_resistance_ohm, conditions.voltage_applied)
    pi_e = environmental_stress_factor(conditions.environment, "capacitor")
    pi_q = quality_factor(conditions.quality, "capacitor")
    pi_therm = thermal_derating_factor(temp_c, conditions.temp_rated_max_c, recommended_margin_c=20.0)
    guard = aging_guardband(
        duty_cycle=conditions.duty_cycle,
        switching_hz=conditions.switching_hz,
        recovery_fraction=conditions.recovery_fraction,
        calendar_age_years=conditions.calendar_age_years,
        reference_switching_hz=120.0,
    )

    pi = {
        "pi_SR": pi_sr,
        "pi_E": pi_e,
        "pi_Q": pi_q,
        "pi_thermal_derating": pi_therm,
        **guard,
    }
    lam_p = lam_b * pi_sr * pi_e * pi_q * pi_therm * guard["pi_guardband"]
    return _finalize(
        lam_p,
        family="capacitor",
        style=style.value,
        lambda_base=lam_b,
        pi_factors=pi,
        junction_or_case_c=temp_c,
        model="MIL-HDBK-217F Notice 2 §10 part-stress (non-linear)",
        notes=[
            "Linear MTBF scaling is not used.",
            "Voltage and temperature enter λ_b exponentially / as a power law.",
        ],
    )


def semiconductor_base_rate(style: SemiconductorStyle) -> float:
    """λ_b in failures / 10^6 hours (217F discrete tables, commercial-order magnitudes)."""
    return {
        SemiconductorStyle.BJT: 0.00074,
        SemiconductorStyle.MOSFET: 0.012,
        SemiconductorStyle.JFET: 0.0047,
        SemiconductorStyle.DIODE: 0.0038,
    }[style]


def pi_application_switching(style: SemiconductorStyle, duty_cycle: float, switching_hz: float) -> float:
    """
    217F π_A: switching applications are lower than linear/saturated analog.
    Duty/frequency interpolate between switching (~0.70) and linear (~1.5–2.0).
    """
    duty = _clamp(duty_cycle, 0.0, 1.0)
    if style is SemiconductorStyle.DIODE:
        return 0.50 + 0.60 * duty
    switching = 0.70
    linear = 1.50 if style is SemiconductorStyle.MOSFET else 1.50
    analog_heavy = 1.0 - duty * min(switching_hz / 1.0e3, 1.0) if switching_hz else (1.0 - duty)
    analog_heavy = _clamp(analog_heavy, 0.0, 1.0)
    return switching + (linear - switching) * analog_heavy


def pi_power_rating(rated_power_w: Optional[float]) -> float:
    """217F π_R ~ P_r^0.37 for bipolar power rating, unity if unknown/low."""
    if rated_power_w is None or rated_power_w <= 0:
        return 1.0
    return max(0.43, rated_power_w ** 0.37)


def pi_voltage_stress_semiconductor(voltage_ratio: float, style: SemiconductorStyle) -> float:
    """217F π_S ≈ 0.045 exp(3.1 Vs) for bipolar; FETs use a milder exponential."""
    vs = _clamp(voltage_ratio, 0.0, 1.2)
    if style in {SemiconductorStyle.MOSFET, SemiconductorStyle.JFET}:
        return math.exp(1.2 * vs) / math.exp(1.2 * 0.5)
    return 0.045 * math.exp(3.1 * vs)


def part_stress_semiconductor(
    style: SemiconductorStyle,
    conditions: StressConditions,
) -> PartStressResult:
    tj = junction_temperature_c(
        conditions.ambient_c,
        conditions.power_w,
        conditions.theta_ja_c_per_w,
        conditions.case_c,
        conditions.junction_c,
    )
    const_k = FET_TEMP_CONST_K if style in {SemiconductorStyle.MOSFET, SemiconductorStyle.JFET} else BJT_TEMP_CONST_K
    lam_b = semiconductor_base_rate(style)
    pi_t = pi_temperature_semiconductor(tj, const_k)
    pi_a = pi_application_switching(style, conditions.duty_cycle, conditions.switching_hz)
    pi_r = pi_power_rating(conditions.rated_power_w)
    vs = stress_ratio(conditions.voltage_applied, conditions.voltage_rated)
    pi_s = pi_voltage_stress_semiconductor(vs, style)
    pi_e = environmental_stress_factor(conditions.environment, "semiconductor")
    pi_q = quality_factor(conditions.quality, "semiconductor")
    pi_therm = thermal_derating_factor(tj, conditions.temp_rated_max_c, recommended_margin_c=30.0)
    guard = aging_guardband(
        duty_cycle=conditions.duty_cycle,
        switching_hz=conditions.switching_hz,
        recovery_fraction=conditions.recovery_fraction,
        calendar_age_years=conditions.calendar_age_years,
        reference_switching_hz=10_000.0,
    )

    pi = {
        "pi_T": pi_t,
        "pi_A": pi_a,
        "pi_R": pi_r,
        "pi_S": pi_s,
        "pi_E": pi_e,
        "pi_Q": pi_q,
        "pi_thermal_derating": pi_therm,
        **guard,
    }
    lam_p = lam_b * pi_t * pi_a * pi_r * pi_s * pi_e * pi_q * pi_therm * guard["pi_guardband"]
    return _finalize(
        lam_p,
        family="semiconductor",
        style=style.value,
        lambda_base=lam_b,
        pi_factors=pi,
        junction_or_case_c=tj,
        model="MIL-HDBK-217F Notice 2 §6 part-stress (non-linear)",
        notes=[
            "Linear MTBF scaling is not used.",
            "π_T is the 217F exponential in 1/Tj; thermal derating is a separate envelope correction.",
        ],
    )


def analyze_part_stress(
    family: str,
    style: str,
    conditions: StressConditions,
) -> PartStressResult:
    family_key = family.strip().lower()
    style_key = style.strip().upper()
    if family_key in {"capacitor", "cap"}:
        return part_stress_capacitor(CapacitorStyle[style_key], conditions)
    if family_key in {"semiconductor", "semi", "transistor", "mosfet", "diode"}:
        aliases = {"TRANSISTOR": "BJT", "FET": "JFET"}
        return part_stress_semiconductor(SemiconductorStyle[aliases.get(style_key, style_key)], conditions)
    raise ReliabilityModelError(f"Unsupported part family '{family}'")
