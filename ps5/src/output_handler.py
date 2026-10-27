import json
import os
from datetime import datetime
from typing import Dict, Any

def write_json_report(analysis_data: Dict[str, Any], bom_filename: str, output_path: str) -> None:
    """Exports structured analysis report to JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "source_bom": os.path.basename(bom_filename),
        "summary": analysis_data["metrics"],
        "parts": analysis_data["by_severity"]
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

def print_terminal_report(analysis_data: Dict[str, Any], bom_filename: str) -> None:
    """Prints readable terminal summary report."""
    metrics = analysis_data["metrics"]
    parts = analysis_data["by_severity"]
    
    print("\n" + "=" * 90)
    print(f"  BOM SUPPLY CHAIN RISK ANALYSIS REPORT: {os.path.basename(bom_filename)}")
    print("=" * 90)
    
    print(f"Overall Risk Level : [{metrics['overall_bom_risk_band'].upper()}]")
    print(f"Average Risk Score : {metrics['average_risk_score']} / 1.000")
    print(f"Data Completeness  : {int(metrics['average_confidence_score'] * 100)}%")
    print(f"Total Part Types   : {metrics['total_parts']} unique line items ({metrics['total_component_count']} total units)")
    print(f"BOM Cost / Unit    : ${metrics['total_bom_unit_cost_usd']:.2f} USD")
    print(f"Financial Exposure : ${metrics['total_financial_exposure_usd']:.2f} USD (Risk-Weighted Cost-at-Risk)")
    print(f"Risk Band Split    : Critical: {metrics['critical_count']} | High: {metrics['high_count']} | Medium: {metrics['medium_count']} | Low: {metrics['low_count']}\n")
    
    print("-" * 90)
    print(f"{'PART NUMBER':<22} | {'BAND':<9} | {'SCORE':<5} | {'COST':<7} | {'FIN. EXP':<8} | {'RISK EXPLANATIONS & OVERRIDES'}")
    print("-" * 90)
    
    for p in parts:
        pn = p["part_number"] or "<TBD PLACEHOLDER>"
        band = p["risk_band"] or "Unknown"
        score = f"{p['risk_score']:.3f}" if p["risk_score"] is not None else "N/A"
        cost = f"${p['unit_cost_usd']:.2f}" if p.get("unit_cost_usd") is not None else "N/A"
        fin_exp = f"${p['financial_exposure_usd']:.2f}" if p["financial_exposure_usd"] is not None else "N/A"
        
        reasons_str = "; ".join(p["risk_reasons"]) if p["risk_reasons"] else "No specific risk triggers"
        print(f"{pn:<22} | {band:<9} | {score:<5} | {cost:<7} | {fin_exp:<8} | {reasons_str}")
        
    print("=" * 90 + "\n")
