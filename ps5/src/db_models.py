"""SQLAlchemy 2.0 table mappings for electronic BOM, substitutes, and redesign cost."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.schemas import Criticality, LifecycleStatus


class Base(DeclarativeBase):
    pass


class BomComponentRow(Base):
    __tablename__ = "bom_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    part_number: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    package: Mapped[str] = mapped_column(String(64), nullable=False)
    criticality: Mapped[Criticality] = mapped_column(Enum(Criticality, native_enum=False, length=16), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Float, nullable=False)
    second_source: Mapped[bool] = mapped_column(Boolean, nullable=False)
    lead_time_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_status: Mapped[LifecycleStatus] = mapped_column(
        Enum(LifecycleStatus, native_enum=False, length=16),
        nullable=False,
    )
    distributor_stock: Mapped[int] = mapped_column(Integer, nullable=False)

    substitutes: Mapped[List["SubstituteComponentRow"]] = relationship(
        back_populates="original",
        cascade="all, delete-orphan",
    )
    redesign_costs: Mapped[List["RedesignCostRow"]] = relationship(
        back_populates="original",
        cascade="all, delete-orphan",
    )


class SubstituteComponentRow(Base):
    __tablename__ = "substitute_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_id: Mapped[int] = mapped_column(ForeignKey("bom_components.id"), nullable=False)
    part_number: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    original_part_number: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    package: Mapped[str] = mapped_column(String(64), nullable=False)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    second_source: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    lifecycle_status: Mapped[LifecycleStatus] = mapped_column(
        Enum(LifecycleStatus, native_enum=False, length=16),
        nullable=False,
        default=LifecycleStatus.ACTIVE,
    )
    lead_time_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distributor_stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    voltage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tolerance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    original: Mapped["BomComponentRow"] = relationship(back_populates="substitutes")
    redesign_costs: Mapped[List["RedesignCostRow"]] = relationship(back_populates="substitute")


class RedesignCostRow(Base):
    __tablename__ = "redesign_costs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_id: Mapped[int] = mapped_column(ForeignKey("bom_components.id"), nullable=False)
    substitute_id: Mapped[Optional[int]] = mapped_column(ForeignKey("substitute_components.id"), nullable=True)
    original_part_number: Mapped[str] = mapped_column(String(128), nullable=False)
    substitute_part_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    requalification_expense: Mapped[float] = mapped_column(Float, nullable=False)
    holding_cost: Mapped[float] = mapped_column(Float, nullable=False)
    engineering_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    hourly_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_time_buy_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    holding_cost_per_unit_per_week: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    holding_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    original: Mapped["BomComponentRow"] = relationship(back_populates="redesign_costs")
    substitute: Mapped[Optional["SubstituteComponentRow"]] = relationship(back_populates="redesign_costs")
