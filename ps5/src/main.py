import argparse
import os
import sys
from typing import List

from src.bom_parser import parse_bom
from src.risk_merger import merge_risk_data
from src.risk_engine import compute_risk
from src.risk_analyzer import analyze_bom_risk
from src.output_handler import write_json_report, print_terminal_report

def run_pipeline(bom_path: str, data_dir: str, output_path: str, quiet: bool = False):
    """Executes full BOM Risk Analysis pipeline."""
    if not os.path.exists(bom_path):
        print(f"Error: BOM file not found at '{bom_path}'", file=sys.stderr)
        sys.exit(1)
        
    if not os.path.exists(data_dir):
        print(f"Error: Data reference directory not found at '{data_dir}'", file=sys.stderr)
        sys.exit(1)
        
    # Stage 1: Parsing
    profiles = parse_bom(bom_path)
    if not profiles:
        print(f"Warning: No valid BOM entries parsed from '{bom_path}'", file=sys.stderr)
        return
    
    # Stage 2: Merging reference data & gap auditing
    profiles = merge_risk_data(profiles, data_dir)
    
    # Stage 3: Risk Scoring & Compounding Rules
    profiles = [compute_risk(p) for p in profiles]
    
    # Stage 4: Prioritization & Analysis
    analysis = analyze_bom_risk(profiles)
    
    # Stage 5: Output Generation
    write_json_report(analysis, bom_path, output_path)
    
    if not quiet:
        print_terminal_report(analysis, bom_path)
        print(f"Full JSON report saved to: [ {output_path} ]\n")
        
    return analysis

def main():
    parser = argparse.ArgumentParser(description="BOM Supply Chain Risk Analysis Engine")
    parser.add_argument("--bom", type=str, default=os.path.join("data", "sample_projects", "bom_burglar_alarm.csv"), help="Path to BOM CSV file")
    parser.add_argument("--data-dir", type=str, default="data", help="Path to reference datasets directory")
    parser.add_argument("--output", type=str, default=os.path.join("outputs", "risk_analysis.json"), help="Output path for JSON report")
    parser.add_argument("--quiet", action="store_true", help="Suppress terminal report output")
    
    args = parser.parse_args()
    run_pipeline(args.bom, args.data_dir, args.output, args.quiet)

if __name__ == "__main__":
    main()
