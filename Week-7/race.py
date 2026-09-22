"""Race the agent against the fixed workflow over the same 10 claims.

    python race.py

Writes one JSON line per claim per system to runs/race_<system>.jsonl, the
per-claim grid to race_claims.csv, and the 8 headline numbers to race.csv.
Every claim is graded by contract.grade against expected.json, which was
committed before this script first ran.

Refuses to overwrite a finished race: delete the runs/race_*.jsonl files to re-run.
"""
import os
import csv
import sys
import json
import time
import datetime
import statistics

import llm
import agent
import workflow
import contract

SYSTEMS = {"workflow": workflow.run, "agent": agent.run}

with open("expected.json", encoding="utf-8") as f:
    EXPECTED = json.load(f)["claims"]
CLAIM_IDS = sorted(EXPECTED)


def race(system, run):
    path = "runs/race_%s.jsonl" % system
    if os.path.exists(path):
        sys.exit("%s exists - delete it to re-run the race" % path)
    rows = []
    for claim_id in CLAIM_IDS:
        lines = []
        result = run(claim_id, log=lines.append)
        passed, why = contract.grade(result["output"], EXPECTED[claim_id])
        row = {**result, "system": system, "class": EXPECTED[claim_id]["class"],
               "passed": passed, "fail_reasons": why, "log": lines, "model": llm.MODEL,
               "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        rows.append(row)
        print("  %-8s %s  %-4s %-24s %5d tok  %5.2fs%s"
              % (system, claim_id, "PASS" if passed else "FAIL", row["class"], row["tokens"],
                 row["latency_s"], ("  " + "; ".join(why)) if why else ""), flush=True)
        time.sleep(2)   # between claims, outside every measurement
    return rows


def summary(system, rows):
    n = len(rows)
    return {"system": system,
            "claims": n,
            "pass_rate": "%d/%d" % (sum(r["passed"] for r in rows), n),
            "p50_latency_s": round(statistics.median(r["latency_s"] for r in rows), 2),
            "total_tokens": sum(r["tokens"] for r in rows),
            "cost_per_claim_usd": round(sum(r["cost_usd"] for r in rows) / n, 6),
            "model": llm.MODEL}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs("runs", exist_ok=True)
    results = {name: race(name, run) for name, run in SYSTEMS.items()}

    with open("race.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary("x", results["agent"]).keys()))
        w.writeheader()
        for name, rows in results.items():
            w.writerow(summary(name, rows))

    with open("race_claims.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["claim_id", "class", "expected_position", "expected_payable"]
                   + ["%s_%s" % (s, k) for s in SYSTEMS
                      for k in ("pass", "position", "payable", "laps", "tokens", "latency_s", "stop_reason")])
        for i, claim_id in enumerate(CLAIM_IDS):
            exp = EXPECTED[claim_id]
            line = [claim_id, exp["class"], exp["coverage_position"], exp["payable_amount"]]
            for s in SYSTEMS:
                r = results[s][i]
                out = r["output"] or {}
                line += [r["passed"], out.get("coverage_position"), out.get("payable_amount"),
                         r["laps"], r["tokens"], round(r["latency_s"], 2), r["stop_reason"] or ""]
            w.writerow(line)

    print()
    for name, rows in results.items():
        print(summary(name, rows))
