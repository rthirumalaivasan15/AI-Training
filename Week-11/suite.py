"""Run the eval suite against the app as configured, judge every case, print the
pass count.

    python suite.py red        # before the fix  -> runs/suite_red.jsonl, runs/suite_red.txt
    python suite.py green      # after the fix   -> runs/suite_green.jsonl, runs/suite_green.txt

The suite is suite_cases.load(): the 10 Week-6 cases the app was last measured on,
plus every production failure turned into a case file in evals/. Every case is
run through app.handle - the same code path as production - with write=False, so
eval runs never enter the production logs.

PASS = the Week 6 rule (all four assertions + judge PASS) and, for a case file
with an "expect" block, the position is not one it forbids and GROUNDS cites one
of the codes it requires. The whole suite runs every time, so a fix that quietly
breaks another case shows up in the same count.

A case already in the run file is not run again; delete the file to re-run a tag.
"""
import os
import re
import sys
import json
import asyncio
import datetime

import app
import judge
import prompts
import tracer
import assertions
import suite_cases

HYPHENS = re.compile("[‐‑‒–—−]")


def expect_check(case, summary):
    exp = case.get("expect")
    if not exp:
        return True, "no expect block"
    f = assertions.fields(summary or "")
    position = (f.get("COVERAGE POSITION") or "").upper()
    grounds = HYPHENS.sub("-", f.get("GROUNDS") or "")
    if position in exp.get("position_not", []):
        return False, "position %s, which this case forbids" % position
    if exp.get("position_in") and position not in exp["position_in"]:
        return False, "position %s, not one of %s" % (position, exp["position_in"])
    want = exp.get("must_cite_any", [])
    if want and not any(code in grounds for code in want):
        return False, "GROUNDS %r cites none of %s" % (grounds, want)
    return True, "position %s, grounds %s" % (position, grounds)


async def run(tag):
    path_jsonl = os.path.join("runs", "suite_%s.jsonl" % tag)
    os.makedirs("runs", exist_ok=True)
    done = {}
    if os.path.exists(path_jsonl):
        with open(path_jsonl, encoding="utf-8") as f:
            done = {r["id"]: r for r in (json.loads(l) for l in f if l.strip())}
    version = prompts.active()
    for case in suite_cases.load():
        if case["id"] in done:
            continue
        rec = await app.handle(case["notes"], "eval", case.get("input_type", "file_note"),
                               write=False, log=lambda l: None)
        v = judge.verdict(case, rec["output"])
        ok_expect, why = expect_check(case, rec["output"])
        row = {"id": case["id"], "source": case["source"], "tag": tag,
               "prompt_version": rec["prompt_version"], "prompt_sha": rec["prompt_sha"],
               "position": rec["position"], "grounds": rec["grounds"], "context_ids": rec["context_ids"],
               **v, "expect_ok": ok_expect, "expect_detail": why,
               "pass": v["verdict"] == "PASS" and v["asserts_ok"] and ok_expect,
               "tokens": rec["tokens"], "cost_usd": rec["cost_usd"], "latency_s": rec["latency_s"],
               "summary": rec["output"], "week6_cases_sha": suite_cases.week6_sha(),
               "ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
        tracer.scrub({"trace_id": case["id"], "input": "", "output": row["summary"]})  # refuse PII in eval output
        done[case["id"]] = row
        with open(path_jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("  %-26s %-14s judge %-4s asserts %-4s expect %-4s -> %s" % (
            case["id"], row["position"], v["verdict"], "ok" if v["asserts_ok"] else "FAIL",
            "ok" if ok_expect else "FAIL", "PASS" if row["pass"] else "FAIL"), flush=True)

    rows = [done[c["id"]] for c in suite_cases.load()]
    passed = sum(r["pass"] for r in rows)
    out = ["SUITE %s - prompt %s (sha %s) - Week-6 cases sha %s - %s" % (
               tag.upper(), version, prompts.sha(version), suite_cases.week6_sha(),
               datetime.datetime.now().astimezone().isoformat(timespec="seconds")), ""]
    for r in rows:
        why = [] if r["pass"] else (["judge " + str(r["verdict"])] if r["verdict"] != "PASS" else []) + \
            [c["name"] for c in r["assertions"] if not c["passed"]] + ([] if r["expect_ok"] else ["expect: " + r["expect_detail"]])
        out.append("  %-26s %-16s %-24s %s" % (r["id"], r["position"], (r["grounds"] or "-")[:24],
                                              "PASS" if r["pass"] else "FAIL  " + "; ".join(why)))
    out += ["", "SUITE %s: %d/%d pass" % (tag.upper(), passed, len(rows))]
    with open(os.path.join("runs", "suite_%s.txt" % tag), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(run(sys.argv[1]))
