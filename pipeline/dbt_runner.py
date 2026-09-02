# pipeline/dbt_runner.py — Programmatic & CLI runner for dbt DuckDB pipeline
#
# Runs the Medallion transformation pipeline:
#   Bronze (Staging) → Silver (Intermediate) → Gold (Marts)
# Exports clean Parquet files to data/processed/

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DBT_DIR = PROJECT_ROOT / "dbt"


def run_dbt_command(command: str = "run", extra_args: Optional[List[str]] = None) -> int:
    """
    Execute a dbt command against the local DuckDB profile.

    Args:
        command: dbt command ('run', 'test', 'compile', 'docs generate')
        extra_args: Additional CLI flags (e.g. ['--select', 'fct_cars_ml_features'])

    Returns:
        Return code from the dbt process (0 = success).
    """
    # Ensure all required data & log directories exist
    (PROJECT_ROOT / "data" / "duckdb").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "data" / "silver").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "data" / "gold").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "logs").mkdir(parents=True, exist_ok=True)

    cmd = [
        "dbt",
        command,
        "--project-dir",
        str(DBT_DIR),
        "--profiles-dir",
        str(DBT_DIR),
    ]
    if extra_args:
        cmd.extend(extra_args)

    logger.info(f"Running dbt: {' '.join(cmd)}")
    start_time = time.time()

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    duration = round(time.time() - start_time, 2)

    if result.returncode == 0:
        logger.info(f"dbt {command} completed successfully in {duration}s.")
    else:
        logger.error(f"dbt {command} failed with exit code {result.returncode} ({duration}s).")

    return result.returncode


def run_transformation() -> int:
    """Run `dbt run` followed by `dbt test`."""
    run_code = run_dbt_command("run")
    if run_code != 0:
        return run_code
    return run_dbt_command("test")


def main() -> None:
    """CLI entry point for dbt transformation pipeline."""
    parser = argparse.ArgumentParser(description="Run dbt Car Price Transformation Pipeline")
    parser.add_argument(
        "action",
        nargs="?",
        default="all",
        choices=["run", "test", "all"],
        help="Action to perform: run, test, or all (run + test)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  [%(levelname)-8s]  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if args.action == "run":
        code = run_dbt_command("run")
    elif args.action == "test":
        code = run_dbt_command("test")
    else:
        code = run_transformation()

    sys.exit(code)


if __name__ == "__main__":
    main()
