"""Run the claims agent over the 10 cases and save the full trajectory of each.

    python run_trace.py before          -> runs/traj_before.jsonl
    python run_trace.py after           -> runs/traj_after.jsonl

One JSON line per claim: every tool call with its arguments and what it returned,
the final answer, the outcome grade, and the tokens, cost and latency of the run.
Nothing is scored here - trajectory_eval.py does the scoring, so a run can be
re-scored after the eval changes without paying for the model again.

Never overwrites a finished run: delete the file to re-run that tag.
"""
import os
import sys
import json
import time
import datetime

import llm
import agent
import contract

with open("expected.json", encoding="utf-8") as f:
    OUTCOMES = json.load(f)["claims"]
CLAIM_IDS = sorted(OUTCOMES)


def run(tag):
    path = "runs/traj_%s.jsonl" % tag
    if os.path.exists(path):
        sys.exit("%s exists - delete it to re-run this tag" % path)
    os.makedirs("runs", exist_ok=True)

    for claim_id in CLAIM_IDS:
        lines = []
        result = agent.run(claim_id, log=lines.append)
        passed, why = contract.grade(result["output"], OUTCOMES[claim_id])
        row = {**result, "tag": tag, "class": OUTCOMES[claim_id]["class"],
               "outcome_passed": passed, "outcome_fail_reasons": why,
               "log": lines, "model": llm.MODEL,
               "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("  %s  outcome %-4s  %d steps  %5d tok  %5.2fs  %s"
              % (claim_id, "PASS" if passed else "FAIL", len(result["tool_calls"]),
                 result["tokens"], result["latency_s"],
                 " > ".join(c["tool"] for c in result["tool_calls"])), flush=True)
        time.sleep(2)   # between claims, outside every measurement
    print("wrote", path)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    run(sys.argv[1] if len(sys.argv) > 1 else "before")
