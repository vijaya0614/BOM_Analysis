"""Electrical Compatibility and Engineering Tolerance Analysis Engine.

Implements:
8.1 Worst-Case Circuit Analysis (WCCA) for extreme parameter bounds
8.2 Root-Sum-Square (RSS) statistical tolerance analysis:
    sigma_y = sqrt(sum ((df/dx_i) * sigma_i)^2)
8.3 Reproducible Monte Carlo simulation with deterministic random seeds
    and binned distribution histograms for charting.
8.4 Sensitivity analysis (variance contribution of each parameter)
8.5 Component engineering margins (voltage, current, power, thermal).
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

DEFAULT_SAMPLE_COUNT = 2000
DEFAULT_RANDOM_SEED = 42
HISTOGRAM_BIN_COUNT = 15


@dataclass
class CircuitParameter:
    name: str
    nominal: float
    tolerance_pct: float  # e.g. 5.0 for +/- 5%
    distribution: str = "NORMAL"  # "NORMAL" (3-sigma = tolerance) | "UNIFORM"
    unit: str = ""
    description: str = ""

    @property
    def sigma(self) -> float:
        """Standard deviation assuming tolerance is 3-sigma."""
        tol_val = abs(self.nominal * (self.tolerance_pct / 100.0))
        if self.distribution == "NORMAL":
            return tol_val / 3.0
        # For uniform distribution on [-a, a], sigma = a / sqrt(3)
        return tol_val / math.sqrt(3.0)

    @property
    def min_val(self) -> float:
        return self.nominal * (1.0 - self.tolerance_pct / 100.0)

    @property
    def max_val(self) -> float:
        return self.nominal * (1.0 + self.tolerance_pct / 100.0)


@dataclass
class MonteCarloHistogramBin:
    bin_start: float
    bin_end: float
    bin_center: float
    count: int
    frequency: float


@dataclass
class ToleranceAnalysisResult:
    analysis_name: str
    nominal_output: float
    output_unit: str
    worst_case_min: float
    worst_case_max: float
    rss_sigma: float
    rss_3sigma_min: float
    rss_3sigma_max: float
    monte_carlo_samples: int
    random_seed: int
    monte_carlo_mean: float
    monte_carlo_std: float
    monte_carlo_min: float
    monte_carlo_max: float
    monte_carlo_p5: float
    monte_carlo_p95: float
    spec_min_limit: Optional[float]
    spec_max_limit: Optional[float]
    monte_carlo_violation_rate_pct: float
    histogram_bins: List[MonteCarloHistogramBin]
    sensitivity_ranking: List[Dict[str, Any]]
    assumptions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["histogram_bins"] = [asdict(b) for b in self.histogram_bins]
        res["model_metadata"] = {
            "monte_carlo_samples": self.monte_carlo_samples,
            "random_seed": self.random_seed,
            "histogram_bin_count": HISTOGRAM_BIN_COUNT,
            "normal_tolerance_interpretation": "plus_or_minus_3_sigma",
            "uniform_tolerance_interpretation": "uniform_over_min_max_bounds",
            "rss_assumes_independent_parameter_errors": True,
            "calibration_status": "INPUT_TOLERANCE_ASSUMPTION_BASED",
        }
        return res


@dataclass
class EngineeringMargins:
    operating_voltage: Optional[float]
    rated_voltage: Optional[float]
    voltage_margin_pct: Optional[float]
    operating_current: Optional[float]
    rated_current: Optional[float]
    current_margin_pct: Optional[float]
    operating_power: Optional[float]
    rated_power: Optional[float]
    power_margin_pct: Optional[float]
    operating_temp_c: Optional[float]
    rated_temp_max_c: Optional[float]
    thermal_margin_c: Optional[float]
    derating_compliant: bool
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_engineering_margins(
    v_op: Optional[float] = None,
    v_max: Optional[float] = None,
    i_op: Optional[float] = None,
    i_max: Optional[float] = None,
    p_op: Optional[float] = None,
    p_max: Optional[float] = None,
    t_op: Optional[float] = None,
    t_max: Optional[float] = None,
) -> EngineeringMargins:
    """Calculate voltage, current, power, and thermal safety margins against ratings."""
    warnings: List[str] = []
    compliant = True

    # Voltage margin: (V_max - V_op) / V_max
    v_margin = None
    if v_op is not None and v_max is not None and v_max > 0:
        v_margin = round(((v_max - v_op) / v_max) * 100.0, 1)
        if v_op > v_max:
            warnings.append(f"Operating voltage {v_op}V exceeds absolute maximum rating {v_max}V.")
            compliant = False
        elif v_margin < 20.0:
            warnings.append(f"Voltage derating margin ({v_margin}%) is below recommended 20% guideline.")

    # Current margin: (I_max - I_op) / I_max
    i_margin = None
    if i_op is not None and i_max is not None and i_max > 0:
        i_margin = round(((i_max - i_op) / i_max) * 100.0, 1)
        if i_op > i_max:
            warnings.append(f"Continuous current {i_op}A exceeds rated current {i_max}A.")
            compliant = False
        elif i_margin < 20.0:
            warnings.append(f"Current margin ({i_margin}%) is below 20% guideline.")

    # Power margin: (P_max - P_op) / P_max
    p_margin = None
    if p_op is not None and p_max is not None and p_max > 0:
        p_margin = round(((p_max - p_op) / p_max) * 100.0, 1)
        if p_op > p_max:
            warnings.append(f"Power dissipation {p_op}W exceeds rated power {p_max}W.")
            compliant = False
        elif p_margin < 30.0:
            warnings.append(f"Power derating margin ({p_margin}%) is below recommended 30% guideline.")

    # Thermal margin: T_max - T_op
    t_margin = None
    if t_op is not None and t_max is not None:
        t_margin = round(t_max - t_op, 1)
        if t_op > t_max:
            warnings.append(f"Operating junction temperature {t_op}°C exceeds maximum rating {t_max}°C.")
            compliant = False
        elif t_margin < 15.0:
            warnings.append(f"Thermal margin ({t_margin}°C) is narrow (< 15°C buffer).")

    return EngineeringMargins(
        operating_voltage=v_op,
        rated_voltage=v_max,
        voltage_margin_pct=v_margin,
        operating_current=i_op,
        rated_current=i_max,
        current_margin_pct=i_margin,
        operating_power=p_op,
        rated_power=p_max,
        power_margin_pct=p_margin,
        operating_temp_c=t_op,
        rated_temp_max_c=t_max,
        thermal_margin_c=t_margin,
        derating_compliant=compliant,
        warnings=warnings,
    )


def run_circuit_tolerance_analysis(
    circuit_name: str,
    parameters: List[CircuitParameter],
    transfer_function: Callable[[Dict[str, float]], float],
    output_unit: str = "V",
    spec_min_limit: Optional[float] = None,
    spec_max_limit: Optional[float] = None,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    random_seed: int = DEFAULT_RANDOM_SEED,
) -> ToleranceAnalysisResult:
    """
    Executes comprehensive tolerance analysis:
    - Nominal output
    - Worst-Case Analysis (evaluating corners)
    - Root-Sum-Square (numerical partial derivatives)
    - Deterministic Monte Carlo simulation
    - Sensitivity ranking
    """
    nom_dict = {p.name: p.nominal for p in parameters}
    nominal_out = transfer_function(nom_dict)

    # 1. RSS Analysis via numerical finite-difference partial derivatives:
    # df/dx_i ~ (f(x_i + h) - f(x_i - h)) / (2h)
    sum_var = 0.0
    sensitivity_raw: List[Tuple[str, float, float]] = []

    for p in parameters:
        h = max(1e-6, abs(p.nominal * 0.001))
        p_plus = dict(nom_dict)
        p_plus[p.name] = p.nominal + h
        p_minus = dict(nom_dict)
        p_minus[p.name] = p.nominal - h

        df_dx = (transfer_function(p_plus) - transfer_function(p_minus)) / (2.0 * h)
        param_sigma = p.sigma
        component_var = (df_dx * param_sigma) ** 2
        sum_var += component_var
        sensitivity_raw.append((p.name, df_dx, component_var))

    rss_sigma = math.sqrt(sum_var) if sum_var > 0 else 0.0
    rss_3sigma_min = round(nominal_out - 3.0 * rss_sigma, 4)
    rss_3sigma_max = round(nominal_out + 3.0 * rss_sigma, 4)

    # Sensitivity ranking: contribution to output variance
    sens_ranked: List[Dict[str, Any]] = []
    for name, df_dx, comp_var in sorted(sensitivity_raw, key=lambda x: x[2], reverse=True):
        pct_contrib = (comp_var / sum_var * 100.0) if sum_var > 0 else 0.0
        sens_ranked.append({
            "parameter": name,
            "sensitivity_derivative": round(df_dx, 4),
            "variance_contribution_pct": round(pct_contrib, 1),
        })

    # 2. Worst-Case Analysis:
    # Evaluate parameter corners based on derivative direction
    corner_min_dict: Dict[str, float] = {}
    corner_max_dict: Dict[str, float] = {}
    for p in parameters:
        df_dx = next((s[1] for s in sensitivity_raw if s[0] == p.name), 0.0)
        if df_dx >= 0:
            corner_min_dict[p.name] = p.min_val
            corner_max_dict[p.name] = p.max_val
        else:
            corner_min_dict[p.name] = p.max_val
            corner_max_dict[p.name] = p.min_val

    wc_min = round(transfer_function(corner_min_dict), 4)
    wc_max = round(transfer_function(corner_max_dict), 4)

    # 3. Monte Carlo Simulation:
    # Use deterministic random seed for 100% reproducible demo
    rng = random.Random(random_seed)
    simulated_values: List[float] = []

    for _ in range(sample_count):
        sample_params: Dict[str, float] = {}
        for p in parameters:
            if p.distribution == "NORMAL":
                sample_params[p.name] = rng.gauss(p.nominal, p.sigma)
            else:
                sample_params[p.name] = rng.uniform(p.min_val, p.max_val)
        simulated_values.append(transfer_function(sample_params))

    simulated_values.sort()
    mc_mean = sum(simulated_values) / sample_count
    mc_var = sum((v - mc_mean) ** 2 for v in simulated_values) / max(1, sample_count - 1)
    mc_std = math.sqrt(mc_var)
    mc_min = simulated_values[0]
    mc_max = simulated_values[-1]
    p5_idx = int(0.05 * sample_count)
    p95_idx = int(0.95 * sample_count)
    mc_p5 = simulated_values[p5_idx]
    mc_p95 = simulated_values[p95_idx]

    # Calculate violations
    violations = 0
    for v in simulated_values:
        if spec_min_limit is not None and v < spec_min_limit:
            violations += 1
        elif spec_max_limit is not None and v > spec_max_limit:
            violations += 1
    violation_rate = round((violations / float(sample_count)) * 100.0, 2)

    # Generate 15 histogram bins for frontend visualization
    num_bins = HISTOGRAM_BIN_COUNT
    span = max(1e-6, mc_max - mc_min)
    bin_width = span / num_bins
    bins: List[MonteCarloHistogramBin] = []

    for i in range(num_bins):
        b_start = mc_min + i * bin_width
        b_end = b_start + bin_width
        b_center = (b_start + b_end) / 2.0
        # Include upper boundary in last bin
        if i == num_bins - 1:
            cnt = sum(1 for v in simulated_values if b_start <= v <= b_end + 1e-9)
        else:
            cnt = sum(1 for v in simulated_values if b_start <= v < b_end)
        bins.append(MonteCarloHistogramBin(
            bin_start=round(b_start, 4),
            bin_end=round(b_end, 4),
            bin_center=round(b_center, 4),
            count=cnt,
            frequency=round(cnt / float(sample_count), 4),
        ))

    assumptions = [
        f"Monte Carlo executed with {sample_count} samples and deterministic seed {random_seed}.",
        "Normal parameter distributions assume catalog tolerance represents 3-sigma variation.",
        "Worst-case corners evaluated at parameter extremes along gradient directions.",
        "Linearized RSS assumes parameter errors are mutually independent.",
    ]

    return ToleranceAnalysisResult(
        analysis_name=circuit_name,
        nominal_output=round(nominal_out, 4),
        output_unit=output_unit,
        worst_case_min=wc_min,
        worst_case_max=wc_max,
        rss_sigma=round(rss_sigma, 4),
        rss_3sigma_min=rss_3sigma_min,
        rss_3sigma_max=rss_3sigma_max,
        monte_carlo_samples=sample_count,
        random_seed=random_seed,
        monte_carlo_mean=round(mc_mean, 4),
        monte_carlo_std=round(mc_std, 4),
        monte_carlo_min=round(mc_min, 4),
        monte_carlo_max=round(mc_max, 4),
        monte_carlo_p5=round(mc_p5, 4),
        monte_carlo_p95=round(mc_p95, 4),
        spec_min_limit=spec_min_limit,
        spec_max_limit=spec_max_limit,
        monte_carlo_violation_rate_pct=violation_rate,
        histogram_bins=bins,
        sensitivity_ranking=sens_ranked,
        assumptions=assumptions,
    )


# Standard canonical electronics circuits for immediate analysis
def voltage_divider_analysis(
    r1_ohms: float = 10000.0,
    r1_tol_pct: float = 1.0,
    r2_ohms: float = 10000.0,
    r2_tol_pct: float = 1.0,
    vin_volts: float = 5.0,
    vin_tol_pct: float = 2.0,
    v_target_min: float = 2.35,
    v_target_max: float = 2.65,
    samples: int = 2000,
) -> ToleranceAnalysisResult:
    """Analyze a standard precision resistive voltage divider: Vout = Vin * (R2 / (R1 + R2))."""
    params = [
        CircuitParameter(name="R1", nominal=r1_ohms, tolerance_pct=r1_tol_pct, unit="Ω", description="High-side resistor"),
        CircuitParameter(name="R2", nominal=r2_ohms, tolerance_pct=r2_tol_pct, unit="Ω", description="Low-side resistor"),
        CircuitParameter(name="Vin", nominal=vin_volts, tolerance_pct=vin_tol_pct, unit="V", description="Input supply rail"),
    ]

    def vdiv_transfer(p: Dict[str, float]) -> float:
        return p["Vin"] * (p["R2"] / (p["R1"] + p["R2"]))

    return run_circuit_tolerance_analysis(
        circuit_name="Precision Voltage Divider Output",
        parameters=params,
        transfer_function=vdiv_transfer,
        output_unit="V",
        spec_min_limit=v_target_min,
        spec_max_limit=v_target_max,
        sample_count=samples,
    )


def buck_regulator_vout_analysis(
    vref_volts: float = 0.80,
    vref_tol_pct: float = 1.5,
    r_top_ohms: float = 52300.0,
    r_top_tol_pct: float = 1.0,
    r_bot_ohms: float = 10000.0,
    r_bot_tol_pct: float = 1.0,
    target_vout_volts: float = 5.0,
    spec_window_pct: float = 4.0,  # +/- 4% regulation window
    samples: int = 2000,
) -> ToleranceAnalysisResult:
    """Analyze Buck Regulator Feedback Network: Vout = Vref * (1 + R_top / R_bot)."""
    params = [
        CircuitParameter(name="Vref", nominal=vref_volts, tolerance_pct=vref_tol_pct, unit="V", description="Internal bandgap reference"),
        CircuitParameter(name="R_top", nominal=r_top_ohms, tolerance_pct=r_top_tol_pct, unit="Ω", description="Upper feedback resistor"),
        CircuitParameter(name="R_bot", nominal=r_bot_ohms, tolerance_pct=r_bot_tol_pct, unit="Ω", description="Lower feedback resistor"),
    ]

    def buck_vout(p: Dict[str, float]) -> float:
        return p["Vref"] * (1.0 + p["R_top"] / p["R_bot"])

    nom = vref_volts * (1.0 + r_top_ohms / r_bot_ohms)
    win = nom * (spec_window_pct / 100.0)

    return run_circuit_tolerance_analysis(
        circuit_name="Buck Converter Output Voltage (Feedback Loop)",
        parameters=params,
        transfer_function=buck_vout,
        output_unit="V",
        spec_min_limit=round(nom - win, 3),
        spec_max_limit=round(nom + win, 3),
        sample_count=samples,
    )
