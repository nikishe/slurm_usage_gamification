#!/usr/bin/env python3
"""
HPC Job Efficiency Report
Requires: sacct, seff
Usage: python3 job_report.py [username]
"""

import subprocess
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Config ────────────────────────────────────────────────────────────────────
DAYS_BACK   = 30
USER        = sys.argv[1] if len(sys.argv) > 1 else os.popen("whoami").read().strip()
START_DATE  = (datetime.now() - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")
GENERATED   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
OUTPUT_FILE = datetime.now().strftime(f"job_report_{USER}_%Y_%m_%d_%H%M%S.html")
# ─────────────────────────────────────────────────────────────────────────────


def run(cmd: str) -> str:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()


def get_jobs() -> list[dict]:
    raw = run(
        f"sacct -X -u {USER} -S {START_DATE} --end now "
        f"--state=CD,F,TO,CA "
        f"--format=JobID,JobName,State,Submit,Start,End,AllocCPUS,ReqMem,Partition,NodeList "
        f"--noheader --parsable2 --units=G"
    )
    jobs = []
    for line in raw.splitlines():
        parts = line.split("|")
        if len(parts) < 10 or not parts[0]:
            continue
        jobs.append({
            "job_id":    parts[0],
            "name":      parts[1],
            "state":     parts[2],
            "submit":    parts[3],
            "start":     parts[4],
            "end":       parts[5],
            "alloc_cpu": parts[6],
            "req_mem":   parts[7],
            "partition": parts[8],
            "nodes":     parts[9],
        })
    return jobs


def calc_wait(submit: str, start: str) -> float:
    fmt = "%Y-%m-%dT%H:%M:%S"
    try:
        return max((datetime.strptime(start, fmt) - datetime.strptime(submit, fmt)).total_seconds() / 60, 0)
    except Exception:
        return 0.0


def fmt_mins(mins: float) -> str:
    if mins < 60:
        return f"{mins:.0f}m"
    return f"{int(mins // 60)}h {int(mins % 60)}m"


def get_seff(job_id: str) -> dict:
    out = run(f"seff {job_id}")
    d = {"mem_eff": "N/A", "cpu_eff": "N/A", "wall": "N/A", "mem_used": "N/A", "mem_req": "N/A"}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Memory Efficiency:"):
            d["mem_eff"] = line.split(":", 1)[1].strip().split()[0]
        elif line.startswith("CPU Efficiency:"):
            d["cpu_eff"] = line.split(":", 1)[1].strip().split()[0]
        elif line.startswith("Job Wall-clock time:"):
            d["wall"] = line.split(":", 1)[1].strip()
        elif line.startswith("Memory Utilized:"):
            d["mem_used"] = line.split(":", 1)[1].strip()
        elif line.startswith(("Memory Requested:", "Memory Allocated:")):
            d["mem_req"] = line.split(":", 1)[1].strip()
    return d


def eff_class(val: str) -> str:
    try:
        pct = float(val.replace("%", ""))
        if pct >= 75: return "eff-good"
        if pct >= 40: return "eff-warn"
        return "eff-poor"
    except Exception:
        return ""


def state_colour(state: str) -> str:
    s = state.upper()
    if s == "COMPLETED":    return "#22c55e"
    if s == "FAILED":       return "#ef4444"
    if s == "TIMEOUT":      return "#f97316"
    if s.startswith("CANCELLED"): return "#a855f7"
    return "#6b7280"


def avg_eff(enriched: list[dict], key: str) -> str:
    vals = []
    for s in enriched:
        try:
            vals.append(float(s[key].replace("%", "")))
        except Exception:
            pass
    return f"{sum(vals)/len(vals):.1f}%" if vals else "N/A"


def build_rows(jobs: list[dict], enriched: list[dict]) -> str:
    rows = ""
    for j, s in zip(jobs, enriched):
        wait   = calc_wait(j["submit"], j["start"])
        wait_s = fmt_mins(wait) if wait > 0 else "N/A"
        mc     = eff_class(s["mem_eff"])
        cc     = eff_class(s["cpu_eff"])
        col    = state_colour(j["state"])
        rows += f"""
        <tr>
          <td><code>{j['job_id']}</code></td>
          <td>{j['name']}</td>
          <td><span class="badge" style="background:{col}">{j['state']}</span></td>
          <td>{j['partition']}</td>
          <td>{j['alloc_cpu']}</td>
          <td>{j['req_mem']}</td>
          <td>{wait_s}</td>
          <td>{s['wall']}</td>
          <td class="{mc}">{s['mem_used']} / {s['mem_req']}<br><small>{s['mem_eff']}</small></td>
          <td class="{cc}">{s['cpu_eff']}</td>
        </tr>"""
    return rows


def build_html(jobs: list[dict], enriched: list[dict]) -> str:
    total     = len(jobs)
    completed = sum(1 for j in jobs if j["state"] == "COMPLETED")
    failed    = sum(1 for j in jobs if j["state"] == "FAILED")
    timeout   = sum(1 for j in jobs if j["state"] == "TIMEOUT")
    avg_mem   = avg_eff(enriched, "mem_eff")
    avg_cpu   = avg_eff(enriched, "cpu_eff")
    rows      = build_rows(jobs, enriched)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Job Report – {USER}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #e2e8f0; padding: 2rem; }}
    h1   {{ font-size: 1.6rem; margin-bottom: 0.25rem; color: #f8fafc; }}
    .sub {{ color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }}
    .cards {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 1rem 1.5rem; min-width: 130px; }}
    .card .val {{ font-size: 1.8rem; font-weight: 700; color: #38bdf8; }}
    .card .lbl {{ font-size: 0.78rem; color: #94a3b8; margin-top: 2px; }}
    .card.warn .val {{ color: #f97316; }}
    .card.bad  .val {{ color: #ef4444; }}
    .card.good .val {{ color: #22c55e; }}
    .search-bar {{ margin-bottom: 1rem; }}
    .search-bar input {{
      width: 100%; padding: 0.5rem 1rem; border-radius: 8px;
      border: 1px solid #334155; background: #1e293b; color: #e2e8f0;
      font-size: 0.9rem; outline: none;
    }}
    .search-bar input:focus {{ border-color: #38bdf8; }}
    .table-wrap {{ overflow-x: auto; border-radius: 10px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    thead tr {{ background: #1e293b; }}
    thead th {{ padding: 0.75rem 1rem; text-align: left; color: #94a3b8;
                font-weight: 600; white-space: nowrap; cursor: pointer; user-select: none; }}
    thead th:hover {{ color: #38bdf8; }}
    tbody tr {{ border-bottom: 1px solid #1e293b; transition: background 0.15s; }}
    tbody tr:hover {{ background: #1e293b; }}
    tbody td {{ padding: 0.65rem 1rem; vertical-align: middle; }}
    code {{ background: #0f172a; padding: 2px 6px; border-radius: 4px; font-size: 0.82rem; color: #7dd3fc; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 99px;
              font-size: 0.75rem; font-weight: 600; color: #fff; }}
    .eff-good {{ color: #22c55e; font-weight: 600; }}
    .eff-warn {{ color: #f97316; font-weight: 600; }}
    .eff-poor {{ color: #ef4444; font-weight: 600; }}
    small {{ color: #94a3b8; }}
    .legend {{ margin-top: 1.5rem; font-size: 0.78rem; color: #64748b; }}
    .legend span {{ margin-right: 1rem; }}
  </style>
</head>
<body>
  <h1>🖥️ HPC Job Report — {USER}</h1>
  <p class="sub">Last {DAYS_BACK} days &nbsp;·&nbsp; Generated {GENERATED}</p>

  <div class="cards">
    <div class="card"><div class="val">{total}</div><div class="lbl">Total Jobs</div></div>
    <div class="card good"><div class="val">{completed}</div><div class="lbl">Completed</div></div>
    <div class="card bad"><div class="val">{failed}</div><div class="lbl">Failed</div></div>
    <div class="card warn"><div class="val">{timeout}</div><div class="lbl">Timed Out</div></div>
    <div class="card"><div class="val">{avg_mem}</div><div class="lbl">Avg Mem Efficiency</div></div>
    <div class="card"><div class="val">{avg_cpu}</div><div class="lbl">Avg CPU Efficiency</div></div>
  </div>

  <div class="search-bar">
    <input type="text" id="search" placeholder="🔍  Filter by Job ID, name, state, partition…" oninput="filterTable()">
  </div>

  <div class="table-wrap">
    <table id="jobTable">
      <thead>
        <tr>
          <th onclick="sortTable(0)">Job ID ↕</th>
          <th onclick="sortTable(1)">Name ↕</th>
          <th onclick="sortTable(2)">State ↕</th>
          <th onclick="sortTable(3)">Partition ↕</th>
          <th onclick="sortTable(4)">CPUs ↕</th>
          <th onclick="sortTable(5)">Req Mem ↕</th>
          <th onclick="sortTable(6)">Wait Time ↕</th>
          <th onclick="sortTable(7)">Wall Clock ↕</th>
          <th onclick="sortTable(8)">Memory Used / Req</th>
          <th onclick="sortTable(9)">CPU Efficiency ↕</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <div class="legend">
    <span class="eff-good">■ ≥75% Good</span>
    <span class="eff-warn">■ 40–74% OK</span>
    <span class="eff-poor">■ &lt;40% Poor</span>
  </div>

  <script>
    function filterTable() {{
      const q = document.getElementById("search").value.toLowerCase();
      document.querySelectorAll("#jobTable tbody tr").forEach(row => {{
        row.style.display = row.textContent.toLowerCase().includes(q) ? "" : "none";
      }});
    }}
    let sortDir = {{}};
    function sortTable(col) {{
      const tbody = document.querySelector("#jobTable tbody");
      const rows  = Array.from(tbody.querySelectorAll("tr"));
      sortDir[col] = !sortDir[col];
      rows.sort((a, b) => {{
        const av = a.cells[col].textContent.trim();
        const bv = b.cells[col].textContent.trim();
        const an = parseFloat(av), bn = parseFloat(bv);
        const cmp = isNaN(an) || isNaN(bn) ? av.localeCompare(bv) : an - bn;
        return sortDir[col] ? cmp : -cmp;
      }});
      rows.forEach(r => tbody.appendChild(r));
    }}
  </script>
</body>
</html>"""


def main():
    print(f"Fetching jobs for user '{USER}' since {START_DATE}...")
    jobs = get_jobs()
    if not jobs:
        print(f"No jobs found in the last {DAYS_BACK} days.")
        sys.exit(0)

    print(f"Found {len(jobs)} jobs. Running seff in parallel...")
    enriched_map = {}
    completed_count = 0
    total = len(jobs)
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(get_seff, j["job_id"]): j["job_id"] for j in jobs}
        for future in as_completed(futures):
            job_id = futures[future]
            enriched_map[job_id] = future.result()
            completed_count += 1
            print(f"  [{completed_count}/{total}] seff {job_id}", end="\r")
    print()
    enriched = [enriched_map[j["job_id"]] for j in jobs]

    html = build_html(jobs, enriched)
    Path(OUTPUT_FILE).write_text(html)
    print(f"\n✅ Report saved to: {os.path.abspath(OUTPUT_FILE)}")


if __name__ == "__main__":
    main()
