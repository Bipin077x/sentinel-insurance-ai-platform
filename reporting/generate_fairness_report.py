import os
import sys
import argparse
import io
from contextlib import redirect_stdout
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from underwriting.fairness_eval import evaluate_fairness
from reporting.utils import save_and_log_report

def generate_fairness_report(pipeline: str) -> str:
    """
    Wraps the existing fairness_eval.py output into the reporting format
    and prominently includes standing limitation notes.
    """
    if pipeline != "underwriting":
        print("Fairness eval currently only supports the 'underwriting' pipeline.")
        sys.exit(1)
        
    now_ts = datetime.now(timezone.utc).isoformat()
    
    # Capture the print-based output of evaluate_fairness()
    buf = io.StringIO()
    with redirect_stdout(buf):
        evaluate_fairness()
    eval_output = buf.getvalue()
    
    md = f"# Fairness Summary Report\n\n"
    md += f"**Pipeline:** {pipeline}\n"
    md += f"**Generated At:** {now_ts}\n\n"
    
    md += "> [!CAUTION]\n"
    md += "> **STRUCTURAL LIMITATIONS OF THIS REPORT**\n"
    md += ">\n"
    md += "> **This report must NOT be interpreted as validation that this system is fair.**\n"
    md += ">\n"
    md += "> 1. **Synthetic Demographic Data Only**: The data evaluated here is entirely synthetic. It does not represent a real population distribution and has not been sourced through legally validated inference methods (e.g., BISG). Results cannot be generalized to production use.\n"
    md += ">\n"
    md += "> 2. **Maximal Signal Testing Only**: This evaluation tests for extreme, direct, near-perfect correlations with protected attributes. It provides no evidence about subtle, real-world proxy correlations (e.g., zip code, employment sector, trip destination correlating with protected classes). A clean result here means only that egregious explicit bias was not detected — not that no disparate impact exists.\n"
    md += ">\n"
    md += "> **Regulatory Use**: This report is a development-stage POC artifact, not a regulatory compliance submission.\n\n"
    
    md += f"## 1. Fairness Evaluation Output\n"
    md += f"```text\n{eval_output}\n```\n\n"
    
    return md

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate fairness report.")
    parser.add_argument("--pipeline", required=True, help="Must be 'underwriting'")
    args = parser.parse_args()
    
    report_md = generate_fairness_report(args.pipeline)
    
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"fairness_{args.pipeline}_{ts_str}.md"
    
    saved_path = save_and_log_report(
        report_content=report_md, 
        report_type="fairness", 
        filters={"pipeline": args.pipeline}, 
        filename=filename
    )
    
    print(f"Report successfully generated and logged: {saved_path}")
