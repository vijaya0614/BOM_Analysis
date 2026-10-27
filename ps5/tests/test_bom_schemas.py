import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.db_models import Base, BomComponentRow, RedesignCostRow, SubstituteComponentRow
from src.schemas import (
    BillOfMaterials,
    BomComponent,
    Criticality,
    LifecycleStatus,
    RedesignCost,
    SubstituteComponent,
)


def sample_bom_line(**overrides):
    data = {
        "part_number": "IRFZ44N",
        "category": "MOSFET",
        "package": "TO-220AB",
        "criticality": "High",
        "qty": 2,
        "unit_cost": 1.25,
        "second_source": True,
        "lead_time_weeks": 8,
        "lifecycle_status": "Active",
        "distributor_stock": 420,
    }
    data.update(overrides)
    return data


def test_bom_component_accepts_enumerated_fields():
    line = BomComponent.model_validate(sample_bom_line())
    assert line.criticality is Criticality.HIGH
    assert line.lifecycle_status is LifecycleStatus.ACTIVE
    assert line.second_source is True
    assert line.extended_cost == 2.5


def test_bom_component_rejects_invalid_criticality_and_lifecycle():
    with pytest.raises(ValidationError):
        BomComponent.model_validate(sample_bom_line(criticality="Severe"))
    with pytest.raises(ValidationError):
        BomComponent.model_validate(sample_bom_line(lifecycle_status="EOL"))


def test_substitute_component_exposes_parametric_specs():
    candidate = SubstituteComponent(
        part_number="IRFZ44NS",
        original_part_number="IRFZ44N",
        category="MOSFET",
        package="D2PAK",
        voltage=55.0,
        current=49.0,
        tolerance=5.0,
    )
    specs = candidate.parametric_specs
    assert specs.voltage == 55.0
    assert specs.current == 49.0
    assert specs.tolerance == 5.0


def test_redesign_cost_totals_requalification_and_holding():
    cost = RedesignCost(
        original_part_number="IRFZ44N",
        substitute_part_number="IRFZ44NS",
        requalification_expense=1500.0,
        holding_cost=0.0,
        engineering_hours=12,
        hourly_rate=85,
        last_time_buy_qty=200,
        holding_cost_per_unit_per_week=0.02,
        holding_weeks=10,
    )
    assert cost.labor_cost == 1020.0
    assert cost.computed_holding_cost == 40.0
    assert cost.total_redesign_cost == 2560.0


def test_bill_of_materials_rolls_up_extended_cost():
    bom = BillOfMaterials(
        name="mini_smart_cooling_controller",
        components=[
            BomComponent.model_validate(sample_bom_line()),
            BomComponent.model_validate(sample_bom_line(part_number="0805-10K", category="Resistor", package="0805", criticality="Low", qty=10, unit_cost=0.02)),
        ],
    )
    assert bom.total_unit_cost == 2.7


def test_sqlalchemy_round_trip_with_pydantic():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    line = BomComponent.model_validate(sample_bom_line())
    substitute = SubstituteComponent(
        part_number="IRFZ44NS",
        original_part_number=line.part_number,
        category=line.category,
        package="D2PAK",
        voltage=55.0,
        current=49.0,
        tolerance=5.0,
        unit_cost=1.40,
        second_source=True,
        lifecycle_status=LifecycleStatus.ACTIVE,
        lead_time_weeks=4,
        distributor_stock=90,
    )
    redesign = RedesignCost(
        original_part_number=line.part_number,
        substitute_part_number=substitute.part_number,
        requalification_expense=1500.0,
        holding_cost=250.0,
    )

    with Session(engine) as session:
        row = BomComponentRow(**line.model_dump(exclude={"extended_cost"}))
        session.add(row)
        session.flush()
        sub_row = SubstituteComponentRow(original_id=row.id, **substitute.model_dump())
        session.add(sub_row)
        session.flush()
        cost_row = RedesignCostRow(
            original_id=row.id,
            substitute_id=sub_row.id,
            **redesign.model_dump(exclude={"labor_cost", "computed_holding_cost", "total_redesign_cost"}),
        )
        session.add(cost_row)
        session.commit()

        loaded = session.scalars(select(BomComponentRow)).one()
        restored = BomComponent.model_validate(loaded)
        assert restored.part_number == "IRFZ44N"
        assert restored.distributor_stock == 420
        assert loaded.substitutes[0].voltage == 55.0
        assert loaded.redesign_costs[0].requalification_expense == 1500.0
        assert loaded.redesign_costs[0].holding_cost == 250.0
