"""Market Conditions, Supply Pressure, and Availability Risk Engine.

Implements:
6.1 Inventory coverage in weeks (usable stock / weekly demand)
6.2 Lead-time procurement margin and deadline arrival tracking
6.3 Demand-to-supply pressure normalization
6.4 Supplier concentration via Herfindahl-Hirschman Index (HHI = sum s_i^2)
6.5 Configurable Supply Pressure Index (SPI = 100 * sum w_i * x_i)
6.6 Availability tolerance settings with PASS / FAIL / UNKNOWN status checks.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

SPI_WEIGHTS = {
    "stock_coverage": 0.25,
    "lead_time": 0.20,
    "allocation_status": 0.15,
    "supplier_concentration": 0.15,
    "price_volatility": 0.10,
    "lifecycle_status": 0.15,
}
SPI_TIER_THRESHOLDS = {"MODERATE_MIN": 25.0, "HIGH_MIN": 50.0, "CRITICAL_MIN": 75.0}
SPI_MISSING_INPUT_PROXIES = {
    "stock_coverage_risk": 0.50,
    "lead_time_risk": 0.50,
    "supplier_concentration_risk": 0.50,
    "price_volatility_risk": 0.20,
    "lifecycle_risk": 0.50,
}


@dataclass
class SupplierShare:
    supplier_name: str
    share_fraction: float  # 0.0 to 1.0


@dataclass
class AvailabilityTolerances:
    """Configurable buyer thresholds."""
    min_required_stock: int = 500
    max_lead_time_weeks: float = 16.0
    min_inventory_coverage_weeks: float = 8.0
    min_independent_suppliers: int = 2
    max_price_increase_pct: float = 20.0
    allow_allocation_status: bool = False
    max_acceptable_hhi: float = 0.50  # 0.0 (perfectly distributed) to 1.0 (monopoly)
    required_procurement_date: Optional[str] = None  # "YYYY-MM-DD"


@dataclass
class ToleranceCheckResult:
    parameter: str
    configured_threshold: Any
    observed_value: Any
    status: str  # "PASS" | "FAIL" | "UNKNOWN"
    explanation: str


@dataclass
class SupplyPressureReport:
    part_number: str
    available_stock: Optional[int]
    weekly_demand: Optional[float]
    inventory_coverage_weeks: Optional[float]
    estimated_lead_time_weeks: Optional[float]
    available_procurement_window_weeks: Optional[float]
    lead_time_margin_weeks: Optional[float]
    can_arrive_before_deadline: Optional[bool]
    demand_supply_pressure_ratio: Optional[float]
    supplier_count: int
    hhi_concentration: Optional[float]
    hhi_tier: str
    supply_pressure_index: float  # 0 to 100
    spi_risk_category: str  # "LOW" | "MODERATE" | "HIGH" | "CRITICAL"
    factor_breakdown: Dict[str, float]
    tolerance_checks: List[ToleranceCheckResult]
    data_freshness_date: str
    limitations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["tolerance_checks"] = [asdict(t) for t in self.tolerance_checks]
        res["model_metadata"] = {
            "spi_weights": SPI_WEIGHTS,
            "spi_tier_thresholds": SPI_TIER_THRESHOLDS,
            "missing_input_proxies": {
                **SPI_MISSING_INPUT_PROXIES,
            },
            "hhi_without_supplier_shares": "uniform-share proxy from supplier_count; zero means unknown",
        }
        return res


def compute_inventory_coverage(
    available_usable_stock: Optional[int],
    weekly_demand: Optional[float],
) -> Optional[float]:
    """
    6.1 Inventory coverage in weeks = Available usable stock / Weekly demand.
    Explicitly handles zero demand and unknown stock.
    """
    if available_usable_stock is None or weekly_demand is None:
        return None
    if weekly_demand <= 0:
        return float("inf") if available_usable_stock > 0 else 0.0
    return round(available_usable_stock / weekly_demand, 2)


def compute_lead_time_margin(
    estimated_lead_time_weeks: Optional[float],
    required_deadline: Optional[str],
    current_date: Optional[date] = None,
) -> Tuple[Optional[float], Optional[float], Optional[bool]]:
    """
    6.2 Compare estimated lead time against procurement window before required deadline.
    Returns: (procurement_window_weeks, lead_time_margin_weeks, arrives_on_time)
    """
    if estimated_lead_time_weeks is None or not required_deadline:
        return None, None, None

    try:
        deadline = datetime.strptime(required_deadline, "%Y-%m-%d").date()
    except ValueError:
        return None, None, None

    now = current_date or date.today()
    days_remaining = (deadline - now).days
    procurement_window_weeks = round(max(0.0, days_remaining / 7.0), 2)
    lead_time_margin = round(procurement_window_weeks - estimated_lead_time_weeks, 2)
    arrives_on_time = lead_time_margin >= 0.0

    return procurement_window_weeks, lead_time_margin, arrives_on_time


def compute_hhi(
    supplier_shares: Optional[List[SupplierShare]] = None,
    supplier_count: int = 0,
) -> Tuple[Optional[float], str]:
    """
    6.4 Herfindahl-Hirschman Index: HHI = sum(s_i^2) where s_i in [0, 1].
    If individual shares are unknown, uses uniform share approximation only as an explicit proxy.
    """
    if supplier_shares and len(supplier_shares) > 0:
        total = sum(s.share_fraction for s in supplier_shares)
        if total <= 0:
            return None, "UNKNOWN"
        # Normalize in case shares do not sum exactly to 1.0
        normalized = [s.share_fraction / total for s in supplier_shares]
        hhi = sum(s * s for s in normalized)
    elif supplier_count > 0:
        # Uniform distribution fallback
        hhi = 1.0 / float(supplier_count)
    else:
        return None, "UNKNOWN"

    hhi = round(hhi, 4)
    if hhi <= 0.15:
        tier = "UNCONCENTRATED"
    elif hhi <= 0.25:
        tier = "MODERATE_CONCENTRATION"
    elif hhi < 1.0:
        tier = "HIGH_CONCENTRATION"
    else:
        tier = "SOLE_SOURCE_MONOPOLY"

    return hhi, tier


def compute_supply_pressure_index(
    coverage_weeks: Optional[float],
    lead_time_margin_weeks: Optional[float],
    hhi: Optional[float],
    is_allocated: bool = False,
    is_backordered: bool = False,
    lifecycle_status: Optional[str] = None,
    price_change_pct: Optional[float] = None,
) -> Tuple[float, Dict[str, float]]:
    """
    6.5 Supply Pressure Index: SPI = 100 * sum(w_i * x_i).
    Normalized risk factors (0.0 best, 1.0 worst).
    """
    # Factor 1: Stock coverage (target 12 weeks for 0 risk, 0 weeks for 1.0 risk)
    if coverage_weeks is None:
        x_stock = SPI_MISSING_INPUT_PROXIES["stock_coverage_risk"]
    elif coverage_weeks == float("inf") or coverage_weeks >= 12.0:
        x_stock = 0.0
    else:
        x_stock = max(0.0, min(1.0, (12.0 - coverage_weeks) / 12.0))

    # Factor 2: Lead time pressure (negative margin is maximum risk)
    if lead_time_margin_weeks is None:
        x_lead = SPI_MISSING_INPUT_PROXIES["lead_time_risk"]
    elif lead_time_margin_weeks < 0:
        x_lead = 1.0
    elif lead_time_margin_weeks >= 8.0:
        x_lead = 0.0
    else:
        x_lead = max(0.0, min(1.0, (8.0 - lead_time_margin_weeks) / 8.0))

    # Factor 3: Market allocation and backorder status
    if is_allocated and is_backordered:
        x_alloc = 1.0
    elif is_allocated or is_backordered:
        x_alloc = 0.85
    else:
        x_alloc = 0.0

    # Factor 4: Supplier concentration (HHI)
    if hhi is None:
        x_hhi = SPI_MISSING_INPUT_PROXIES["supplier_concentration_risk"]
    else:
        x_hhi = max(0.0, min(1.0, hhi))

    # Factor 5: Price volatility
    if price_change_pct is None:
        x_price = SPI_MISSING_INPUT_PROXIES["price_volatility_risk"]
    elif price_change_pct <= 0:
        x_price = 0.0
    else:
        x_price = max(0.0, min(1.0, price_change_pct / 50.0))

    # Factor 6: Lifecycle exposure
    status = (lifecycle_status or "").upper()
    if status in {"EOL", "OBSOLETE"}:
        x_life = 1.0
    elif status == "NRND":
        x_life = 0.70
    elif status == "ACTIVE":
        x_life = 0.10
    else:
        x_life = SPI_MISSING_INPUT_PROXIES["lifecycle_risk"]

    raw_spi = 100.0 * (
        SPI_WEIGHTS["stock_coverage"] * x_stock
        + SPI_WEIGHTS["lead_time"] * x_lead
        + SPI_WEIGHTS["allocation_status"] * x_alloc
        + SPI_WEIGHTS["supplier_concentration"] * x_hhi
        + SPI_WEIGHTS["price_volatility"] * x_price
        + SPI_WEIGHTS["lifecycle_status"] * x_life
    )

    factors = {
        "stock_risk": round(x_stock, 3),
        "lead_time_risk": round(x_lead, 3),
        "allocation_risk": round(x_alloc, 3),
        "concentration_risk": round(x_hhi, 3),
        "price_volatility_risk": round(x_price, 3),
        "lifecycle_risk": round(x_life, 3),
    }

    return round(raw_spi, 1), factors


def evaluate_market_supply_risk(
    part_number: str,
    available_stock: Optional[int] = None,
    weekly_demand: Optional[float] = None,
    estimated_lead_time_weeks: Optional[float] = None,
    supplier_count: int = 0,
    supplier_shares: Optional[List[SupplierShare]] = None,
    is_allocated: bool = False,
    is_backordered: bool = False,
    lifecycle_status: Optional[str] = None,
    price_change_pct: Optional[float] = None,
    tolerances: Optional[AvailabilityTolerances] = None,
) -> SupplyPressureReport:
    """Evaluate comprehensive market conditions, supply pressure, and availability tolerances."""
    tol = tolerances or AvailabilityTolerances()
    limitations: List[str] = []

    # 6.1 Coverage
    coverage = compute_inventory_coverage(available_stock, weekly_demand)
    if available_stock is None:
        limitations.append("Available usable distributor stock is unverified or missing.")
    if weekly_demand is None:
        limitations.append("Production weekly demand rate is unconfigured.")

    # 6.2 Lead-time margin
    req_date = tol.required_procurement_date
    window, margin, on_time = compute_lead_time_margin(estimated_lead_time_weeks, req_date)
    if estimated_lead_time_weeks is None:
        limitations.append("Manufacturer lead time is unrecorded.")

    # 6.3 Demand-to-supply ratio
    if available_stock is not None and weekly_demand is not None:
        monthly_demand = weekly_demand * 4.33
        ratio = round(monthly_demand / max(1, available_stock), 3)
    else:
        ratio = None

    # 6.4 HHI
    hhi, hhi_tier = compute_hhi(supplier_shares, supplier_count)
    if not supplier_shares and supplier_count > 0:
        limitations.append("Supplier sourcing shares are approximate based on supplier count alone.")
    elif not supplier_shares:
        limitations.append("Supplier count and supplier shares are missing; concentration remains unknown.")

    # 6.5 SPI
    spi, factor_breakdown = compute_supply_pressure_index(
        coverage_weeks=coverage,
        lead_time_margin_weeks=margin,
        hhi=hhi,
        is_allocated=is_allocated,
        is_backordered=is_backordered,
        lifecycle_status=lifecycle_status,
        price_change_pct=price_change_pct,
    )

    if spi >= SPI_TIER_THRESHOLDS["CRITICAL_MIN"]:
        spi_tier = "CRITICAL"
    elif spi >= SPI_TIER_THRESHOLDS["HIGH_MIN"]:
        spi_tier = "HIGH"
    elif spi >= SPI_TIER_THRESHOLDS["MODERATE_MIN"]:
        spi_tier = "MODERATE"
    else:
        spi_tier = "LOW"

    # 6.6 Tolerance checks
    checks: List[ToleranceCheckResult] = []

    # Check 1: Minimum stock
    if available_stock is not None:
        s_pass = available_stock >= tol.min_required_stock
        checks.append(ToleranceCheckResult(
            parameter="minimum_required_stock",
            configured_threshold=tol.min_required_stock,
            observed_value=available_stock,
            status="PASS" if s_pass else "FAIL",
            explanation=f"Stock {available_stock} {'meets' if s_pass else 'is below'} required minimum of {tol.min_required_stock}.",
        ))
    else:
        checks.append(ToleranceCheckResult(
            parameter="minimum_required_stock",
            configured_threshold=tol.min_required_stock,
            observed_value=None,
            status="UNKNOWN",
            explanation="Distributor stock is unrecorded.",
        ))

    # Check 2: Maximum lead time
    if estimated_lead_time_weeks is not None:
        lt_pass = estimated_lead_time_weeks <= tol.max_lead_time_weeks
        checks.append(ToleranceCheckResult(
            parameter="maximum_lead_time_weeks",
            configured_threshold=tol.max_lead_time_weeks,
            observed_value=estimated_lead_time_weeks,
            status="PASS" if lt_pass else "FAIL",
            explanation=f"Lead time {estimated_lead_time_weeks}w {'within' if lt_pass else 'exceeds'} maximum threshold of {tol.max_lead_time_weeks}w.",
        ))
    else:
        checks.append(ToleranceCheckResult(
            parameter="maximum_lead_time_weeks",
            configured_threshold=tol.max_lead_time_weeks,
            observed_value=None,
            status="UNKNOWN",
            explanation="Lead time is unknown.",
        ))

    # Check 3: Inventory coverage
    if coverage is not None:
        cov_pass = coverage >= tol.min_inventory_coverage_weeks
        checks.append(ToleranceCheckResult(
            parameter="minimum_inventory_coverage_weeks",
            configured_threshold=tol.min_inventory_coverage_weeks,
            observed_value=coverage,
            status="PASS" if cov_pass else "FAIL",
            explanation=f"Coverage of {coverage}w {'satisfies' if cov_pass else 'is below'} target {tol.min_inventory_coverage_weeks}w buffer.",
        ))
    else:
        checks.append(ToleranceCheckResult(
            parameter="minimum_inventory_coverage_weeks",
            configured_threshold=tol.min_inventory_coverage_weeks,
            observed_value=None,
            status="UNKNOWN",
            explanation="Inventory coverage cannot be calculated without demand and stock.",
        ))

    # Check 4: Independent suppliers
    supp_pass = supplier_count >= tol.min_independent_suppliers
    checks.append(ToleranceCheckResult(
        parameter="min_independent_suppliers",
        configured_threshold=tol.min_independent_suppliers,
        observed_value=supplier_count,
        status="PASS" if supp_pass else "FAIL",
        explanation=f"Found {supplier_count} suppliers (required: {tol.min_independent_suppliers}).",
    ))

    # Check 5: Allocation status
    if is_allocated and not tol.allow_allocation_status:
        checks.append(ToleranceCheckResult(
            parameter="allocation_status",
            configured_threshold="No Allocation",
            observed_value="ALLOCATED",
            status="FAIL",
            explanation="Component is currently under manufacturer allocation.",
        ))
    else:
        checks.append(ToleranceCheckResult(
            parameter="allocation_status",
            configured_threshold="No Allocation",
            observed_value="NORMAL",
            status="PASS",
            explanation="Component is not under allocation.",
        ))

    # Check 6: Deadline arrival
    if on_time is not None:
        checks.append(ToleranceCheckResult(
            parameter="procurement_deadline_arrival",
            configured_threshold=req_date,
            observed_value=f"Margin: {margin}w",
            status="PASS" if on_time else "FAIL",
            explanation=f"Component {'can' if on_time else 'CANNOT'} arrive before {req_date} (margin: {margin} weeks).",
        ))
    else:
        checks.append(ToleranceCheckResult(
            parameter="procurement_deadline_arrival",
            configured_threshold=req_date or "UNCONFIGURED",
            observed_value=None,
            status="UNKNOWN",
            explanation="Deadline or lead time unconfigured.",
        ))

    return SupplyPressureReport(
        part_number=part_number,
        available_stock=available_stock,
        weekly_demand=weekly_demand,
        inventory_coverage_weeks=coverage,
        estimated_lead_time_weeks=estimated_lead_time_weeks,
        available_procurement_window_weeks=window,
        lead_time_margin_weeks=margin,
        can_arrive_before_deadline=on_time,
        demand_supply_pressure_ratio=ratio,
        supplier_count=supplier_count,
        hhi_concentration=hhi,
        hhi_tier=hhi_tier,
        supply_pressure_index=spi,
        spi_risk_category=spi_tier,
        factor_breakdown=factor_breakdown,
        tolerance_checks=checks,
        data_freshness_date=datetime.now().strftime("%Y-%m-%d"),
        limitations=limitations,
    )
