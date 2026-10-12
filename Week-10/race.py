"""Race both arms over the same 10 Week-6 cases.

    python race.py

For each case in cases.CASE_IDS: the single agent, then the orchestrator, so both
arms meet the same rate-limit weather. One JSON line per case per arm in
runs/race_single.jsonl and runs/race_multi.jsonl, appended as each case finishes.
A case already in a file is never run again - delete the file to re-run an arm.
Nothing is scored here: judge.py judges, report.py counts.
"""
import os
import sys
import json
import time
import asyncio
import datetime

import llm
import cases
import single_agent
import orchestrator

ARMS = {"single": single_agent.run_case, "multi": orchestrator.run}


def path(arm):
    return os.path.join("runs", "race_%s.jsonl" % arm)


def done(arm):
    if not os.path.exists(path(arm)):
        return set()
    with open(path(arm), encoding="utf-8") as f:
        return {json.loads(l)["id"] for l in f if l.strip()}


async def main():
    os.makedirs("runs", exist_ok=True)
    finished = {arm: done(arm) for arm in ARMS}
    for case in cases.load():
        for arm, run in ARMS.items():
            if case["id"] in finished[arm]:
                continue
            lines = []
            result = await run(case, log=lines.append)
            row = {**result, "mode": case["mode"], "model": llm.MODEL, "cases_sha": cases.source_sha(),
                   "log": lines, "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
            with open(path(arm), "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print("  %-6s %s  %-16s %2d calls %6d tok  $%.5f  %5.2fs" % (
                arm, case["id"], orchestrator.summary_format.position(result["summary"]),
                result["calls"], result["tokens"], result["cost_usd"], result["latency_s"]), flush=True)
            time.sleep(2)   # between runs, outside every measurement


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
