"""Operating-limit and tolerance evaluation.

This module augments compatibility checks with evidence-bearing engineering
margin calculations. It does not replace compatibility_rules or declare a
candidate compatible on its own.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

PASS = "PASS"
WARNING = "WARNING"
FAIL = "FAIL"
SAFE_MARGIN = "SAFE_MARGIN"
WARNING_MARGIN = "WARNING_MARGIN"
LIMIT_APPROACHING = "LIMIT_APPROACHING"
OUT_OF_LIMIT = "OUT_OF_LIMIT"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

DATASET_FACT = "DATASET_FACT"
DERIVED_VALUE = "DERIVED_VALUE"
MISSING_DATA = "MISSING_DATA"

_SAFE_THRESHOLD = 0.20
_WARNING_THRESHOLD = 0.05


def _num(value: Any) -> Optional[float]:
    try:
        if value is None or value == "" or value == INSUFFICIENT_DATA:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _confidence(value: str) -> str:
    return value or INSUFFICIENT_DATA


def _margin_status(normalized_margin: Optional[float]) -> str:
    if normalized_margin is None:
        return INSUFFICIENT_DATA
    if normalized_margin < 0:
        return OUT_OF_LIMIT
    if normalized_margin <= _WARNING_THRESHOLD:
        return LIMIT_APPROACHING
    if normalized_margin <= _SAFE_THRESHOLD:
        return WARNING_MARGIN
    return SAFE_MARGIN


def _legacy_status(status: str) -> str:
    if status in {SAFE_MARGIN, WARNING_MARGIN, LIMIT_APPROACHING}:
        return PASS if status == SAFE_MARGIN else WARNING
    if status == OUT_OF_LIMIT:
        return FAIL
    return INSUFFICIENT_DATA


def _range_margin(value: float, limit_min: Optional[float], limit_max: Optional[float]) -> Dict[str, Optional[float]]:
    margins = []
    if limit_min is not None:
        distance = value - limit_min
        denom = abs(limit_min) if limit_min else abs(value) or 1.0
        margins.append((distance, distance / denom))
    if limit_max is not None:
        distance = limit_max - value
        denom = abs(limit_max) if limit_max else abs(value) or 1.0
        margins.append((distance, distance / denom))
    if not margins:
        return {"margin": None, "normalized_margin": None}
    limiting = min(margins, key=lambda item: item[1])
    return {"margin": limiting[0], "normalized_margin": limiting[1]}


def evaluate_operating_limit(
    *,
    parameter: str,
    operating_value: Any = None,
    limit_min: Any = None,
    limit_max: Any = None,
    required_min: Any = None,
    required_max: Any = None,
    candidate_min: Any = None,
    candidate_max: Any = None,
    unit: str = "",
    condition: str = "",
    source: str = "",
    confidence: str = "",
) -> Dict[str, Any]:
    """Evaluate an operating value against a limit or a required range.

    ``operating_value`` is the preferred path. When it is absent, the legacy
    range-coverage path compares a required operating envelope against a
    candidate's stated allowable range. It never treats a candidate rating as
    the actual operating value.
    """
    op = _num(operating_value)
    lo = _num(limit_min)
    hi = _num(limit_max)
    req_min = _num(required_min)
    req_max = _num(required_max)
    cand_min = _num(candidate_min)
    cand_max = _num(candidate_max)

    result = {
        "check_type": "OPERATING_LIMIT",
        "parameter": parameter,
        "operating_value": op,
        "limit_min": lo,
        "limit_max": hi,
        "required_min": req_min,
        "required_max": req_max,
        "candidate_min": cand_min,
        "candidate_max": cand_max,
        "margin": None,
        "normalized_margin": None,
        "unit": unit,
        "condition": condition,
        "source": source,
        "confidence": _confidence(confidence),
        "evidence_type": MISSING_DATA,
    }

    if op is not None:
        if lo is None and hi is None:
            return {**result, "status": INSUFFICIENT_DATA, "legacy_status": INSUFFICIENT_DATA, "reason": "OPERATING_LIMIT_MISSING_LIMIT"}
        margin = _range_margin(op, lo, hi)
        status = _margin_status(margin["normalized_margin"])
        return {
            **result,
            **margin,
            "status": status,
            "legacy_status": _legacy_status(status),
            "reason": "OPERATING_LIMIT_FAIL" if status == OUT_OF_LIMIT else "OPERATING_LIMIT_MARGIN",
            "evidence_type": DERIVED_VALUE,
        }

    if lo is not None or hi is not None:
        return {**result, "status": INSUFFICIENT_DATA, "legacy_status": INSUFFICIENT_DATA, "reason": "OPERATING_VALUE_MISSING"}

    if req_min is None and req_max is None:
        return {**result, "status": INSUFFICIENT_DATA, "legacy_status": INSUFFICIENT_DATA, "reason": "OPERATING_REQUIREMENT_MISSING"}
    if cand_min is None and cand_max is None:
        return {**result, "status": INSUFFICIENT_DATA, "legacy_status": INSUFFICIENT_DATA, "reason": "OPERATING_LIMIT_MISSING_LIMIT"}

    candidate_lo = cand_min if cand_min is not None else cand_max
    candidate_hi = cand_max if cand_max is not None else cand_min
    margin_values = []
    status = SAFE_MARGIN
    reason = "OPERATING_LIMIT_MARGIN"
    if req_min is not None:
        if candidate_lo is None:
            status = INSUFFICIENT_DATA
            reason = "OPERATING_LIMIT_MISSING_LIMIT"
        else:
            distance = req_min - candidate_lo
            margin_values.append(distance / (abs(req_min) or 1.0))
            if candidate_lo > req_min:
                status = OUT_OF_LIMIT
                reason = "OPERATING_LIMIT_FAIL"
    if status != OUT_OF_LIMIT and req_max is not None:
        if candidate_hi is None:
            status = INSUFFICIENT_DATA
            reason = "OPERATING_LIMIT_MISSING_LIMIT"
        else:
            distance = candidate_hi - req_max
            margin_values.append(distance / (abs(req_max) or 1.0))
            if candidate_hi < req_max:
                status = OUT_OF_LIMIT
                reason = "OPERATING_LIMIT_FAIL"
    normalized = min(margin_values) if margin_values and status != INSUFFICIENT_DATA else None
    if status not in {OUT_OF_LIMIT, INSUFFICIENT_DATA}:
        status = _margin_status(normalized)
    return {
        **result,
        "candidate_min": candidate_lo,
        "candidate_max": candidate_hi,
        "margin": normalized,
        "normalized_margin": normalized,
        "status": status,
        "legacy_status": _legacy_status(status),
        "reason": reason,
        "evidence_type": DERIVED_VALUE,
    }


def evaluate_tolerance(
    *,
    parameter: str,
    required_nominal: Any = None,
    required_tolerance: Any = None,
    required_min: Any = None,
    required_max: Any = None,
    candidate_nominal: Any = None,
    candidate_tolerance: Any = None,
    candidate_min: Any = None,
    candidate_max: Any = None,
    actual_value: Any = None,
    design_value: Any = None,
    unit: str = "",
    condition: str = "",
    source: str = "",
    confidence: str = "",
) -> Dict[str, Any]:
    rnom = _num(required_nominal)
    rtol = _num(required_tolerance)
    rmin = _num(required_min)
    rmax = _num(required_max)
    cnom = _num(candidate_nominal)
    ctol = _num(candidate_tolerance)
    cmin = _num(candidate_min)
    cmax = _num(candidate_max)
    actual = _num(actual_value)
    design = _num(design_value)
    comparison_value = actual if actual is not None else design

    nominal = cnom if cnom is not None else rnom
    tolerance = ctol if ctol is not None else rtol
    lower = cmin
    upper = cmax
    evidence_type = DATASET_FACT if cmin is not None or cmax is not None else MISSING_DATA
    if nominal is not None and tolerance is not None:
        delta = abs(nominal) * (tolerance / 100.0)
        lower = nominal - delta
        upper = nominal + delta
        evidence_type = DERIVED_VALUE
    elif lower is None and upper is None and rmin is not None and rmax is not None:
        lower = rmin
        upper = rmax
        evidence_type = DATASET_FACT

    result = {
        "check_type": "TOLERANCE",
        "parameter": parameter,
        "nominal": nominal,
        "tolerance": tolerance,
        "lower_bound": lower,
        "upper_bound": upper,
        "actual_value": actual,
        "design_value": design,
        "margin": None,
        "normalized_margin": None,
        "unit": unit,
        "condition": condition,
        "source": source,
        "confidence": _confidence(confidence),
        "evidence_type": evidence_type,
    }

    if nominal is None and lower is None and upper is None:
        return {**result, "status": INSUFFICIENT_DATA, "legacy_status": INSUFFICIENT_DATA, "reason": "TOLERANCE_DATA_MISSING"}
    if comparison_value is None:
        if rnom is not None and cnom is not None and rtol is None and ctol is None and cmin is None and cmax is None:
            status = SAFE_MARGIN if cnom == rnom else WARNING_MARGIN
            return {**result, "status": status, "legacy_status": _legacy_status(status), "reason": "TOLERANCE_NOMINAL_ONLY"}
        return {**result, "status": INSUFFICIENT_DATA, "legacy_status": INSUFFICIENT_DATA, "reason": "TOLERANCE_COMPARISON_VALUE_MISSING"}
    if lower is None and upper is None:
        return {**result, "status": INSUFFICIENT_DATA, "legacy_status": INSUFFICIENT_DATA, "reason": "TOLERANCE_BOUNDS_MISSING"}

    margin = _range_margin(comparison_value, lower, upper)
    if lower is not None and upper is not None and upper != lower:
        distance_to_bound = min(comparison_value - lower, upper - comparison_value)
        margin = {
            "margin": distance_to_bound,
            "normalized_margin": distance_to_bound / ((upper - lower) / 2.0),
        }
    status = _margin_status(margin["normalized_margin"])
    return {
        **result,
        **margin,
        "status": status,
        "legacy_status": _legacy_status(status),
        "reason": "TOLERANCE_FAIL" if status == OUT_OF_LIMIT else "TOLERANCE_MARGIN",
    }
