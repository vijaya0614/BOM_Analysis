"""Pydantic models for an electronic Bill of Materials (BOM)."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class Criticality(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class LifecycleStatus(str, Enum):
    ACTIVE = "Active"
    NRND = "NRND"
    OBSOLETE = "Obsolete"


class ParametricSpecs(BaseModel):
    """Electrical / parametric envelope used when ranking substitute parts."""

    model_config = ConfigDict(extra="forbid")

    voltage: Optional[float] = Field(default=None, ge=0, description="Rated or operating voltage (V)")
    current: Optional[float] = Field(default=None, ge=0, description="Rated or operating current (A)")
    tolerance: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Parametric tolerance as a percentage (e.g. 1.0 for 1%)",
    )


class BomComponent(BaseModel):
    """One line on an electronic BOM with supply-chain attributes."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    part_number: str = Field(min_length=1)
    category: str = Field(min_length=1)
    package: str = Field(min_length=1)
    criticality: Criticality
    qty: int = Field(gt=0)
    unit_cost: float = Field(ge=0)
    second_source: bool
    lead_time_weeks: int = Field(ge=0)
    lifecycle_status: LifecycleStatus
    distributor_stock: int = Field(ge=0)

    @field_validator("part_number", "category", "package", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @computed_field
    @property
    def extended_cost(self) -> float:
        return round(self.qty * self.unit_cost, 4)


class SubstituteComponent(BaseModel):
    """Alternate MPN that can replace a BOM line, with parametric specs."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    part_number: str = Field(min_length=1)
    original_part_number: str = Field(min_length=1)
    category: str = Field(min_length=1)
    package: str = Field(min_length=1)
    manufacturer: Optional[str] = None
    second_source: bool = True
    lifecycle_status: LifecycleStatus = LifecycleStatus.ACTIVE
    lead_time_weeks: int = Field(default=0, ge=0)
    distributor_stock: int = Field(default=0, ge=0)
    unit_cost: float = Field(default=0.0, ge=0)
    voltage: Optional[float] = Field(default=None, ge=0)
    current: Optional[float] = Field(default=None, ge=0)
    tolerance: Optional[float] = Field(default=None, ge=0, le=100)

    @property
    def parametric_specs(self) -> ParametricSpecs:
        return ParametricSpecs(
            voltage=self.voltage,
            current=self.current,
            tolerance=self.tolerance,
        )


class RedesignCost(BaseModel):
    """Cost of swapping a BOM part: requalification spend plus inventory holding."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    original_part_number: str = Field(min_length=1)
    substitute_part_number: Optional[str] = None
    requalification_expense: float = Field(
        ge=0,
        description="Lab, NRE, firmware, and certification spend to qualify a substitute",
    )
    holding_cost: float = Field(
        ge=0,
        description="Carrying cost of last-time-buy or buffer inventory while redesign proceeds",
    )
    engineering_hours: float = Field(default=0.0, ge=0)
    hourly_rate: float = Field(default=0.0, ge=0)
    last_time_buy_qty: int = Field(default=0, ge=0)
    holding_cost_per_unit_per_week: float = Field(default=0.0, ge=0)
    holding_weeks: int = Field(default=0, ge=0)

    @computed_field
    @property
    def labor_cost(self) -> float:
        return round(self.engineering_hours * self.hourly_rate, 4)

    @computed_field
    @property
    def computed_holding_cost(self) -> float:
        return round(
            self.last_time_buy_qty * self.holding_cost_per_unit_per_week * self.holding_weeks,
            4,
        )

    @computed_field
    @property
    def total_redesign_cost(self) -> float:
        holding = self.holding_cost if self.holding_cost else self.computed_holding_cost
        return round(self.requalification_expense + holding + self.labor_cost, 4)


class BillOfMaterials(BaseModel):
    """Named BOM with component lines, optional substitutes, and redesign estimates."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    name: str = Field(min_length=1)
    revision: str = "A"
    components: List[BomComponent] = Field(default_factory=list)
    substitutes: List[SubstituteComponent] = Field(default_factory=list)
    redesign_costs: List[RedesignCost] = Field(default_factory=list)

    @computed_field
    @property
    def total_unit_cost(self) -> float:
        return round(sum(line.extended_cost for line in self.components), 4)
