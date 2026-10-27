from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class PartRiskProfile:
    """
    Unified dataclass representing a BOM part and its enriched supply-chain risk profile.
    Carries data from parsing through merging, dynamic taxonomy inference, scoring, and financial exposure analysis.
    """
    part_number: Optional[str]
    references: List[str] = field(default_factory=list)
    raw_reference_str: str = ""
    qty: int = 1
    
    # Joined / Inferred supply-chain signals
    lifecycle_status: Optional[str] = None       # "Active", "NRND", "Obsolete"
    lead_time_weeks: Optional[int] = None
    stock: Optional[int] = None
    has_second_source: Optional[bool] = None
    criticality: Optional[str] = None            # "Low", "Medium", "High"
    criticality_derived: bool = False
    
    # Financial & Taxonomy metadata
    unit_cost_usd: Optional[float] = None        # Unit cost in USD; None when unmeasured
    financial_exposure_usd: Optional[float] = None # qty * unit_cost_usd * risk_score
    taxonomy_category: str = "General Component"
    is_dynamically_inferred: bool = False
    evidence_status: str = ""
    
    # Gap & Uncertainty tracking
    missing_fields: List[str] = field(default_factory=list)
    confidence_score: float = 1.0                # Fraction of known/trusted fields (0.0 to 1.0)
    
    # Computed risk metrics
    risk_score: Optional[float] = None           # Continuous score (0.0 to 1.0)
    risk_band: Optional[str] = None              # "Low", "Medium", "High", "Critical"
    risk_reasons: List[str] = field(default_factory=list)
    exposure_score: Optional[float] = None        # risk_score * qty
    historical_data: Optional[Dict[str, Any]] = None
    obsolescence_probability_5y: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to serializable dictionary for JSON reporting and UI visualization."""
        return {
            "part_number": self.part_number,
            "references": self.references,
            "raw_reference_str": self.raw_reference_str,
            "qty": self.qty,
            "lifecycle_status": self.lifecycle_status,
            "lead_time_weeks": self.lead_time_weeks,
            "stock": self.stock,
            "has_second_source": self.has_second_source,
            "criticality": self.criticality,
            "criticality_derived": self.criticality_derived,
            "unit_cost_usd": round(self.unit_cost_usd, 2) if self.unit_cost_usd is not None else None,
            "financial_exposure_usd": round(self.financial_exposure_usd, 2) if self.financial_exposure_usd is not None else None,
            "taxonomy_category": self.taxonomy_category,
            "is_dynamically_inferred": self.is_dynamically_inferred,
            "evidence_status": self.evidence_status or ("INFERRED" if self.is_dynamically_inferred else ""),
            "missing_fields": self.missing_fields,
            "confidence_score": round(self.confidence_score, 2),
            "risk_score": round(self.risk_score, 3) if self.risk_score is not None else None,
            "risk_band": self.risk_band,
            "risk_reasons": self.risk_reasons,
            "exposure_score": round(self.exposure_score, 3) if self.exposure_score is not None else None,
            "obsolescence_probability_5y": round(self.obsolescence_probability_5y, 4) if self.obsolescence_probability_5y is not None else None,
        }


@dataclass
class ComponentSpec:
    """
    Engineering specification and supply-chain profile for a concrete component.
    Specs are category-specific and stored in the free-form specs dictionary.
    """
    component_id: str
    part_number: str
    category: str
    manufacturer: Optional[str] = None
    refdes: Optional[str] = None
    package: Optional[str] = None
    lifecycle_status: Optional[str] = None
    lead_time_weeks: Optional[int] = None
    stock: Optional[int] = None
    has_second_source: Optional[bool] = None
    criticality: Optional[str] = None
    physical_location: Optional[str] = None
    specs: Dict[str, Any] = field(default_factory=dict)
    demo_data: bool = False

    def get_spec(self, name: str, default: Any = None) -> Any:
        if name == "package":
            return self.package
        return self.specs.get(name, default)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "part_number": self.part_number,
            "manufacturer": self.manufacturer,
            "refdes": self.refdes,
            "category": self.category,
            "package": self.package,
            "lifecycle_status": self.lifecycle_status,
            "lead_time_weeks": self.lead_time_weeks,
            "stock": self.stock,
            "has_second_source": self.has_second_source,
            "criticality": self.criticality,
            "physical_location": self.physical_location,
            "specs": self.specs,
            "demo_data": self.demo_data,
        }
