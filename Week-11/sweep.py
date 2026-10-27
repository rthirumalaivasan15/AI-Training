"""Check every COVERED answer of a day with the Week 6 judge and list the ones it fails.

    python sweep.py                  # the latest logged day
    python sweep.py --day 2026-10-26

The complaint describes the output ("it said covered"), so the sweep starts from
the output slice - position COVERED - and asks the judge whether each of those
positions is what the endorsement wording actually gives. A verdict is stored in
logs/verdicts.jsonl the first time a trace is judged and never asked again, so the
sweep only spends model calls on answers it has not seen: an online check that
turns "read every covered answer" into one command.
"""
import os
import sys
import json
import argparse
import datetime

import judge
import tracer

VERDICTS = os.path.join(tracer.LOG_DIR, "verdicts.jsonl")


def load_verdicts():
    if not os.path.exists(VERDICTS):
        return {}
    with open(VERDICTS, encoding="utf-8") as f:
        return {v["trace_id"]: v for v in (json.loads(l) for l in f if l.strip())}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--day")
    a = p.parse_args()
    rows = tracer.read()
    day = a.day or rows[-1]["ts"][:10]
    covered = [r for r in rows if r["ts"].startswith(day) and (r.get("position") or "").upper() == "COVERED"]
    verdicts = load_verdicts()
    tmpl = judge.template()

    for r in covered:
        if r["trace_id"] in verdicts:
            continue
        reply, tokens = judge.ask(judge.render(tmpl, {"notes": r["input"]}, r["output"]))
        v, reason = judge.parse(reply)
        rec = {"trace_id": r["trace_id"], "verdict": v, "reason": reason, "judge_model": judge.JUDGE_MODEL,
               "judge_prompt_sha": judge.WEEK6_V2_SHA, "judge_tokens": tokens,
               "judged_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
        verdicts[r["trace_id"]] = rec
        with open(VERDICTS, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print("%s: %d answers said COVERED" % (day, len(covered)))
    for r in covered:
        v = verdicts[r["trace_id"]]
        print("  %s  %s  %s  %-6s judge %-4s  %s" % (
            "!!" if v["verdict"] != "PASS" else "  ", r["ts"][11:19], r["trace_id"], r["user"], v["verdict"],
            (r["input"] or "")[:80]))
    bad = [r for r in covered if verdicts[r["trace_id"]]["verdict"] != "PASS"]
    print("\n%d the judge says are wrong:" % len(bad))
    for r in bad:
        print("  %s  - %s" % (r["trace_id"], verdicts[r["trace_id"]]["reason"][:160]))
    print("\nlook closer: python find.py --show <trace_id>")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
