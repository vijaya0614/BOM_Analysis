from typing import Any, Dict, List, Optional

from src.models import ComponentSpec

MATCH = "MATCH"
MISMATCH = "MISMATCH"
UNKNOWN = "UNKNOWN"

NONE = "NONE"
INCOMPATIBLE = "INCOMPATIBLE"
REDESIGN_REQUIRED = "REDESIGN_REQUIRED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"


def _number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _check(parameter: str, original: Any, candidate: Any, status: str, impact: str, weight: int) -> Dict[str, Any]:
    return {
        "parameter": parameter,
        "original": original,
        "candidate": candidate,
        "status": status,
        "impact": impact,
        "weight": weight,
    }


def check_exact(original: ComponentSpec, candidate: ComponentSpec, parameter: str, weight: int, impact: str = INCOMPATIBLE) -> Dict[str, Any]:
    ov = original.get_spec(parameter)
    cv = candidate.get_spec(parameter)
    if ov is None or cv is None:
        return _check(parameter, ov, cv, UNKNOWN, REVIEW_REQUIRED, weight)
    return _check(parameter, ov, cv, MATCH if str(ov).lower() == str(cv).lower() else MISMATCH, NONE if str(ov).lower() == str(cv).lower() else impact, weight)


def check_package(original: ComponentSpec, candidate: ComponentSpec, weight: int = 20) -> Dict[str, Any]:
    return check_exact(original, candidate, "package", weight, REDESIGN_REQUIRED)


def check_minimum(original: ComponentSpec, candidate: ComponentSpec, parameter: str, weight: int, impact: str = INCOMPATIBLE) -> Dict[str, Any]:
    ov = _number(original.get_spec(parameter))
    cv = _number(candidate.get_spec(parameter))
    if ov is None or cv is None:
        return _check(parameter, ov, cv, UNKNOWN, REVIEW_REQUIRED, weight)
    ok = cv >= ov
    return _check(parameter, ov, cv, MATCH if ok else MISMATCH, NONE if ok else impact, weight)


def check_maximum(original: ComponentSpec, candidate: ComponentSpec, parameter: str, weight: int, impact: str = REVIEW_REQUIRED) -> Dict[str, Any]:
    ov = _number(original.get_spec(parameter))
    cv = _number(candidate.get_spec(parameter))
    if ov is None or cv is None:
        return _check(parameter, ov, cv, UNKNOWN, REVIEW_REQUIRED, weight)
    ok = cv <= ov
    return _check(parameter, ov, cv, MATCH if ok else MISMATCH, NONE if ok else impact, weight)


def check_range_cover(original: ComponentSpec, candidate: ComponentSpec, min_parameter: str, max_parameter: str, weight: int) -> List[Dict[str, Any]]:
    omin = _number(original.get_spec(min_parameter))
    omax = _number(original.get_spec(max_parameter))
    cmin = _number(candidate.get_spec(min_parameter))
    cmax = _number(candidate.get_spec(max_parameter))
    if None in (omin, omax, cmin, cmax):
        return [
            _check(min_parameter, omin, cmin, UNKNOWN, REVIEW_REQUIRED, weight // 2),
            _check(max_parameter, omax, cmax, UNKNOWN, REVIEW_REQUIRED, weight - weight // 2),
        ]
    min_ok = cmin <= omin
    max_ok = cmax >= omax
    return [
        _check(min_parameter, omin, cmin, MATCH if min_ok else MISMATCH, NONE if min_ok else INCOMPATIBLE, weight // 2),
        _check(max_parameter, omax, cmax, MATCH if max_ok else MISMATCH, NONE if max_ok else INCOMPATIBLE, weight - weight // 2),
    ]


def check_numeric_equal(original: ComponentSpec, candidate: ComponentSpec, parameter: str, weight: int, tolerance_pct: float = 0.0) -> Dict[str, Any]:
    ov = _number(original.get_spec(parameter))
    cv = _number(candidate.get_spec(parameter))
    if ov is None or cv is None:
        return _check(parameter, ov, cv, UNKNOWN, REVIEW_REQUIRED, weight)
    allowed = abs(ov) * tolerance_pct
    ok = abs(cv - ov) <= allowed
    return _check(parameter, ov, cv, MATCH if ok else MISMATCH, NONE if ok else INCOMPATIBLE, weight)


def resistor_checks(original: ComponentSpec, candidate: ComponentSpec) -> List[Dict[str, Any]]:
    return [
        check_numeric_equal(original, candidate, "resistance_ohms", 35),
        check_maximum(original, candidate, "tolerance_pct", 20, REVIEW_REQUIRED),
        check_minimum(original, candidate, "power_w", 25),
        check_package(original, candidate, 20),
    ]


def capacitor_checks(original: ComponentSpec, candidate: ComponentSpec) -> List[Dict[str, Any]]:
    return [
        check_numeric_equal(original, candidate, "capacitance_uf", 30),
        check_minimum(original, candidate, "voltage_rating_v", 25),
        check_maximum(original, candidate, "tolerance_pct", 15, REVIEW_REQUIRED),
        check_exact(original, candidate, "polarity", 10, INCOMPATIBLE),
        check_package(original, candidate, 20),
    ]


def regulator_checks(original: ComponentSpec, candidate: ComponentSpec) -> List[Dict[str, Any]]:
    checks = []
    checks.extend(check_range_cover(original, candidate, "input_voltage_min_v", "input_voltage_max_v", 20))
    checks.extend(
        [
            check_numeric_equal(original, candidate, "output_voltage_v", 25, 0.02),
            check_minimum(original, candidate, "output_current_a", 20),
            check_minimum(original, candidate, "operating_temperature_max_c", 10, REVIEW_REQUIRED),
            check_package(original, candidate, 20),
            check_exact(original, candidate, "pinout", 5, REDESIGN_REQUIRED),
        ]
    )
    return checks


def mosfet_checks(original: ComponentSpec, candidate: ComponentSpec) -> List[Dict[str, Any]]:
    return [
        check_minimum(original, candidate, "vds_v", 20),
        check_minimum(original, candidate, "id_a", 20),
        check_maximum(original, candidate, "rds_on_mohm", 20, REVIEW_REQUIRED),
        check_maximum(original, candidate, "gate_drive_voltage_v", 15, INCOMPATIBLE),
        check_package(original, candidate, 20),
        check_exact(original, candidate, "pinout", 5, REDESIGN_REQUIRED),
    ]


def temperature_sensor_checks(original: ComponentSpec, candidate: ComponentSpec) -> List[Dict[str, Any]]:
    checks = []
    checks.extend(check_range_cover(original, candidate, "measurement_min_c", "measurement_max_c", 30))
    checks.extend(check_range_cover(original, candidate, "supply_voltage_min_v", "supply_voltage_max_v", 20))
    checks.extend(
        [
            check_exact(original, candidate, "interface", 25, INCOMPATIBLE),
            check_package(original, candidate, 20),
            check_numeric_equal(original, candidate, "accuracy_c", 5, 0.50),
        ]
    )
    return checks


def microcontroller_checks(original: ComponentSpec, candidate: ComponentSpec) -> List[Dict[str, Any]]:
    checks = [
        check_exact(original, candidate, "architecture", 20, REDESIGN_REQUIRED),
        check_minimum(original, candidate, "flash_kb", 15, REDESIGN_REQUIRED),
        check_minimum(original, candidate, "ram_kb", 15, REDESIGN_REQUIRED),
        check_minimum(original, candidate, "gpio_count", 10, REDESIGN_REQUIRED),
        check_package(original, candidate, 20),
        check_exact(original, candidate, "pinout", 5, REDESIGN_REQUIRED),
    ]
    checks[3:3] = check_range_cover(original, candidate, "supply_voltage_min_v", "supply_voltage_max_v", 15)
    return checks


def timer_ic_checks(original: ComponentSpec, candidate: ComponentSpec) -> List[Dict[str, Any]]:
    checks = []
    checks.extend(check_range_cover(original, candidate, "supply_voltage_min_v", "supply_voltage_max_v", 30))
    checks.extend(
        [
            check_minimum(original, candidate, "output_current_ma", 20, REVIEW_REQUIRED),
            check_minimum(original, candidate, "channels", 10, REDESIGN_REQUIRED),
            check_package(original, candidate, 25),
            check_exact(original, candidate, "pinout", 15, REDESIGN_REQUIRED),
        ]
    )
    return checks


def motor_driver_checks(original: ComponentSpec, candidate: ComponentSpec) -> List[Dict[str, Any]]:
    checks = []
    checks.extend(check_range_cover(original, candidate, "motor_voltage_min_v", "motor_voltage_max_v", 25))
    checks.extend(
        [
            check_minimum(original, candidate, "output_current_a", 20),
            check_minimum(original, candidate, "channels", 10, REDESIGN_REQUIRED),
            check_numeric_equal(original, candidate, "logic_voltage_v", 15, 0.05),
            check_package(original, candidate, 20),
            check_exact(original, candidate, "pinout", 10, REDESIGN_REQUIRED),
        ]
    )
    return checks


def switch_checks(original: ComponentSpec, candidate: ComponentSpec) -> List[Dict[str, Any]]:
    return [
        check_exact(original, candidate, "contact_type", 20, INCOMPATIBLE),
        check_minimum(original, candidate, "poles", 15, REDESIGN_REQUIRED),
        check_minimum(original, candidate, "throws", 15, REDESIGN_REQUIRED),
        check_minimum(original, candidate, "current_rating_ma", 20, REVIEW_REQUIRED),
        check_package(original, candidate, 20),
        check_exact(original, candidate, "pinout", 10, REDESIGN_REQUIRED),
    ]


def led_checks(original: ComponentSpec, candidate: ComponentSpec) -> List[Dict[str, Any]]:
    return [
        check_exact(original, candidate, "color", 25, REVIEW_REQUIRED),
        check_numeric_equal(original, candidate, "forward_voltage_v", 20, 0.20),
        check_minimum(original, candidate, "current_ma", 15, REVIEW_REQUIRED),
        check_exact(original, candidate, "polarity", 10, INCOMPATIBLE),
        check_package(original, candidate, 20),
        check_exact(original, candidate, "pinout", 10, REDESIGN_REQUIRED),
    ]


def fan_checks(original: ComponentSpec, candidate: ComponentSpec) -> List[Dict[str, Any]]:
    return [
        check_numeric_equal(original, candidate, "voltage_v", 25, 0.05),
        check_minimum(original, candidate, "current_a", 15, REVIEW_REQUIRED),
        check_exact(original, candidate, "wires", 15, REDESIGN_REQUIRED),
        check_numeric_equal(original, candidate, "size_mm", 20, 0.0),
        check_package(original, candidate, 15),
        check_exact(original, candidate, "pinout", 10, REDESIGN_REQUIRED),
    ]


def connector_checks(original: ComponentSpec, candidate: ComponentSpec) -> List[Dict[str, Any]]:
    return [
        check_numeric_equal(original, candidate, "pitch_mm", 20, 0.0),
        check_minimum(original, candidate, "positions", 20, REDESIGN_REQUIRED),
        check_minimum(original, candidate, "current_rating_a", 20, REVIEW_REQUIRED),
        check_exact(original, candidate, "mounting", 15, REDESIGN_REQUIRED),
        check_package(original, candidate, 15),
        check_exact(original, candidate, "pinout", 10, REDESIGN_REQUIRED),
    ]


def generic_checks(original: ComponentSpec, candidate: ComponentSpec) -> List[Dict[str, Any]]:
    return [check_package(original, candidate, 40)]


CATEGORY_RULES = {
    "resistor": resistor_checks,
    "capacitor": capacitor_checks,
    "regulator": regulator_checks,
    "mosfet": mosfet_checks,
    "temperature_sensor": temperature_sensor_checks,
    "microcontroller": microcontroller_checks,
    "timer_ic": timer_ic_checks,
    "motor_driver": motor_driver_checks,
    "switch": switch_checks,
    "led": led_checks,
    "fan": fan_checks,
    "connector": connector_checks,
}


def run_compatibility_checks(original: ComponentSpec, candidate: ComponentSpec) -> List[Dict[str, Any]]:
    if original.category != candidate.category:
        return [
            _check("category", original.category, candidate.category, MISMATCH, INCOMPATIBLE, 100)
        ]
    return CATEGORY_RULES.get(original.category, generic_checks)(original, candidate)
