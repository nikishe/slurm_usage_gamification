#!/usr/bin/env python3
"""
Batch HPC Job Report Runner
Reads usernames from a CSV file and runs hpc_job_report_parrallel.py for each.

Usage: python3 run_reports_for_users.py <users.csv> [--column NAME] [--workers N]
"""

import csv
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRIPT = Path(__file__).parent / "hpc_job_report_parrallel.py"
DEFAULT_WORKERS = os.cpu_count() or 4


def load_usernames(csv_path: str, column: str | None) -> list[str]:
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            col = column or reader.fieldnames[0]
            if col not in reader.fieldnames:
                sys.exit(f"Column '{col}' not found. Available: {reader.fieldnames}")
            return [row[col].strip() for row in reader if row[col].strip()]
        f.seek(0)
        return [row[0].strip() for row in csv.reader(f) if row and row[0].strip()]


def run_report(user: str) -> tuple[str, int]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), user],
        cwd=SCRIPT.parent,
        capture_output=True,
        text=True,
    )
    return user, result.returncode, result.stdout, result.stderr


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python3 run_reports_for_users.py <users.csv> [--column NAME] [--workers N]")

    csv_path = sys.argv[1]
    column, workers = None, DEFAULT_WORKERS

    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--column" and i + 1 < len(args):
            column = args[i + 1]; i += 2
        elif args[i] == "--workers" and i + 1 < len(args):
            workers = int(args[i + 1]); i += 2
        else:
            i += 1

    if not Path(csv_path).exists():
        sys.exit(f"File not found: {csv_path}")

    usernames = load_usernames(csv_path, column)
    if not usernames:
        sys.exit("No usernames found in CSV.")

    print(f"Found {len(usernames)} user(s) — running with {workers} parallel workers\n")

    completed = 0
    total = len(usernames)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run_report, user): user for user in usernames}
        for future in as_completed(futures):
            user, code, stdout, stderr = future.result()
            completed += 1
            status = "OK" if code == 0 else f"ERROR (exit {code})"
            print(f"[{completed}/{total}] {user}: {status}")
            if stdout:
                for line in stdout.strip().splitlines():
                    print(f"  {line}")
            if code != 0 and stderr:
                print(f"  STDERR: {stderr.strip()}")

    print("\nDone.")


if __name__ == "__main__":
    main()
