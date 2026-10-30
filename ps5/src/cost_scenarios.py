"""Cost Savings and Lifecycle Economics Scenario Engine.

Compares four obsolescence and supply-chain strategies:
A. Continue & Monitor (Baseline)
B. Purchase & Hold Inventory in Advance (Last-Time Buy / LTB)
C. Qualify and Use Alternative Component (Drop-in Substitute)
D. Redesign Affected Subsystem (Design Refresh / Architecture Spin)

Formulas:
- C_total = C_parts + C_redesign + C_qualification + C_inventory + C_delay + C_disruption
- Net Savings = C_baseline - C_alternative
- Savings % = 100 * (C_baseline - C_alternative) / C_baseline
- Expected Disruption Cost = P(disruption) * Cost(disruption)
- Break-Even Analysis over production volume and unit price difference.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_LTB_PRICE_MULTIPLIER = 1.05
DEFAULT_SUBSTITUTE_PRICE_MULTIPLIER = 0.90
DEFAULT_REDESIGN_PRICE_MULTIPLIER = 0.70
SUBSTITUTE_RESIDUAL_DISRUPTION_PROBABILITY = 0.05


@dataclass
class StrategyCostBreakdown:
    strategy_id: str  # "STRATEGY_A" | "STRATEGY_B" | "STRATEGY_C" | "STRATEGY_D"
    strategy_name: str
    parts_purchase_cost: float
    redesign_engineering_cost: float
    qualification_testing_cost: float
    inventory_holding_cost: float
    delay_and_scrap_cost: float
    expected_disruption_cost: float
    total_cost: float
    net_savings_vs_baseline: float
    savings_percentage: float
    break_even_volume_units: Optional[int]
    financial_risk_level: str
    pros: List[str]
    cons: List[str]
    traceable_formula: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CostScenarioComparisonReport:
    part_number: str
    annual_production_volume: int
    horizon_years: int
    total_units_required: int
    baseline_part_cost: float
    strategies: Dict[str, StrategyCostBreakdown]
    recommended_strategy_id: str
    recommended_strategy_name: str
    decision_rationale: str
    break_even_summary: str
    assumptions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["strategies"] = {k: v.to_dict() for k, v in self.strategies.items()}
        return res


def evaluate_cost_scenarios(
    part_number: str,
    annual_volume: int = 5000,
    horizon_years: int = 5,
    current_unit_price: float = 3.50,
    ltb_unit_price: Optional[float] = None,
    substitute_unit_price: Optional[float] = None,
    redesign_unit_price: Optional[float] = None,
    annual_holding_cost_rate: float = 0.18,  # 18% carrying cost/year
    discount_rate: float = 0.08,             # 8% discount rate
    substitute_qualification_cost: float = 4500.0,
    redesign_engineering_hours: float = 80.0,
    hourly_engineering_rate: float = 125.0,
    redesign_tooling_and_qual_cost: float = 18000.0,
    baseline_disruption_probability: float = 0.55,  # 55% chance of shortage/line stop
    disruption_cost_impact: float = 40000.0,       # $40k shutdown/rework/delay impact
) -> CostScenarioComparisonReport:
    """
    Computes rigorous lifecycle financial comparisons across the 4 core strategies.
    Avoids double-counting and provides formulaic transparency for all line items.
    """
    total_units = annual_volume * horizon_years

    p_orig = current_unit_price
    p_ltb = ltb_unit_price if ltb_unit_price is not None else (p_orig * DEFAULT_LTB_PRICE_MULTIPLIER)
    p_sub = substitute_unit_price if substitute_unit_price is not None else (p_orig * DEFAULT_SUBSTITUTE_PRICE_MULTIPLIER)
    p_redesign = redesign_unit_price if redesign_unit_price is not None else (p_orig * DEFAULT_REDESIGN_PRICE_MULTIPLIER)

    # --- Strategy A: Continue & Monitor (Baseline) ---
    c_parts_a = round(total_units * p_orig, 2)
    c_redesign_a = 0.0
    c_qual_a = 0.0
    c_inv_a = 0.0
    c_delay_a = 0.0
    c_disrupt_a = round(baseline_disruption_probability * disruption_cost_impact, 2)
    c_total_a = round(c_parts_a + c_disrupt_a, 2)

    # --- Strategy B: Last-Time Buy (LTB) in Advance ---
    c_parts_b = round(total_units * p_ltb, 2)
    c_redesign_b = 0.0
    c_qual_b = 0.0
    # Average inventory holding cost over depletion horizon:
    # Holding cost NPV = Purchase_value * holding_rate * (Horizon / 2) discounted
    avg_inventory_years = horizon_years / 2.0
    c_inv_b = round(c_parts_b * annual_holding_cost_rate * avg_inventory_years * (1.0 / (1.0 + discount_rate)), 2)
    c_delay_b = 0.0
    c_disrupt_b = 0.0  # Buffer fully covers production demand
    c_total_b = round(c_parts_b + c_inv_b, 2)

    # --- Strategy C: Qualify Alternative Component (Drop-In Substitute) ---
    c_parts_c = round(total_units * p_sub, 2)
    c_redesign_c = 0.0  # Drop-in fit: 0 PCB change
    c_qual_c = round(substitute_qualification_cost, 2)
    c_inv_c = 0.0  # Normal standard lead-time procurement
    c_delay_c = 0.0
    c_disrupt_c = round(SUBSTITUTE_RESIDUAL_DISRUPTION_PROBABILITY * disruption_cost_impact, 2)
    c_total_c = round(c_parts_c + c_qual_c + c_disrupt_c, 2)

    # --- Strategy D: Redesign Subsystem ---
    c_parts_d = round(total_units * p_redesign, 2)
    eng_cost_d = round(redesign_engineering_hours * hourly_engineering_rate, 2)
    c_redesign_d = eng_cost_d
    c_qual_d = round(redesign_tooling_and_qual_cost, 2)
    c_inv_d = 0.0
    c_delay_d = 0.0
    c_disrupt_d = 0.0  # Scenario assumption; no supplier evidence is modeled here.
    c_total_d = round(c_parts_d + c_redesign_d + c_qual_d, 2)

    # Compile strategies and net savings
    strategies_dict: Dict[str, StrategyCostBreakdown] = {}

    # Strategy A
    strategies_dict["STRATEGY_A"] = StrategyCostBreakdown(
        strategy_id="STRATEGY_A",
        strategy_name="Continue & Monitor (Status Quo)",
        parts_purchase_cost=c_parts_a,
        redesign_engineering_cost=c_redesign_a,
        qualification_testing_cost=c_qual_a,
        inventory_holding_cost=c_inv_a,
        delay_and_scrap_cost=c_delay_a,
        expected_disruption_cost=c_disrupt_a,
        total_cost=c_total_a,
        net_savings_vs_baseline=0.0,
        savings_percentage=0.0,
        break_even_volume_units=None,
        financial_risk_level="HIGH_EXPOSURE",
        pros=["Zero upfront capital commitment", "Zero engineering overhead immediately"],
        cons=["High unhedged factory disruption exposure", "Risk of sudden broker gouging or line shutdown"],
        traceable_formula=f"Parts ({total_units} * ${p_orig:.2f}) + Expected Disruption ({baseline_disruption_probability*100:.0f}% * ${disruption_cost_impact:,.0f}) = ${c_total_a:,.2f}",
    )

    # Strategy B
    net_sav_b = round(c_total_a - c_total_b, 2)
    sav_pct_b = round((net_sav_b / c_total_a) * 100.0, 1) if c_total_a > 0 else 0.0
    strategies_dict["STRATEGY_B"] = StrategyCostBreakdown(
        strategy_id="STRATEGY_B",
        strategy_name="Advance Inventory (Last-Time Buy)",
        parts_purchase_cost=c_parts_b,
        redesign_engineering_cost=c_redesign_b,
        qualification_testing_cost=c_qual_b,
        inventory_holding_cost=c_inv_b,
        delay_and_scrap_cost=c_delay_b,
        expected_disruption_cost=c_disrupt_b,
        total_cost=c_total_b,
        net_savings_vs_baseline=net_sav_b,
        savings_percentage=sav_pct_b,
        break_even_volume_units=None,
        financial_risk_level="CAPITAL_INTENSIVE",
        pros=["Assumes purchased inventory fully covers modeled production demand", "Eliminates engineering redesign effort entirely"],
        cons=["Ties up substantial working capital upfront", "Carrying/holding cost and obsolescence scrap risk"],
        traceable_formula=f"Parts (${c_parts_b:,.2f}) + Carrying Cost (18%/yr mid-depletion ${c_inv_b:,.2f}) = ${c_total_b:,.2f}",
    )

    # Strategy C
    net_sav_c = round(c_total_a - c_total_c, 2)
    sav_pct_c = round((net_sav_c / c_total_a) * 100.0, 1) if c_total_a > 0 else 0.0
    # Break-even volume: C_fixed / (P_orig - P_sub)
    be_vol_c = None
    if p_orig > p_sub:
        be_vol_c = int(math.ceil(c_qual_c / (p_orig - p_sub)))

    strategies_dict["STRATEGY_C"] = StrategyCostBreakdown(
        strategy_id="STRATEGY_C",
        strategy_name="Qualify Drop-In Alternative",
        parts_purchase_cost=c_parts_c,
        redesign_engineering_cost=c_redesign_c,
        qualification_testing_cost=c_qual_c,
        inventory_holding_cost=c_inv_c,
        delay_and_scrap_cost=c_delay_c,
        expected_disruption_cost=c_disrupt_c,
        total_cost=c_total_c,
        net_savings_vs_baseline=net_sav_c,
        savings_percentage=sav_pct_c,
        break_even_volume_units=be_vol_c,
        financial_risk_level="OPTIMAL_BALANCED",
        pros=["Moderate one-time qualification fee", "Assumed lower unit component price", "Zero PCB redesign"],
        cons=["Requires engineering bench verification and sample validation"],
        traceable_formula=f"Parts (${c_parts_c:,.2f}) + Qual (${c_qual_c:,.2f}) + Residual Disruption (${c_disrupt_c:,.2f}) = ${c_total_c:,.2f}",
    )

    # Strategy D
    net_sav_d = round(c_total_a - c_total_d, 2)
    sav_pct_d = round((net_sav_d / c_total_a) * 100.0, 1) if c_total_a > 0 else 0.0
    # Break even volume vs baseline: (Redesign + Tooling) / (P_orig - P_redesign)
    be_vol_d = None
    delta_p_d = p_orig - p_redesign
    if delta_p_d > 0:
        be_vol_d = int(math.ceil((c_redesign_d + c_qual_d) / delta_p_d))

    strategies_dict["STRATEGY_D"] = StrategyCostBreakdown(
        strategy_id="STRATEGY_D",
        strategy_name="Subsystem Architecture Redesign",
        parts_purchase_cost=c_parts_d,
        redesign_engineering_cost=c_redesign_d,
        qualification_testing_cost=c_qual_d,
        inventory_holding_cost=c_inv_d,
        delay_and_scrap_cost=c_delay_d,
        expected_disruption_cost=c_disrupt_d,
        total_cost=c_total_d,
        net_savings_vs_baseline=net_sav_d,
        savings_percentage=sav_pct_d,
        break_even_volume_units=be_vol_d,
        financial_risk_level="HIGH_UPFRONT_INVESTMENT",
        pros=["Modernizes the architecture", "Assumed BOM cost reduction at scale"],
        cons=["High upfront NRE and lab re-certification required", "Engineering resource bottleneck"],
        traceable_formula=f"Parts (${c_parts_d:,.2f}) + NRE Engineering (${c_redesign_d:,.2f}) + Tooling/Cert (${c_qual_d:,.2f}) = ${c_total_d:,.2f}",
    )

    # Select best strategy by minimum total cost
    sorted_strats = sorted(strategies_dict.values(), key=lambda s: s.total_cost)
    best = sorted_strats[0]

    be_summary = (
        f"Strategy C breaks even at {be_vol_c:,} units (qual fee recouped via BOM savings). "
        if be_vol_c
        else "Strategy C qualification is amortized immediately. "
    )
    if be_vol_d:
        be_summary += f"Strategy D redesign breaks even at {be_vol_d:,} units."

    rationale = (
        f"{best.strategy_name} provides the lowest total lifecycle cost of ${best.total_cost:,.2f}, "
        f"saving ${best.net_savings_vs_baseline:,.2f} ({best.savings_percentage}%) compared to status quo baseline. "
        f"This accounts for unit purchase costs, inventory holding, qualification, and expected disruption risk."
    )

    assumptions = [
        f"Analysis modeled over {annual_volume:,} units/year across {horizon_years} years ({total_units:,} units total).",
        f"Inventory holding cost rate modeled at {annual_holding_cost_rate*100:.0f}% annually with linear drawdown.",
        f"Baseline unmitigated line-stop probability estimated at {baseline_disruption_probability*100:.0f}%.",
        f"When omitted, LTB, substitute, and redesign unit prices are modeled at {DEFAULT_LTB_PRICE_MULTIPLIER:.2f}x, {DEFAULT_SUBSTITUTE_PRICE_MULTIPLIER:.2f}x, and {DEFAULT_REDESIGN_PRICE_MULTIPLIER:.2f}x the original price; these are placeholders, not market quotes.",
        f"Substitute residual disruption probability is fixed at {SUBSTITUTE_RESIDUAL_DISRUPTION_PROBABILITY:.0%}; redesign and fully covered LTB use zero residual disruption cost by assumption.",
        "All calculations use deterministic, traceable accounting formulas without hidden multipliers.",
    ]

    return CostScenarioComparisonReport(
        part_number=part_number,
        annual_production_volume=annual_volume,
        horizon_years=horizon_years,
        total_units_required=total_units,
        baseline_part_cost=p_orig,
        strategies=strategies_dict,
        recommended_strategy_id=best.strategy_id,
        recommended_strategy_name=best.strategy_name,
        decision_rationale=rationale,
        break_even_summary=be_summary,
        assumptions=assumptions,
    )
