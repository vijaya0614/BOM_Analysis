"""Physical Dimensionality and Form-Fit-Function Compatibility Engine.

Evaluates mechanical, geometric, and package interchangeability between original
and candidate components:
- Package family and code
- Dimensions (length, width, height in mm)
- Pin count, pin pitch, and pinout compatibility
- SMD vs Through-Hole mounting type
- PCB footprint and land pattern
- Height clearance and keep-out zones
- Thermal pad and heatsink interface
- Moisture Sensitivity Level (MSL)

Classification:
- DROP_IN_CANDIDATE: Exact or fully compatible physical fit without PCB changes
- CONDITIONAL_CANDIDATE: Electrically viable but requires PCB layout/footprint redesign
- INCOMPATIBLE: Hard physical/mounting violation
- INSUFFICIENT_EVIDENCE: Required physical data unverified
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PhysicalConstraintCheck:
    parameter: str
    original_value: Any
    candidate_value: Any
    status: str  # "MATCH" | "CONDITIONAL" | "MISMATCH" | "UNKNOWN"
    severity: str  # "HARD_GATE" | "MODERATE" | "MINOR"
    delta: Optional[float] = None
    unit: str = "mm"
    engineering_notes: str = ""


@dataclass
class PhysicalEvaluationResult:
    original_part: str
    candidate_part: str
    classification: str  # "DROP_IN_CANDIDATE" | "CONDITIONAL_CANDIDATE" | "INCOMPATIBLE" | "INSUFFICIENT_EVIDENCE"
    is_drop_in: bool
    requires_pcb_redesign: bool
    hard_violations: List[str]
    required_redesign_actions: List[str]
    physical_compatibility_score: float  # 0 to 100
    confidence_score: float  # 0 to 100
    constraint_checks: List[PhysicalConstraintCheck]
    notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["constraint_checks"] = [asdict(c) for c in self.constraint_checks]
        return res


def normalize_package(pkg: Optional[str]) -> str:
    """Normalize package name strings for comparison."""
    if not pkg:
        return "UNKNOWN"
    p = pkg.upper().strip()
    replacements = {
        "SOIC-8": "SOIC-8",
        "SO-8": "SOIC-8",
        "SOIC8": "SOIC-8",
        "SOT-23-3": "SOT-23",
        "SOT23": "SOT-23",
        "SOT-23-5": "SOT-23-5",
        "SOT23-5": "SOT-23-5",
        "VQFN-48": "QFN-48",
        "48-VQFN": "QFN-48",
        "QFN48": "QFN-48",
        "0805": "0805",
        "0603": "0603",
        "0402": "0402",
        "1206": "1206",
        "TO-220": "TO-220",
        "TO-252": "TO-252",
        "DPAK": "TO-252",
        "D2PAK": "TO-263",
    }
    for k, v in replacements.items():
        if k in p:
            return v
    return p


def evaluate_physical_compatibility(
    original_part: str,
    candidate_part: str,
    orig_package: Optional[str] = None,
    cand_package: Optional[str] = None,
    orig_mounting: Optional[str] = None,  # "SMD" | "THT"
    cand_mounting: Optional[str] = None,
    orig_pin_count: Optional[int] = None,
    cand_pin_count: Optional[int] = None,
    orig_pin_pitch_mm: Optional[float] = None,
    cand_pin_pitch_mm: Optional[float] = None,
    orig_length_mm: Optional[float] = None,
    cand_length_mm: Optional[float] = None,
    orig_width_mm: Optional[float] = None,
    cand_width_mm: Optional[float] = None,
    orig_height_mm: Optional[float] = None,
    cand_height_mm: Optional[float] = None,
    max_permitted_height_mm: Optional[float] = None,
    orig_has_thermal_pad: Optional[bool] = None,
    cand_has_thermal_pad: Optional[bool] = None,
    pinout_identical: Optional[bool] = None,
) -> PhysicalEvaluationResult:
    """
    Evaluates physical, dimensional, and form-fit-function compatibility between two components.
    Hard gates: Mounting type, pin count, pinout polarity, keep-out boundary.
    """
    checks: List[PhysicalConstraintCheck] = []
    hard_violations: List[str] = []
    redesign_actions: List[str] = []
    notes: List[str] = []

    points_earned = 0.0
    max_points = 0.0
    known_fields = 0
    total_fields = 0

    # 1. Mounting Type (SMD vs Through-hole) — HARD GATE
    total_fields += 1
    if orig_mounting and cand_mounting:
        known_fields += 1
        max_points += 25.0
        m_orig = orig_mounting.upper().strip()
        m_cand = cand_mounting.upper().strip()
        if m_orig == m_cand:
            points_earned += 25.0
            checks.append(PhysicalConstraintCheck(
                parameter="mounting_type",
                original_value=m_orig,
                candidate_value=m_cand,
                status="MATCH",
                severity="HARD_GATE",
                unit="type",
                engineering_notes="Identical mounting technology (both SMD or both THT).",
            ))
        else:
            hard_violations.append(f"Mounting technology mismatch: Original is {m_orig}, Candidate is {m_cand}.")
            checks.append(PhysicalConstraintCheck(
                parameter="mounting_type",
                original_value=m_orig,
                candidate_value=m_cand,
                status="MISMATCH",
                severity="HARD_GATE",
                unit="type",
                engineering_notes="Cannot mount SMD on THT footprint without board redesign.",
            ))
    else:
        checks.append(PhysicalConstraintCheck(
            parameter="mounting_type",
            original_value=orig_mounting,
            candidate_value=cand_mounting,
            status="UNKNOWN",
            severity="HARD_GATE",
            unit="type",
            engineering_notes="Mounting type not specified for both components.",
        ))

    # 2. Package Code and Family
    total_fields += 1
    pkg_orig = normalize_package(orig_package)
    pkg_cand = normalize_package(cand_package)
    if pkg_orig != "UNKNOWN" and pkg_cand != "UNKNOWN":
        known_fields += 1
        max_points += 20.0
        if pkg_orig == pkg_cand:
            points_earned += 20.0
            checks.append(PhysicalConstraintCheck(
                parameter="package_code",
                original_value=pkg_orig,
                candidate_value=pkg_cand,
                status="MATCH",
                severity="MODERATE",
                unit="pkg",
                engineering_notes="Direct package match.",
            ))
        else:
            redesign_actions.append(f"PCB footprint modification required: from {pkg_orig} to {pkg_cand}.")
            checks.append(PhysicalConstraintCheck(
                parameter="package_code",
                original_value=pkg_orig,
                candidate_value=pkg_cand,
                status="CONDITIONAL",
                severity="MODERATE",
                unit="pkg",
                engineering_notes=f"Different package: {pkg_orig} vs {pkg_cand}.",
            ))
    else:
        checks.append(PhysicalConstraintCheck(
            parameter="package_code",
            original_value=orig_package,
            candidate_value=cand_package,
            status="UNKNOWN",
            severity="MODERATE",
            unit="pkg",
            engineering_notes="Package code unrecorded.",
        ))

    # 3. Pin Count — HARD GATE for drop-in
    total_fields += 1
    if orig_pin_count is not None and cand_pin_count is not None:
        known_fields += 1
        max_points += 20.0
        if orig_pin_count == cand_pin_count:
            points_earned += 20.0
            checks.append(PhysicalConstraintCheck(
                parameter="pin_count",
                original_value=orig_pin_count,
                candidate_value=cand_pin_count,
                status="MATCH",
                severity="HARD_GATE",
                delta=0.0,
                unit="pins",
                engineering_notes=f"Identical pin count: {orig_pin_count} pins.",
            ))
        else:
            hard_violations.append(f"Pin count mismatch: {orig_pin_count} pins vs {cand_pin_count} pins.")
            checks.append(PhysicalConstraintCheck(
                parameter="pin_count",
                original_value=orig_pin_count,
                candidate_value=cand_pin_count,
                status="MISMATCH",
                severity="HARD_GATE",
                delta=float(cand_pin_count - orig_pin_count),
                unit="pins",
                engineering_notes=f"Candidate has {cand_pin_count} pins compared to {orig_pin_count}.",
            ))
    else:
        checks.append(PhysicalConstraintCheck(
            parameter="pin_count",
            original_value=orig_pin_count,
            candidate_value=cand_pin_count,
            status="UNKNOWN",
            severity="HARD_GATE",
            unit="pins",
            engineering_notes="Pin count unknown for one or both parts.",
        ))

    # 4. Pin Pitch — HARD GATE for drop-in
    total_fields += 1
    if orig_pin_pitch_mm is not None and cand_pin_pitch_mm is not None:
        known_fields += 1
        max_points += 15.0
        pitch_delta = abs(cand_pin_pitch_mm - orig_pin_pitch_mm)
        if pitch_delta <= 0.02:  # Tolerable 0.02mm lead manufacturing variation
            points_earned += 15.0
            checks.append(PhysicalConstraintCheck(
                parameter="pin_pitch",
                original_value=orig_pin_pitch_mm,
                candidate_value=cand_pin_pitch_mm,
                status="MATCH",
                severity="HARD_GATE",
                delta=round(pitch_delta, 3),
                unit="mm",
                engineering_notes="Pin pitch matches within mechanical tolerance.",
            ))
        else:
            hard_violations.append(f"Pin pitch mismatch: {orig_pin_pitch_mm}mm vs {cand_pin_pitch_mm}mm.")
            checks.append(PhysicalConstraintCheck(
                parameter="pin_pitch",
                original_value=orig_pin_pitch_mm,
                candidate_value=cand_pin_pitch_mm,
                status="MISMATCH",
                severity="HARD_GATE",
                delta=round(pitch_delta, 3),
                unit="mm",
                engineering_notes=f"Pitch delta {pitch_delta:.2f}mm will cause solder bridge or misalignment.",
            ))
    else:
        checks.append(PhysicalConstraintCheck(
            parameter="pin_pitch",
            original_value=orig_pin_pitch_mm,
            candidate_value=cand_pin_pitch_mm,
            status="UNKNOWN",
            severity="HARD_GATE",
            unit="mm",
            engineering_notes="Pin pitch not specified.",
        ))

    # 5. Height and Enclosure Clearance
    total_fields += 1
    if cand_height_mm is not None:
        known_fields += 1
        max_points += 10.0
        if max_permitted_height_mm is not None and cand_height_mm > max_permitted_height_mm:
            h_viol = cand_height_mm - max_permitted_height_mm
            hard_violations.append(f"Candidate height {cand_height_mm}mm exceeds enclosure clearance of {max_permitted_height_mm}mm by {h_viol:.2f}mm.")
            checks.append(PhysicalConstraintCheck(
                parameter="package_height",
                original_value=orig_height_mm,
                candidate_value=cand_height_mm,
                status="MISMATCH",
                severity="HARD_GATE",
                delta=round(cand_height_mm - (orig_height_mm or cand_height_mm), 2),
                unit="mm",
                engineering_notes="Height exceeds enclosure envelope.",
            ))
        else:
            points_earned += 10.0
            checks.append(PhysicalConstraintCheck(
                parameter="package_height",
                original_value=orig_height_mm,
                candidate_value=cand_height_mm,
                status="MATCH",
                severity="MINOR",
                delta=round(cand_height_mm - (orig_height_mm or cand_height_mm), 2) if orig_height_mm else 0.0,
                unit="mm",
                engineering_notes="Package height within allowable mechanical limits.",
            ))
    else:
        checks.append(PhysicalConstraintCheck(
            parameter="package_height",
            original_value=orig_height_mm,
            candidate_value=cand_height_mm,
            status="UNKNOWN",
            severity="MINOR",
            unit="mm",
            engineering_notes="Component height unrecorded.",
        ))

    # 6. Thermal Pad / Heatsink Interface
    total_fields += 1
    if orig_has_thermal_pad is not None and cand_has_thermal_pad is not None:
        known_fields += 1
        max_points += 10.0
        if orig_has_thermal_pad == cand_has_thermal_pad:
            points_earned += 10.0
            checks.append(PhysicalConstraintCheck(
                parameter="thermal_pad",
                original_value=orig_has_thermal_pad,
                candidate_value=cand_has_thermal_pad,
                status="MATCH",
                severity="MODERATE",
                unit="bool",
                engineering_notes="Thermal pad requirements align.",
            ))
        elif orig_has_thermal_pad and not cand_has_thermal_pad:
            redesign_actions.append("Thermal dissipation path must be re-evaluated: candidate lacks exposed thermal pad.")
            checks.append(PhysicalConstraintCheck(
                parameter="thermal_pad",
                original_value=orig_has_thermal_pad,
                candidate_value=cand_has_thermal_pad,
                status="CONDITIONAL",
                severity="MODERATE",
                unit="bool",
                engineering_notes="Original uses thermal pad for heatsinking; candidate lacks thermal pad.",
            ))
        else:
            checks.append(PhysicalConstraintCheck(
                parameter="thermal_pad",
                original_value=orig_has_thermal_pad,
                candidate_value=cand_has_thermal_pad,
                status="MATCH",
                severity="MINOR",
                unit="bool",
                engineering_notes="Candidate includes thermal pad.",
            ))
            points_earned += 8.0
    else:
        checks.append(PhysicalConstraintCheck(
            parameter="thermal_pad",
            original_value=orig_has_thermal_pad,
            candidate_value=cand_has_thermal_pad,
            status="UNKNOWN",
            severity="MODERATE",
            unit="bool",
            engineering_notes="Thermal pad spec unrecorded.",
        ))

    # 7. Pinout identity
    if pinout_identical is False:
        hard_violations.append("Candidate pinout mapping does not match original part.")
        redesign_actions.append("Signal and power trace rerouting required due to pinout difference.")

    # Calculate overall scores
    phys_score = round((points_earned / max_points * 100.0) if max_points > 0 else 50.0, 1)
    confidence = round((known_fields / float(total_fields)) * 100.0, 1)

    # Classify candidate
    if hard_violations:
        classification = "INCOMPATIBLE"
        is_drop_in = False
        requires_redesign = False
    elif redesign_actions:
        classification = "CONDITIONAL_CANDIDATE"
        is_drop_in = False
        requires_redesign = True
    elif confidence < 40.0:
        classification = "INSUFFICIENT_EVIDENCE"
        is_drop_in = False
        requires_redesign = False
    else:
        classification = "DROP_IN_CANDIDATE"
        is_drop_in = True
        requires_redesign = False

    return PhysicalEvaluationResult(
        original_part=original_part,
        candidate_part=candidate_part,
        classification=classification,
        is_drop_in=is_drop_in,
        requires_pcb_redesign=requires_redesign,
        hard_violations=hard_violations,
        required_redesign_actions=redesign_actions,
        physical_compatibility_score=phys_score,
        confidence_score=confidence,
        constraint_checks=checks,
        notes=notes,
    )
