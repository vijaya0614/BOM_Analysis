from src.redesign_decision import (
    DESIGN_REFRESH,
    DROP_IN,
    LTB,
    MitigationPart,
    compare_strategies,
    optimize_obsolescence_plan,
    recommend_strategy,
)
from src.schemas import BomComponent, RedesignCost


def _cheap_dropin() -> MitigationPart:
    return MitigationPart(
        part_number="REG-5V",
        demand_per_year=10,
        unit_cost=8.0,
        holding_rate=0.40,
        discount_rate=0.08,
        horizon_years=5,
        substitute_unit_cost=1.20,
        refresh_unit_cost=3.50,
        dropin_requalification=25.0,
        refresh_requalification=8000.0,
        dropin_hours=1,
        refresh_hours=80,
        hourly_rate=90.0,
        dropin_delay_years=1,
        refresh_year=3,
    )


def _expensive_requal_ltb() -> MitigationPart:
    return MitigationPart(
        part_number="ASIC-1",
        demand_per_year=5,
        unit_cost=20.0,
        holding_rate=0.05,
        discount_rate=0.10,
        horizon_years=5,
        substitute_unit_cost=22.0,
        refresh_unit_cost=18.0,
        dropin_requalification=40000.0,
        refresh_requalification=90000.0,
        dropin_hours=200,
        refresh_hours=400,
        hourly_rate=150.0,
        dropin_delay_years=1,
        refresh_year=2,
    )


def test_compare_strategies_returns_three_npvs():
    ranked = compare_strategies(_cheap_dropin())
    names = {item.strategy for item in ranked}
    assert names == {LTB, DROP_IN, DESIGN_REFRESH}
    assert all(item.total_npv >= 0 for item in ranked if item.feasible)
    best = recommend_strategy(_cheap_dropin())
    assert best.strategy == DROP_IN
    assert best.requalification_npv > 0


def test_low_holding_prefers_last_time_buy():
    best = recommend_strategy(_expensive_requal_ltb())
    assert best.strategy == LTB
    assert best.quantity == 25
    assert best.holding_npv > 0
    assert best.requalification_npv == 0


def test_design_refresh_wins_when_unit_cost_falls_and_nre_is_shared_in_mip():
    cheap_refresh = MitigationPart(
        part_number="MCU-1",
        demand_per_year=20,
        unit_cost=12.0,
        holding_rate=0.25,
        discount_rate=0.08,
        horizon_years=5,
        substitute_unit_cost=11.5,
        refresh_unit_cost=2.0,
        dropin_requalification=3000.0,
        refresh_requalification=200.0,
        dropin_hours=30,
        refresh_hours=10,
        hourly_rate=80.0,
        dropin_delay_years=1,
        refresh_year=1,
    )
    best = recommend_strategy(cheap_refresh)
    assert best.strategy == DESIGN_REFRESH


def test_integer_program_matches_independent_argmin():
    parts = [_cheap_dropin(), _expensive_requal_ltb()]
    result = optimize_obsolescence_plan(parts, shared_refresh_nre=0.0)
    assert result.status == "Optimal"
    assert result.assignments["REG-5V"] == DROP_IN
    assert result.assignments["ASIC-1"] == LTB
    assert result.quantities["ASIC-1"] == 25
    assert result.objective_npv is not None and result.objective_npv > 0


def test_engineering_capacity_blocks_requalification():
    busy = MitigationPart(
        part_number="FPGA-1",
        demand_per_year=8,
        unit_cost=45.0,
        holding_rate=0.40,
        discount_rate=0.08,
        horizon_years=4,
        substitute_unit_cost=4.0,
        refresh_unit_cost=3.0,
        dropin_requalification=40.0,
        refresh_requalification=60.0,
        dropin_hours=50,
        refresh_hours=90,
        hourly_rate=40.0,
        dropin_delay_years=1,
        refresh_year=2,
    )
    unconstrained = optimize_obsolescence_plan([busy])
    constrained = optimize_obsolescence_plan([busy], engineering_hours_capacity=5)
    assert unconstrained.status == "Optimal"
    assert constrained.status == "Optimal"
    assert constrained.assignments["FPGA-1"] == LTB
    assert unconstrained.assignments["FPGA-1"] != LTB


def test_from_bom_component_and_redesign_cost():
    component = BomComponent(
        part_number="IRFZ44N",
        category="MOSFET",
        package="TO-220AB",
        criticality="High",
        qty=4,
        unit_cost=1.25,
        second_source=True,
        lead_time_weeks=8,
        lifecycle_status="NRND",
        distributor_stock=20,
    )
    redesign = RedesignCost(
        original_part_number="IRFZ44N",
        substitute_part_number="IRFZ44NS",
        requalification_expense=1500.0,
        holding_cost=0.0,
        engineering_hours=12,
        hourly_rate=85,
        last_time_buy_qty=200,
        holding_cost_per_unit_per_week=0.002,
        holding_weeks=10,
    )
    part = MitigationPart.from_component(component, redesign, substitute_unit_cost=1.4)
    ranked = compare_strategies(part)
    assert len(ranked) == 3
    assert part.dropin_available is True
    result = optimize_obsolescence_plan([part])
    assert result.status == "Optimal"
    assert result.assignments["IRFZ44N"] in {LTB, DROP_IN, DESIGN_REFRESH}
