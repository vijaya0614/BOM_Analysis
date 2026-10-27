"""Obsolescence mitigation: compare LTB, drop-in, and design refresh, then solve a MIP."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

import pulp

from src.schemas import BomComponent, RedesignCost

LTB = "LTB"
DROP_IN = "DROP_IN"
DESIGN_REFRESH = "DESIGN_REFRESH"
STRATEGIES = (LTB, DROP_IN, DESIGN_REFRESH)


def pv(amount: float, rate: float, year: int) -> float:
    """Present value of a cash flow at the end of `year` (year 0 is immediate)."""
    if year <= 0:
        return amount
    return amount / ((1.0 + rate) ** year)


def annuity_pv(payment: float, rate: float, start_year: int, end_year: int) -> float:
    """NPV of `payment` at the end of each year in [start_year, end_year] inclusive."""
    if end_year < start_year:
        return 0.0
    return sum(pv(payment, rate, year) for year in range(start_year, end_year + 1))


def holding_npv_coefficient(years: int, holding_rate: float, discount_rate: float) -> float:
    """
    NPV of inventory carrying cost per dollar of a last-time buy that depletes
    linearly over `years`. Mid-year remaining-stock convention.
    """
    if years <= 0 or holding_rate <= 0:
        return 0.0
    total = 0.0
    for year in range(1, years + 1):
        remaining_fraction = max(0.0, 1.0 - (year - 0.5) / years)
        total += holding_rate * remaining_fraction * pv(1.0, discount_rate, year)
    return total


@dataclass
class MitigationPart:
    """Economics for one at-risk BOM line over a planning horizon."""

    part_number: str
    demand_per_year: int
    unit_cost: float
    holding_rate: float
    discount_rate: float
    horizon_years: int = 5
    substitute_unit_cost: Optional[float] = None
    refresh_unit_cost: Optional[float] = None
    dropin_requalification: float = 0.0
    refresh_requalification: float = 0.0
    dropin_hours: float = 0.0
    refresh_hours: float = 0.0
    hourly_rate: float = 0.0
    dropin_delay_years: int = 1
    refresh_year: int = 2
    dropin_available: bool = True
    refresh_available: bool = True

    def __post_init__(self) -> None:
        if self.demand_per_year < 0:
            raise ValueError("demand_per_year must be >= 0")
        if self.horizon_years < 1:
            raise ValueError("horizon_years must be >= 1")
        if self.refresh_year < 1:
            raise ValueError("refresh_year must be >= 1")
        if self.substitute_unit_cost is None:
            self.substitute_unit_cost = self.unit_cost
        if self.refresh_unit_cost is None:
            self.refresh_unit_cost = self.unit_cost

    @classmethod
    def from_component(
        cls,
        component: BomComponent,
        redesign: Optional[RedesignCost] = None,
        *,
        demand_per_year: Optional[int] = None,
        discount_rate: float = 0.08,
        holding_rate: float = 0.18,
        horizon_years: int = 5,
        substitute_unit_cost: Optional[float] = None,
        refresh_unit_cost: Optional[float] = None,
        dropin_delay_years: int = 1,
        refresh_year: int = 2,
    ) -> "MitigationPart":
        annual_demand = demand_per_year if demand_per_year is not None else max(1, component.qty)
        dropin_requal = 0.0
        refresh_requal = 0.0
        hours_drop = 0.0
        hours_ref = 0.0
        hourly = 0.0
        if redesign is not None:
            refresh_requal = redesign.requalification_expense
            dropin_requal = 0.35 * redesign.requalification_expense
            hours_ref = redesign.engineering_hours
            hours_drop = 0.25 * redesign.engineering_hours
            hourly = redesign.hourly_rate
            if redesign.holding_cost_per_unit_per_week and component.unit_cost:
                holding_rate = min(
                    0.8,
                    (redesign.holding_cost_per_unit_per_week * 52.0) / max(component.unit_cost, 1e-9),
                )
        return cls(
            part_number=component.part_number,
            demand_per_year=annual_demand,
            unit_cost=component.unit_cost,
            holding_rate=holding_rate,
            discount_rate=discount_rate,
            horizon_years=horizon_years,
            substitute_unit_cost=substitute_unit_cost,
            refresh_unit_cost=refresh_unit_cost,
            dropin_requalification=dropin_requal,
            refresh_requalification=refresh_requal,
            dropin_hours=hours_drop,
            refresh_hours=hours_ref,
            hourly_rate=hourly,
            dropin_delay_years=dropin_delay_years,
            refresh_year=min(refresh_year, horizon_years),
            dropin_available=component.second_source or substitute_unit_cost is not None,
        )


@dataclass
class StrategyCost:
    strategy: str
    total_npv: float
    purchase_npv: float
    holding_npv: float
    requalification_npv: float
    quantity: int
    feasible: bool = True
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        return {
            "strategy": self.strategy,
            "total_npv": round(self.total_npv, 4),
            "purchase_npv": round(self.purchase_npv, 4),
            "holding_npv": round(self.holding_npv, 4),
            "requalification_npv": round(self.requalification_npv, 4),
            "quantity": self.quantity,
            "feasible": self.feasible,
            "notes": self.notes,
        }


def _ltb_cost(part: MitigationPart) -> StrategyCost:
    qty = part.demand_per_year * part.horizon_years
    hold_coef = holding_npv_coefficient(part.horizon_years, part.holding_rate, part.discount_rate)
    purchase = part.unit_cost * qty
    holding = purchase * hold_coef
    return StrategyCost(
        strategy=LTB,
        total_npv=purchase + holding,
        purchase_npv=purchase,
        holding_npv=holding,
        requalification_npv=0.0,
        quantity=qty,
        notes=["Buy remaining horizon demand now; no requalification."],
    )


def _bridge_then_run_rate(
    part: MitigationPart,
    *,
    strategy: str,
    delay_years: int,
    later_unit_cost: float,
    requal_cash: float,
    hours: float,
    available: bool,
) -> StrategyCost:
    delay = max(0, min(delay_years, part.horizon_years))
    bridge_qty = part.demand_per_year * delay
    hold_coef = holding_npv_coefficient(delay, part.holding_rate, part.discount_rate) if delay else 0.0
    bridge_purchase = part.unit_cost * bridge_qty
    holding = bridge_purchase * hold_coef
    run_rate = annuity_pv(
        part.demand_per_year * later_unit_cost,
        part.discount_rate,
        start_year=delay + 1,
        end_year=part.horizon_years,
    )
    requal = pv(requal_cash + hours * part.hourly_rate, part.discount_rate, delay)
    notes = [
        f"Bridge {delay} year(s) on the incumbent, then run-rate at ${later_unit_cost:.4f}.",
        f"Requalification effort {hours:.1f} h at ${part.hourly_rate:.2f}/h.",
    ]
    if not available:
        return StrategyCost(
            strategy=strategy,
            total_npv=float("inf"),
            purchase_npv=bridge_purchase + run_rate,
            holding_npv=holding,
            requalification_npv=requal,
            quantity=bridge_qty,
            feasible=False,
            notes=["Strategy unavailable for this part."],
        )
    return StrategyCost(
        strategy=strategy,
        total_npv=bridge_purchase + holding + run_rate + requal,
        purchase_npv=bridge_purchase + run_rate,
        holding_npv=holding,
        requalification_npv=requal,
        quantity=bridge_qty,
        notes=notes,
    )


def drop_in_cost(part: MitigationPart) -> StrategyCost:
    return _bridge_then_run_rate(
        part,
        strategy=DROP_IN,
        delay_years=part.dropin_delay_years,
        later_unit_cost=part.substitute_unit_cost or part.unit_cost,
        requal_cash=part.dropin_requalification,
        hours=part.dropin_hours,
        available=part.dropin_available,
    )


def design_refresh_cost(part: MitigationPart) -> StrategyCost:
    return _bridge_then_run_rate(
        part,
        strategy=DESIGN_REFRESH,
        delay_years=part.refresh_year,
        later_unit_cost=part.refresh_unit_cost or part.unit_cost,
        requal_cash=part.refresh_requalification,
        hours=part.refresh_hours,
        available=part.refresh_available,
    )


def compare_strategies(part: MitigationPart) -> List[StrategyCost]:
    """Expected NPV of LTB, drop-in substitution, and planned design refresh."""
    options = [_ltb_cost(part), drop_in_cost(part), design_refresh_cost(part)]
    return sorted(options, key=lambda item: (not item.feasible, item.total_npv))


def recommend_strategy(part: MitigationPart) -> StrategyCost:
    feasible = [item for item in compare_strategies(part) if item.feasible]
    if not feasible:
        raise ValueError(f"No feasible mitigation strategy for {part.part_number}")
    return feasible[0]


@dataclass
class OptimizationResult:
    status: str
    objective_npv: Optional[float]
    assignments: Dict[str, str]
    quantities: Dict[str, int]
    program_refresh: bool
    strategy_costs: Dict[str, List[Dict[str, object]]]
    solver: str = "PULP_CBC_CMD"

    def as_dict(self) -> Dict[str, object]:
        return {
            "status": self.status,
            "objective_npv": None if self.objective_npv is None else round(self.objective_npv, 4),
            "assignments": self.assignments,
            "quantities": self.quantities,
            "program_refresh": self.program_refresh,
            "strategy_costs": self.strategy_costs,
            "solver": self.solver,
        }


def optimize_obsolescence_plan(
    parts: Sequence[MitigationPart],
    *,
    engineering_hours_capacity: Optional[float] = None,
    shared_refresh_nre: float = 0.0,
    time_limit_seconds: int = 10,
) -> OptimizationResult:
    """
    Binary/integer program: assign each part exactly one mitigation strategy
    and size last-time / bridge buys to cover demand.

    Minimize NPV of purchases + holding + discounted requalification (+ shared refresh NRE).
    """
    if not parts:
        raise ValueError("At least one part is required.")

    comparisons = {part.part_number: compare_strategies(part) for part in parts}

    problem = pulp.LpProblem("obsolescence_management_cost", pulp.LpMinimize)
    choose: Dict[tuple, pulp.LpVariable] = {}
    qty_ltb: Dict[str, pulp.LpVariable] = {}
    qty_drop: Dict[str, pulp.LpVariable] = {}
    qty_refresh: Dict[str, pulp.LpVariable] = {}

    for part in parts:
        name = part.part_number
        for strategy in STRATEGIES:
            choose[name, strategy] = pulp.LpVariable(f"use_{name}_{strategy}", cat="Binary")
        qty_ltb[name] = pulp.LpVariable(f"q_ltb_{name}", lowBound=0, cat="Integer")
        qty_drop[name] = pulp.LpVariable(f"q_drop_{name}", lowBound=0, cat="Integer")
        qty_refresh[name] = pulp.LpVariable(f"q_refresh_{name}", lowBound=0, cat="Integer")

        problem += pulp.lpSum(choose[name, strategy] for strategy in STRATEGIES) == 1
        if not part.dropin_available:
            problem += choose[name, DROP_IN] == 0
        if not part.refresh_available:
            problem += choose[name, DESIGN_REFRESH] == 0

        ltb_need = part.demand_per_year * part.horizon_years
        drop_need = part.demand_per_year * min(part.dropin_delay_years, part.horizon_years)
        refresh_need = part.demand_per_year * min(part.refresh_year, part.horizon_years)

        problem += qty_ltb[name] >= ltb_need * choose[name, LTB]
        problem += qty_ltb[name] <= ltb_need * choose[name, LTB]
        problem += qty_drop[name] >= drop_need * choose[name, DROP_IN]
        problem += qty_drop[name] <= drop_need * choose[name, DROP_IN]
        problem += qty_refresh[name] >= refresh_need * choose[name, DESIGN_REFRESH]
        problem += qty_refresh[name] <= refresh_need * choose[name, DESIGN_REFRESH]

    program_refresh = pulp.LpVariable("program_design_refresh", cat="Binary")
    for part in parts:
        problem += program_refresh >= choose[part.part_number, DESIGN_REFRESH]

    if engineering_hours_capacity is not None:
        effort = pulp.lpSum(
            part.dropin_hours * choose[part.part_number, DROP_IN]
            + part.refresh_hours * choose[part.part_number, DESIGN_REFRESH]
            for part in parts
        )
        problem += effort <= engineering_hours_capacity, "engineering_capacity"

    objective_terms = [shared_refresh_nre * program_refresh]
    for part in parts:
        name = part.part_number
        ltb_hold = holding_npv_coefficient(part.horizon_years, part.holding_rate, part.discount_rate)
        drop_delay = min(part.dropin_delay_years, part.horizon_years)
        ref_delay = min(part.refresh_year, part.horizon_years)
        drop_hold = holding_npv_coefficient(drop_delay, part.holding_rate, part.discount_rate)
        ref_hold = holding_npv_coefficient(ref_delay, part.holding_rate, part.discount_rate)

        drop_run = annuity_pv(
            part.demand_per_year * (part.substitute_unit_cost or part.unit_cost),
            part.discount_rate,
            drop_delay + 1,
            part.horizon_years,
        )
        ref_run = annuity_pv(
            part.demand_per_year * (part.refresh_unit_cost or part.unit_cost),
            part.discount_rate,
            ref_delay + 1,
            part.horizon_years,
        )
        drop_requal = pv(
            part.dropin_requalification + part.dropin_hours * part.hourly_rate,
            part.discount_rate,
            drop_delay,
        )
        ref_requal = pv(
            part.refresh_requalification + part.refresh_hours * part.hourly_rate,
            part.discount_rate,
            ref_delay,
        )

        objective_terms.append(part.unit_cost * (1.0 + ltb_hold) * qty_ltb[name])
        objective_terms.append(part.unit_cost * (1.0 + drop_hold) * qty_drop[name])
        objective_terms.append(part.unit_cost * (1.0 + ref_hold) * qty_refresh[name])
        objective_terms.append(drop_run * choose[name, DROP_IN])
        objective_terms.append(ref_run * choose[name, DESIGN_REFRESH])
        objective_terms.append(drop_requal * choose[name, DROP_IN])
        objective_terms.append(ref_requal * choose[name, DESIGN_REFRESH])

    problem += pulp.lpSum(objective_terms)
    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit_seconds)
    status_code = problem.solve(solver)
    status = pulp.LpStatus[status_code]

    assignments: Dict[str, str] = {}
    quantities: Dict[str, int] = {}
    if status == "Optimal":
        for part in parts:
            name = part.part_number
            chosen = next(strategy for strategy in STRATEGIES if pulp.value(choose[name, strategy]) >= 0.5)
            assignments[name] = chosen
            if chosen == LTB:
                quantities[name] = int(round(pulp.value(qty_ltb[name]) or 0))
            elif chosen == DROP_IN:
                quantities[name] = int(round(pulp.value(qty_drop[name]) or 0))
            else:
                quantities[name] = int(round(pulp.value(qty_refresh[name]) or 0))
        objective = float(pulp.value(problem.objective) or 0.0)
        used_refresh = bool(round(pulp.value(program_refresh) or 0))
    else:
        objective = None
        used_refresh = False

    return OptimizationResult(
        status=status,
        objective_npv=objective,
        assignments=assignments,
        quantities=quantities,
        program_refresh=used_refresh,
        strategy_costs={
            part_number: [item.as_dict() for item in costs] for part_number, costs in comparisons.items()
        },
    )


def optimize_from_bom(
    components: Iterable[BomComponent],
    redesign_by_part: Optional[Mapping[str, RedesignCost]] = None,
    **kwargs,
) -> OptimizationResult:
    redesign_by_part = redesign_by_part or {}
    parts = [
        MitigationPart.from_component(component, redesign_by_part.get(component.part_number))
        for component in components
    ]
    return optimize_obsolescence_plan(parts, **kwargs)
