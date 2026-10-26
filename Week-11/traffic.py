"""A working day of claims traffic through the app, traced into logs/.

    python traffic.py

24 real requests from five adjusters (adj-01..adj-05, pseudonyms): 14 desk
questions drawn from Week 5's traffic list and 10 file notes drawn from the Week 6
cases that are NOT in the eval suite, in a seeded random order with a seeded
random adjuster on each. The plan is written to runs/traffic_plan.json before the
first request; a request already logged is never run again.
"""
import os
import sys
import json
import random
import asyncio
import importlib.util

import app
import suite_cases

SEED = 20261026
N_DESK, N_NOTES = 14, 10
USERS = ["adj-01", "adj-02", "adj-03", "adj-04", "adj-05"]
PLAN = os.path.join("runs", "traffic_plan.json")


def week5_questions():
    spec = importlib.util.spec_from_file_location("week5_questions", os.path.join("..", "Week-5", "questions.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.TRAFFIC


def week6_notes():
    with open(os.path.join("..", "Week-6", "cases.jsonl"), encoding="utf-8") as f:
        cases = [json.loads(l) for l in f if l.strip()]
    return [c for c in cases if c["id"] not in suite_cases.WEEK6_IDS]


def make_plan():
    rng = random.Random(SEED)
    items = [{"source": "week5", "input_type": "desk_question", "notes": q}
             for q in rng.sample(week5_questions(), N_DESK)]
    items += [{"source": "week6:" + c["id"], "input_type": "file_note", "notes": c["notes"]}
              for c in rng.sample(week6_notes(), N_NOTES)]
    rng.shuffle(items)
    for i, item in enumerate(items):
        item.update(n=i + 1, user=rng.choice(USERS))
    return items


async def main():
    os.makedirs("runs", exist_ok=True)
    if not os.path.exists(PLAN):
        with open(PLAN, "w", encoding="utf-8") as f:
            json.dump({"seed": SEED, "items": make_plan()}, f, indent=1, ensure_ascii=False)
    with open(PLAN, encoding="utf-8") as f:
        plan = json.load(f)
    done_path = os.path.join("runs", "traffic_done.json")
    done = json.load(open(done_path)) if os.path.exists(done_path) else {}
    for item in plan["items"]:
        if str(item["n"]) in done:
            continue
        try:
            rec = await app.handle(item["notes"], item["user"], item["input_type"], log=lambda l: None)
            done[str(item["n"])] = rec["trace_id"]
        except RuntimeError as exc:      # the trace is written either way; the day goes on
            done[str(item["n"])] = "error: %s" % exc
            rec = None
        with open(done_path, "w") as f:
            json.dump(done, f, indent=1)
        print("  %2d/%d %s %-13s %-14s %s" % (item["n"], len(plan["items"]), item["user"], item["input_type"],
                                             rec["position"] if rec else "ERROR",
                                             "%d tok $%.5f %.1fs" % (rec["tokens"], rec["cost_usd"], rec["latency_s"])
                                             if rec else done[str(item["n"])][:80]), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
