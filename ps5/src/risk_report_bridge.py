import json
from typing import Any, Dict, List

from src.component_catalog import find_component
from src.substitute_engine import recommend_substitutes


def substitutes_for_risk_report(
    report_path: str,
    catalog_path: str = "data/component_specs.csv",
    data_dir: str = "data",
    include_incompatible: bool = True,
) -> Dict[str, Any]:
    """Maps Person 1 JSON risk-report parts to Person 2 substitute results."""
    try:
        with open(report_path, mode="r", encoding="utf-8") as f:
            report = json.load(f)
    except FileNotFoundError:
        return {
            "error": "REPORT_NOT_FOUND",
            "message": f"Risk report not found at '{report_path}'.",
        }
    except json.JSONDecodeError:
        return {
            "error": "INVALID_REPORT",
            "message": f"Risk report at '{report_path}' is not valid JSON.",
        }

    mapped: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []

    for part in report.get("parts", []):
        part_number = part.get("part_number")
        references = part.get("references") or []
        identifiers = [part_number] + references
        component = next((find_component(str(identifier), catalog_path) for identifier in identifiers if identifier), None)

        if component is None:
            unresolved.append(
                {
                    "part_number": part_number,
                    "references": references,
                    "risk_band": part.get("risk_band"),
                    "risk_score": part.get("risk_score"),
                    "reason": "No matching component specification in data/component_specs.csv.",
                }
            )
            continue

        recommendation = recommend_substitutes(
            component.component_id,
            catalog_path=catalog_path,
            data_dir=data_dir,
            include_incompatible=include_incompatible,
        )
        mapped.append(
            {
                "risk_part": part,
                "resolved_component_id": component.component_id,
                "resolved_part_number": component.part_number,
                "physical_location": component.physical_location,
                "substitutes": recommendation,
            }
        )

    return {
        "source_bom": report.get("source_bom"),
        "summary": report.get("summary"),
        "mapped_count": len(mapped),
        "unresolved_count": len(unresolved),
        "mapped": mapped,
        "unresolved": unresolved,
    }
