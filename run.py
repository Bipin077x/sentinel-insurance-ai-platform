import argparse
import subprocess
import sys
import time
import os

def run_command(command: list[str], env: dict[str, str] = None, wait: bool = True):
    print(f"\n[{' '.join(command)}]")
    env_vars = os.environ.copy()
    if env:
        env_vars.update(env)
    # Ensure UTF-8 output on Windows
    env_vars["PYTHONIOENCODING"] = "utf-8"

    if wait:
        result = subprocess.run(command, env=env_vars)
        if result.returncode != 0:
            print(f"Command failed with exit code {result.returncode}", file=sys.stderr)
            sys.exit(result.returncode)
    else:
        # Run in background
        return subprocess.Popen(command, env=env_vars)

def main():
    parser = argparse.ArgumentParser(description="AI Insurance Platform POC Runner")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    subparsers.add_parser("brokerage", help="Run the Brokerage pipeline")
    subparsers.add_parser("underwriting", help="Run the Underwriting pipeline")
    
    claims_parser = subparsers.add_parser("claims", help="Run the Claims pipeline")
    subparsers.add_parser("claims_adapters", help="Run the Claims pipeline with integration adapters (Requires mock server to be running)")

    subparsers.add_parser("audit", help="Run the Financial Audit pipeline (Anomaly Detection & Review)")
    subparsers.add_parser("verify", help="Run Cryptographic Chain Verification")
    subparsers.add_parser("benchmarks", help="Run Business Outcome Benchmarks")
    subparsers.add_parser("review", help="Launch the Human Review CLI")
    subparsers.add_parser("mock_server", help="Start the Integration Mock Server")

    subparsers.add_parser("all", help="Run all automated pipelines sequentially (Brokerage, Underwriting, Claims, Audit, Verify, Benchmarks)")

    args = parser.parse_args()

    # Always prefer the virtual environment's Python
    venv_python = os.path.join(os.path.dirname(__file__), "venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        python_exe = venv_python
    else:
        python_exe = sys.executable

    if args.command == "brokerage":
        run_command([python_exe, "-m", "brokerage.run_brokerage"])
    elif args.command == "underwriting":
        run_command([python_exe, "-m", "underwriting.run_underwriting"])
    elif args.command == "claims":
        run_command([python_exe, "-m", "claims.run_claims"])
    elif args.command == "claims_adapters":
        run_command([python_exe, "-m", "claims.run_claims", "--use-adapters"])
    elif args.command == "audit":
        run_command([python_exe, "-m", "audit.run_audit"])
    elif args.command == "verify":
        run_command([python_exe, "-m", "audit.chain_verify"])
    elif args.command == "benchmarks":
        run_command([python_exe, "-m", "benchmarks.run_benchmarks"])
    elif args.command == "review":
        run_command([python_exe, "-m", "review.cli"])
    elif args.command == "mock_server":
        run_command([python_exe, "-m", "uvicorn", "integrations.mock_server:app", "--port", "8765"])
    elif args.command == "all":
        print("Running all automated pipelines...")
        run_command([python_exe, "-m", "brokerage.run_brokerage"])
        run_command([python_exe, "-m", "underwriting.run_underwriting"])
        run_command([python_exe, "-m", "claims.run_claims"])
        run_command([python_exe, "-m", "audit.run_audit"])
        run_command([python_exe, "-m", "audit.chain_verify"])
        run_command([python_exe, "-m", "benchmarks.run_benchmarks"])
        print("\nAll automated pipelines completed successfully!")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
