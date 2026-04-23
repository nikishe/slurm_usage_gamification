# slurm_usage_gamification

Generate HTML efficiency reports for SLURM HPC jobs, per user.

## Requirements

- Python 3.10+
- SLURM tools: `sacct`, `seff`

## Scripts

### `hpc_job_report_parrallel.py`

Generates an HTML report for a single user covering the last 30 days.

```bash
python3 hpc_job_report_parrallel.py <username>
```

Output: `job_report_<username>_YYYY_MM_DD_HHMMSS.html`

The report includes:
- Job counts (completed, failed, timed out)
- Average CPU and memory efficiency
- Per-job breakdown with wait time, wall-clock time, and resource usage

### `run_reports_for_users.py`

Batch runner — reads usernames from a CSV and generates a report for each user in parallel.

```bash
python3 run_reports_for_users.py <users.csv> [--column COLUMN_NAME] [--workers N]
```

| Argument | Default | Description |
|---|---|---|
| `users.csv` | required | Path to CSV file containing usernames |
| `--column` | first column | Column name to read usernames from |
| `--workers` | CPU core count | Number of parallel workers |

**Example CSV (`users.csv`):**
```
username
jsmith
ajonas
mlee
```

**Examples:**
```bash
# Auto-detect workers from CPU count
python3 run_reports_for_users.py users.csv

# Use a specific column and worker count
python3 run_reports_for_users.py users.csv --column login --workers 8
```
