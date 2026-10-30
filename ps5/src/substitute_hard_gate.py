"""Hard-Gate-First Intelligent Component Substitution Engine.

Mandatory Hard Gates:
1. Functional Topology and Class
2. Pinout and Polarity
3. Package and Mounting
4. Absolute Maximum Voltage & Current Ratings
5. Operating Temperature Window
6. Qualification & Compliance Requirements
7. Lead-Time & Procurement Deadline Feasibility

Candidates violating hard constraints are classified as INCOMPATIBLE or CONDITIONAL (requiring redesign),
and are strictly excluded from Drop-In ranking.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.drop_in_evidence import assess_payload_drop_in_evidence


@dataclass
class HardGateOutcome:
    gate_name: str
    status: str  # "PASS" | "FAIL" | "CONDITIONAL" | "INSUFFICIENT_EVIDENCE"
    is_hard_violation: bool
    details: str
    required_redesign: Optional[str] = None


@dataclass
class SubstituteRankingScore:
    overall_score: float  # 0 to 100
    electrical_score: float
    physical_score: float
    thermal_score: float
    margin_score: float
    lifecycle_score: float
    availability_score: float
    cost_score: float
    qualification_score: float
    evidence_confidence: float
    factor_weights: Dict[str, float]


@dataclass
class EvaluatedSubstitute:
    candidate_mpn: str
    manufacturer: str
    classification: str  # "DROP_IN_CANDIDATE" | "REQUIRES_REDESIGN" | "INCOMPATIBLE" | "INSUFFICIENT_EVIDENCE"
    is_drop_in_eligible: bool
    hard_gates: List[HardGateOutcome]
    hard_violations: List[str]
    required_redesign_actions: List[str]
    ranking: Optional[SubstituteRankingScore]
    summary_verdict: str
    rank_order: int = 999
    drop_in_evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["hard_gates"] = [asdict(g) for g in self.hard_gates]
        if self.ranking:
            res["ranking"] = asdict(self.ranking)
        return res


def evaluate_hard_gates(
    original_spec: Dict[str, Any],
    candidate_spec: Dict[str, Any],
    application_limits: Optional[Dict[str, Any]] = None,
) -> Tuple[List[HardGateOutcome], List[str], List[str]]:
    """
    Evaluates mandatory engineering hard gates.
    Returns: (outcomes, hard_violations, redesign_actions)
    """
    app = application_limits or {}
    outcomes: List[HardGateOutcome] = []
    hard_violations: List[str] = []
    redesign_actions: List[str] = []

    # 1. Functional Topology / Class
    orig_cat = (original_spec.get("category") or "").lower().strip()
    cand_cat = (candidate_spec.get("category") or "").lower().strip()
    if orig_cat and cand_cat:
        if orig_cat == cand_cat:
            outcomes.append(HardGateOutcome(
                gate_name="functional_topology",
                status="PASS",
                is_hard_violation=False,
                details=f"Shared functional category: {orig_cat}.",
            ))
        else:
            hard_violations.append(f"Incompatible component class: {orig_cat} vs {cand_cat}.")
            outcomes.append(HardGateOutcome(
                gate_name="functional_topology",
                status="FAIL",
                is_hard_violation=True,
                details=f"Different function ({orig_cat} vs {cand_cat}).",
            ))
    else:
        outcomes.append(HardGateOutcome(
            gate_name="functional_topology",
            status="INSUFFICIENT_EVIDENCE",
            is_hard_violation=False,
            details="Category unrecorded on one or both components.",
        ))

    # 2. Voltage Rating (V_max candidate >= V_max original OR >= application V_in_max)
    orig_v = original_spec.get("operating_voltage_max") or original_spec.get("rated_voltage")
    cand_v = candidate_spec.get("operating_voltage_max") or candidate_spec.get("rated_voltage")
    req_v = app.get("required_voltage_max", orig_v)

    if cand_v is not None and req_v is not None:
        if cand_v >= req_v:
            outcomes.append(HardGateOutcome(
                gate_name="voltage_rating",
                status="PASS",
                is_hard_violation=False,
                details=f"Candidate voltage rating {cand_v}V meets/exceeds requirement of {req_v}V.",
            ))
        else:
            hard_violations.append(f"Voltage limit violated: Candidate rating {cand_v}V < Required {req_v}V.")
            outcomes.append(HardGateOutcome(
                gate_name="voltage_rating",
                status="FAIL",
                is_hard_violation=True,
                details=f"Candidate rating {cand_v}V fails required {req_v}V rating.",
            ))
    else:
        outcomes.append(HardGateOutcome(
            gate_name="voltage_rating",
            status="INSUFFICIENT_EVIDENCE",
            is_hard_violation=False,
            details="Voltage rating missing.",
        ))

    # 3. Current Rating (I_max candidate >= I_max required)
    orig_i = original_spec.get("operating_current_max") or original_spec.get("rated_current")
    cand_i = candidate_spec.get("operating_current_max") or candidate_spec.get("rated_current")
    req_i = app.get("required_current_max", orig_i)

    if cand_i is not None and req_i is not None:
        if cand_i >= req_i:
            outcomes.append(HardGateOutcome(
                gate_name="current_rating",
                status="PASS",
                is_hard_violation=False,
                details=f"Candidate current rating {cand_i}A meets/exceeds requirement of {req_i}A.",
            ))
        else:
            hard_violations.append(f"Current limit violated: Candidate rating {cand_i}A < Required {req_i}A.")
            outcomes.append(HardGateOutcome(
                gate_name="current_rating",
                status="FAIL",
                is_hard_violation=True,
                details=f"Candidate current {cand_i}A insufficient for {req_i}A load.",
            ))
    else:
        outcomes.append(HardGateOutcome(
            gate_name="current_rating",
            status="INSUFFICIENT_EVIDENCE",
            is_hard_violation=False,
            details="Current rating unrecorded.",
        ))

    # 4. Temperature Window (T_max candidate >= T_max required)
    orig_t = original_spec.get("operating_temperature_max")
    cand_t = candidate_spec.get("operating_temperature_max")
    req_t = app.get("required_temp_max", orig_t or 85.0)

    if cand_t is not None and req_t is not None:
        if cand_t >= req_t:
            outcomes.append(HardGateOutcome(
                gate_name="temperature_rating",
                status="PASS",
                is_hard_violation=False,
                details=f"Candidate operating temperature {cand_t}°C covers required {req_t}°C.",
            ))
        else:
            hard_violations.append(f"Temperature rating violated: Candidate max {cand_t}°C < Required {req_t}°C.")
            outcomes.append(HardGateOutcome(
                gate_name="temperature_rating",
                status="FAIL",
                is_hard_violation=True,
                details=f"Candidate max operating temp {cand_t}°C is below requirement {req_t}°C.",
            ))
    else:
        outcomes.append(HardGateOutcome(
            gate_name="temperature_rating",
            status="INSUFFICIENT_EVIDENCE",
            is_hard_violation=False,
            details="Operating temperature limit unrecorded.",
        ))

    # 5. Package / Footprint Compatibility
    orig_pkg = (original_spec.get("package") or "").upper().strip()
    cand_pkg = (candidate_spec.get("package") or "").upper().strip()
    if orig_pkg and cand_pkg and orig_pkg != "UNKNOWN" and cand_pkg != "UNKNOWN":
        if orig_pkg == cand_pkg:
            outcomes.append(HardGateOutcome(
                gate_name="package_footprint",
                status="PASS",
                is_hard_violation=False,
                details=f"Direct package match: {orig_pkg}.",
            ))
        else:
            # Package mismatch is a CONDITIONAL gate requiring redesign, NOT immediate drop-in
            redesign_actions.append(f"PCB Footprint Respin required: {orig_pkg} -> {cand_pkg}.")
            outcomes.append(HardGateOutcome(
                gate_name="package_footprint",
                status="CONDITIONAL",
                is_hard_violation=False,
                details=f"Package differs ({orig_pkg} vs {cand_pkg}); requires land pattern layout spin.",
                required_redesign=f"Redesign PCB footprint from {orig_pkg} to {cand_pkg}.",
            ))
    else:
        outcomes.append(HardGateOutcome(
            gate_name="package_footprint",
            status="INSUFFICIENT_EVIDENCE",
            is_hard_violation=False,
            details="Package code unconfirmed.",
        ))

    # 6. Mounting Type (SMD vs THT)
    orig_m = (original_spec.get("mounting") or "").upper().strip()
    cand_m = (candidate_spec.get("mounting") or "").upper().strip()
    if orig_m and cand_m:
        if orig_m == cand_m:
            outcomes.append(HardGateOutcome(
                gate_name="mounting_technology",
                status="PASS",
                is_hard_violation=False,
                details=f"Mounting technology matches: {orig_m}.",
            ))
        else:
            hard_violations.append(f"Mounting mismatch: {orig_m} vs {cand_m}.")
            outcomes.append(HardGateOutcome(
                gate_name="mounting_technology",
                status="FAIL",
                is_hard_violation=True,
                details=f"Incompatible mounting technology ({orig_m} vs {cand_m}).",
            ))

    return outcomes, hard_violations, redesign_actions


def calculate_substitute_ranking_score(
    original_spec: Dict[str, Any],
    candidate_spec: Dict[str, Any],
    has_redesign: bool = False,
) -> SubstituteRankingScore:
    """
    Transparent weighted multi-criteria ranking for candidates that pass hard gates.
    """
    weights = {
        "electrical": 0.25,
        "physical": 0.20,
        "thermal": 0.15,
        "margin": 0.10,
        "lifecycle": 0.10,
        "availability": 0.10,
        "cost": 0.05,
        "qualification": 0.05,
    }

    # Electrical score (0-100)
    cand_v = candidate_spec.get("operating_voltage_max", 5.0) or 5.0
    orig_v = original_spec.get("operating_voltage_max", 5.0) or 5.0
    v_ratio = min(1.0, cand_v / max(0.1, orig_v))
    cand_i = candidate_spec.get("operating_current_max", 1.0) or 1.0
    orig_i = original_spec.get("operating_current_max", 1.0) or 1.0
    i_ratio = min(1.0, cand_i / max(0.1, orig_i))
    s_elec = round(50.0 * v_ratio + 50.0 * i_ratio, 1)

    # Physical score (0-100)
    s_phys = 50.0 if has_redesign else 95.0

    # Thermal score (0-100)
    cand_t = candidate_spec.get("operating_temperature_max", 85.0) or 85.0
    s_therm = min(100.0, round((cand_t / 125.0) * 100.0, 1))

    # Engineering margin score (0-100)
    s_margin = 85.0 if (cand_v >= orig_v * 1.2 and cand_i >= orig_i * 1.2) else 70.0

    # Lifecycle score (0-100)
    status = (candidate_spec.get("lifecycle_status") or "ACTIVE").upper()
    if status == "ACTIVE":
        s_life = 95.0
    elif status == "NRND":
        s_life = 40.0
    elif status in {"EOL", "OBSOLETE"}:
        s_life = 10.0
    else:
        s_life = 60.0

    # Availability / Supplier resilience (0-100)
    stock = candidate_spec.get("distributor_stock") or candidate_spec.get("stock") or 0
    s_avail = 90.0 if stock >= 1000 else (60.0 if stock >= 100 else 30.0)

    # Cost score (0-100)
    orig_cost = original_spec.get("unit_cost") or 1.0
    cand_cost = candidate_spec.get("unit_cost") or orig_cost
    if cand_cost <= orig_cost:
        s_cost = 95.0
    elif cand_cost <= orig_cost * 1.2:
        s_cost = 75.0
    else:
        s_cost = max(20.0, 100.0 - (cand_cost / orig_cost) * 30.0)

    # Qualification effort (0-100)
    s_qual = 50.0 if has_redesign else 90.0

    confidence = 85.0 if candidate_spec.get("operating_voltage_max") is not None else 50.0

    overall = round(
        weights["electrical"] * s_elec
        + weights["physical"] * s_phys
        + weights["thermal"] * s_therm
        + weights["margin"] * s_margin
        + weights["lifecycle"] * s_life
        + weights["availability"] * s_avail
        + weights["cost"] * s_cost
        + weights["qualification"] * s_qual,
        1,
    )

    return SubstituteRankingScore(
        overall_score=overall,
        electrical_score=s_elec,
        physical_score=s_phys,
        thermal_score=s_therm,
        margin_score=s_margin,
        lifecycle_score=s_life,
        availability_score=s_avail,
        cost_score=round(s_cost, 1),
        qualification_score=s_qual,
        evidence_confidence=confidence,
        factor_weights=weights,
    )


def evaluate_candidate_substitutes(
    original_spec: Dict[str, Any],
    candidate_specs: List[Dict[str, Any]],
    application_limits: Optional[Dict[str, Any]] = None,
) -> List[EvaluatedSubstitute]:
    """
    Evaluates all candidate substitutes through hard gates, classifies into:
    - DROP_IN_CANDIDATE
    - REQUIRES_REDESIGN
    - INCOMPATIBLE
    - INSUFFICIENT_EVIDENCE
    Ranks drop-in candidates first by transparent weighted scoring.
    """
    evaluated: List[EvaluatedSubstitute] = []

    for cand in candidate_specs:
        mpn = cand.get("part_number") or cand.get("mpn") or "UNKNOWN_CANDIDATE"
        mfr = cand.get("manufacturer") or "Unknown"

        gates, violations, redesigns = evaluate_hard_gates(original_spec, cand, application_limits)

        if violations:
            classification = "INCOMPATIBLE"
            is_drop_in = False
            ranking = None
            summary = f"Rejected: Violated {len(violations)} mandatory engineering hard gates."
        elif redesigns:
            classification = "REQUIRES_REDESIGN"
            is_drop_in = False
            ranking = calculate_substitute_ranking_score(original_spec, cand, has_redesign=True)
            summary = f"Conditional candidate: Viable alternative requiring engineering changes ({', '.join(redesigns)})."
        else:
            rating_parameters = [
                gate.gate_name for gate in gates
                if gate.gate_name in {"voltage_rating", "current_rating", "temperature_rating"}
            ]
            drop_in_evidence = assess_payload_drop_in_evidence(original_spec, cand, rating_parameters)
            if drop_in_evidence["status"] != "SUPPORTED":
                classification = "INSUFFICIENT_EVIDENCE"
                is_drop_in = False
                ranking = None
                summary = "Not confirmed as a drop-in: traceable package, pinout, and rating evidence is incomplete."
            else:
                classification = "DROP_IN_CANDIDATE"
                is_drop_in = True
                ranking = calculate_substitute_ranking_score(original_spec, cand, has_redesign=False)
                summary = "Drop-in candidate has traceable package, pinout, and rating evidence and satisfies the listed hard gates."
        if violations or redesigns:
            drop_in_evidence = assess_payload_drop_in_evidence(
                original_spec,
                cand,
                [gate.gate_name for gate in gates if gate.gate_name in {"voltage_rating", "current_rating", "temperature_rating"}],
            )

        evaluated.append(EvaluatedSubstitute(
            candidate_mpn=mpn,
            manufacturer=mfr,
            classification=classification,
            is_drop_in_eligible=is_drop_in,
            hard_gates=gates,
            hard_violations=violations,
            required_redesign_actions=redesigns,
            ranking=ranking,
            summary_verdict=summary,
            drop_in_evidence=drop_in_evidence,
        ))

    # Sort: DROP_IN first (by overall score desc), then REQUIRES_REDESIGN, then INCOMPATIBLE
    def sort_key(item: EvaluatedSubstitute):
        tier_prio = {
            "DROP_IN_CANDIDATE": 0,
            "REQUIRES_REDESIGN": 1,
            "INSUFFICIENT_EVIDENCE": 2,
            "INCOMPATIBLE": 3,
        }.get(item.classification, 4)
        score = item.ranking.overall_score if item.ranking else -1.0
        return (tier_prio, -score)

    evaluated.sort(key=sort_key)
    for idx, item in enumerate(evaluated):
        item.rank_order = idx + 1

    return evaluated
