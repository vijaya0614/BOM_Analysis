"""Failure Mode and Effects Analysis (FMEA) Engine for Electronic Components.

Implements:
- Structured component and subsystem FMEA records
- Severity (S: 1-10), Occurrence (O: 1-10), Detection (D: 1-10) scoring
- Traditional Risk Priority Number: RPN = S * O * D (range 1 - 1000)
- Action Priority (High, Medium, Low) methodology
- Class-specific failure mode suggestions derived from component class and mission profile
- Before-and-after mitigation residual risk assessment.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

ACTION_PRIORITY_THRESHOLDS = {
    "HIGH": {"severity_min": 9, "severity_and_occurrence": [7, 5], "rpn_min": 150},
    "MEDIUM": {"severity_min": 5, "occurrence_min": 5, "rpn_min": 75},
}


@dataclass
class FmeaEntry:
    id: str
    part_number: str
    component_name: str
    subsystem: str
    intended_function: str
    failure_mode: str
    local_effect: str
    end_system_effect: str
    potential_cause: str
    prevention_controls: str
    detection_controls: str
    severity: int     # 1 to 10
    occurrence: int   # 1 to 10
    detection: int    # 1 to 10
    rpn: int          # S * O * D
    action_priority: str  # "HIGH" | "MEDIUM" | "LOW"
    recommended_action: str
    action_owner: str
    action_status: str  # "OPEN" | "IN_PROGRESS" | "COMPLETED" | "VERIFIED"
    residual_severity: int
    residual_occurrence: int
    residual_detection: int
    residual_rpn: int
    is_suggested: bool = True
    evidence_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_action_priority(severity: int, occurrence: int, detection: int) -> str:
    """
    Computes explainable Action Priority based on Severity, Occurrence, and Detection ratings.
    HIGH applies at severity >=9, severity >=7 with occurrence >=5, or RPN >=150.
    MEDIUM applies at severity >=5, occurrence >=5, or RPN >=75.
    """
    rpn = severity * occurrence * detection
    high = ACTION_PRIORITY_THRESHOLDS["HIGH"]
    medium = ACTION_PRIORITY_THRESHOLDS["MEDIUM"]
    if severity >= high["severity_min"] or (
        severity >= high["severity_and_occurrence"][0]
        and occurrence >= high["severity_and_occurrence"][1]
    ) or rpn >= high["rpn_min"]:
        return "HIGH"
    if severity >= medium["severity_min"] or occurrence >= medium["occurrence_min"] or rpn >= medium["rpn_min"]:
        return "MEDIUM"
    return "LOW"


# Standard failure mode taxonomy by electronic component category
CATEGORY_FAILURE_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "regulator": [
        {
            "failure_mode": "Internal Pass-FET Thermal Breakdown (Short-to-Input)",
            "local_effect": "Output voltage rises to uncontrolled input rail level.",
            "end_system_effect": "Downstream 3.3V/1.8V digital ICs destroyed by overvoltage; total subsystem halt.",
            "potential_cause": "Excessive continuous thermal dissipation Delta T > 60°C or thermal runaway.",
            "prevention_controls": "Thermal pad heatsink vias, 30% power derating, input TVS diode.",
            "detection_controls": "Internal thermal shutdown circuitry; board power-good supervisor.",
            "severity": 9,
            "occurrence": 4,
            "detection": 4,
            "recommended_action": "Add crowbar zener clamp or dedicated OVP supervisor on output rail.",
            "action_owner": "Power HW Lead",
            "residual_severity": 4,
            "residual_occurrence": 2,
            "residual_detection": 2,
        },
        {
            "failure_mode": "Feedback Resistor Drift (Output Voltage Sag)",
            "local_effect": "Regulated output drifts below minimum operating threshold (-8%).",
            "end_system_effect": "MCU brown-out reset, communication packet corruption.",
            "potential_cause": "High ambient temperature aging and resistor moisture absorption.",
            "prevention_controls": "Use 0.1% 25ppm/°C thin-film feedback resistors.",
            "detection_controls": "Built-in ADC voltage telemetry monitoring.",
            "severity": 6,
            "occurrence": 4,
            "detection": 3,
            "recommended_action": "Replace standard 1% thick-film resistors with automotive grade thin-film.",
            "action_owner": "HW Engineer",
            "residual_severity": 6,
            "residual_occurrence": 2,
            "residual_detection": 2,
        },
    ],
    "microcontroller": [
        {
            "failure_mode": "Firmware Lockup / Watchdog Reset Loop",
            "local_effect": "Processing core ceases telemetry and sensor sampling.",
            "end_system_effect": "Subsystem becomes unresponsive; fail-safe state triggered.",
            "potential_cause": "Power rail transient brown-out during wireless burst transmission.",
            "prevention_controls": "Bulk decoupling capacitor on VDD rail; hardware watchdog timer.",
            "detection_controls": "External hardware supervisor heartbeat pulse monitor.",
            "severity": 8,
            "occurrence": 4,
            "detection": 3,
            "recommended_action": "Increase local bulk decoupling capacitance near MCU pins by 22uF.",
            "action_owner": "Firmware / HW Lead",
            "residual_severity": 5,
            "residual_occurrence": 2,
            "residual_detection": 2,
        },
        {
            "failure_mode": "GPIO Latch-up from External Cable Surge",
            "local_effect": "Shorted I/O line, excessive chip supply current draw.",
            "end_system_effect": "Loss of sensor bus communication; localized heating.",
            "potential_cause": "ESD discharge on external connector or ground bounce during hot-plugging.",
            "prevention_controls": "Series 100 ohm protection resistors and clamp diodes on external pins.",
            "detection_controls": "Power supply current limit trip, automated self-test on boot.",
            "severity": 7,
            "occurrence": 5,
            "detection": 4,
            "recommended_action": "Mount ESD protection array (IEC 61000-4-2 Level 4) at connector entrance.",
            "action_owner": "Signal Integrity Engineer",
            "residual_severity": 4,
            "residual_occurrence": 2,
            "residual_detection": 2,
        },
    ],
    "capacitor": [
        {
            "failure_mode": "MLCC Flex Cracking and Low-Impedance Short",
            "local_effect": "Capacitor develops conductive crack across internal electrodes.",
            "end_system_effect": "Power rail shorted to ground; power supply enters hiccup overcurrent mode.",
            "potential_cause": "PCB mechanical strain during panel depanelization or mounting screw tightening.",
            "prevention_controls": "Design flexible termination (soft-term) MLCC or align parallel to stress axis.",
            "detection_controls": "In-circuit tester (ICT) and automated optical inspection (AOI).",
            "severity": 8,
            "occurrence": 4,
            "detection": 4,
            "recommended_action": "Switch to soft-termination (polymer/flexible end) MLCCs on board edges.",
            "action_owner": "Manufacturing Engineer",
            "residual_severity": 8,
            "residual_occurrence": 1,
            "residual_detection": 3,
        },
        {
            "failure_mode": "Electrolytic Dry-out / High ESR",
            "local_effect": "Capacitance drops below 70%, ESR increases by 400%.",
            "end_system_effect": "Excessive switching ripple voltage causes digital reset.",
            "potential_cause": "Arrhenius electrolyte evaporation under high continuous ambient temperature.",
            "prevention_controls": "Select 105°C / 5000h rated long-life polymer capacitor.",
            "detection_controls": "Periodic ripple voltage health check via diagnostics.",
            "severity": 7,
            "occurrence": 5,
            "detection": 5,
            "recommended_action": "Replace wet electrolytic with conductive polymer solid aluminum capacitor.",
            "action_owner": "Reliability Lead",
            "residual_severity": 5,
            "residual_occurrence": 2,
            "residual_detection": 3,
        },
    ],
    "mosfet": [
        {
            "failure_mode": "Gate-Oxide Punch-Through (Short G-S)",
            "local_effect": "Gate loses control; switch remains permanently OFF or ON.",
            "end_system_effect": "Load actuator / fan remains inactive or permanently energized.",
            "potential_cause": "Inductive turn-off spike exceeding V_GS absolute maximum rating.",
            "prevention_controls": "Flyback freewheeling diode across inductive load; bidirectional gate zener.",
            "detection_controls": "Actuator current sensor feedback loop.",
            "severity": 8,
            "occurrence": 4,
            "detection": 3,
            "recommended_action": "Add 15V TVS clamp directly between Gate and Source pins.",
            "action_owner": "HW Engineer",
            "residual_severity": 5,
            "residual_occurrence": 2,
            "residual_detection": 2,
        },
    ],
}


def generate_component_fmea(
    part_number: str,
    component_name: str,
    category: str,
    subsystem: str = "Electronics Subsystem",
    intended_function: Optional[str] = None,
    mission_profile_temperature_c: Optional[float] = None,
) -> List[FmeaEntry]:
    """
    Generates suggested FMEA entries for a component based on its category and operating environment.
    All entries are labeled as suggestions requiring engineering review.
    """
    cat = (category or "generic").lower().strip()
    templates = []
    for k, v in CATEGORY_FAILURE_TEMPLATES.items():
        if k in cat:
            templates = v
            break

    if not templates:
        # Generic electronic component failure modes
        templates = [
            {
                "failure_mode": "Parametric Drift under Thermal Stress",
                "local_effect": "Electrical specifications deviate outside published datasheet tolerance.",
                "end_system_effect": "Degraded measurement precision or timing margin.",
                "potential_cause": "High ambient temperature and extended operating hours.",
                "prevention_controls": "Component derating and adequate thermal dissipation.",
                "detection_controls": "Factory functional testing and calibration.",
                "severity": 5,
                "occurrence": 4,
                "detection": 4,
                "recommended_action": "Verify worst-case tolerance stackup and evaluate operating temperature margin.",
                "action_owner": "HW Engineer",
                "residual_severity": 4,
                "residual_occurrence": 2,
                "residual_detection": 2,
            },
            {
                "failure_mode": "Solder Joint Intermetallic Fatigue (Open Connection)",
                "local_effect": "Intermittent or high-resistance electrical connection.",
                "end_system_effect": "Loss of signal or power connectivity.",
                "potential_cause": "Thermal expansion coefficient (CTE) mismatch during repeated thermal cycling.",
                "prevention_controls": "Proper solder paste stencil thickness and IPC-A-610 Class 3 soldering.",
                "detection_controls": "Automated optical inspection (AOI) and X-ray inspection for BGA/QFN.",
                "severity": 7,
                "occurrence": 4,
                "detection": 4,
                "recommended_action": "Perform IPC-9701 thermal cycling validation on assembled PCB.",
                "action_owner": "Reliability Lead",
                "residual_severity": 6,
                "residual_occurrence": 2,
                "residual_detection": 3,
            },
        ]

    entries: List[FmeaEntry] = []
    for idx, t in enumerate(templates):
        s = t["severity"]
        o = t["occurrence"]
        d = t["detection"]

        # If high operating temperature in mission profile, increase occurrence slightly
        if mission_profile_temperature_c and mission_profile_temperature_c >= 60.0:
            o = min(10, o + 1)

        rpn = s * o * d
        ap = calculate_action_priority(s, o, d)

        s_post = t["residual_severity"]
        o_post = t["residual_occurrence"]
        d_post = t["residual_detection"]
        rpn_post = s_post * o_post * d_post

        entries.append(FmeaEntry(
            id=f"FMEA-{part_number}-{idx + 1}",
            part_number=part_number,
            component_name=component_name,
            subsystem=subsystem,
            intended_function=intended_function or f"Provide {category} function in {subsystem}",
            failure_mode=t["failure_mode"],
            local_effect=t["local_effect"],
            end_system_effect=t["end_system_effect"],
            potential_cause=t["potential_cause"],
            prevention_controls=t["prevention_controls"],
            detection_controls=t["detection_controls"],
            severity=s,
            occurrence=o,
            detection=d,
            rpn=rpn,
            action_priority=ap,
            recommended_action=t["recommended_action"],
            action_owner=t["action_owner"],
            action_status="OPEN",
            residual_severity=s_post,
            residual_occurrence=o_post,
            residual_detection=d_post,
            residual_rpn=rpn_post,
            is_suggested=True,
            evidence_notes="FMEA suggestion generated from category failure taxonomy; requires engineering sign-off.",
        ))

    return entries
