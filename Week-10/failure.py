"""Inject one worker failure: the coverage/exclusions worker returns a 500 on one case.

    python failure.py            -> runs/failure_C02.json

The case was chosen before the race ran: C02, where the insured asks whether E-17
covers surface water that ran in under a patio door. That claim is decided by the
exclusions check, so a squad that answers without one shows it in the position.
The 500 comes back on every attempt, so the orchestrator's retry cannot clear it;
what it does next is its own generic policy (orchestrator.delegate) - nothing here
tells it how to handle the failure.
"""
import os
import sys
import json
import asyncio
import datetime

import llm
import cases
import orchestrator

CASE_ID = "C02"
WORKER = "coverage_worker"


async def main():
    out_path = os.path.join("runs", "failure_%s.json" % CASE_ID)
    if os.path.exists(out_path):
        sys.exit("%s exists - delete it to re-run" % out_path)
    case = next(c for c in cases.load() if c["id"] == CASE_ID)
    lines = []
    result = await orchestrator.run(case, fail=WORKER, log=lines.append)
    row = {**result, "mode": case["mode"], "model": llm.MODEL, "cases_sha": cases.source_sha(), "log": lines,
           "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(row, f, indent=2, ensure_ascii=False)
    with open(os.path.join("runs", "failure_%s.jsonl" % CASE_ID), "w", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")     # the shape judge.py reads
    print("\n".join(lines))
    print(result["summary"])
    print("wrote", out_path)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
