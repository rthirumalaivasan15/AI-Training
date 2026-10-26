"""For the SQUADMATE, not the finder: plant one bad coverage answer in the logs.

    python plant.py --list
    python plant.py --trap T1 --user adj-02 --by "Squadmate Name"
    python plant.py --trap T1 --user adj-02 --at 15:42 --by "Squadmate Name"
    python plant.py --notes "CLM-... your own claim ..." --exclusion E-52 --user adj-02 --by "..."

What it does:
1. Runs the REAL app on the claim (nothing is typed into the log by hand), so the
   bad answer is one the app genuinely gives - which is what lets the eval case go
   RED before the fix.
2. If the app does NOT say COVERED it plants nothing: the app got that one right,
   pick another trap.
3. If it says COVERED, the trace is written into the latest logged day, stamped at
   --at (or a random moment inside that day's traffic window) under --user, and the
   day file is re-sorted by time so its position gives nothing away.
4. The answer key goes to drill/plant_key.json. The FINDER MUST NOT OPEN IT until
   the drill is over - it is the sealed envelope.

Then tell the finder only: "an adjuster says it told a claimant something was
covered when the policy excludes it, sometime <that day>" - and start the clock.
"""
import os
import sys
import json
import random
import asyncio
import argparse
import datetime

import app
import tracer

POOL = os.path.join("drill", "trap_pool.jsonl")
KEY = os.path.join("drill", "plant_key.json")


def pool():
    with open(POOL, encoding="utf-8") as f:
        return {t["id"]: t for t in (json.loads(l) for l in f if l.strip())}


def stamp(day_rows, at=None):
    first = datetime.datetime.fromisoformat(day_rows[0]["ts"])
    last = datetime.datetime.fromisoformat(day_rows[-1]["ts"])
    if at:
        hh, mm = (int(x) for x in at.split(":"))
        when = first.replace(hour=hh, minute=mm, second=random.randrange(60),
                             microsecond=random.randrange(1000) * 1000)
    else:
        when = first + (last - first) * random.uniform(0.15, 0.85)
    return when.isoformat(timespec="milliseconds")


def resort(path):
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
    rows.sort(key=lambda r: r["ts"])
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--list", action="store_true")
    p.add_argument("--trap")
    p.add_argument("--notes")
    p.add_argument("--exclusion", help="with --notes: the exclusion code that should have applied")
    p.add_argument("--user", default="adj-02")
    p.add_argument("--at", help="HH:MM local time on the logged day; default random inside the traffic window")
    p.add_argument("--by", required=False, help="the squadmate's name, recorded in the key")
    p.add_argument("--tries", type=int, default=5, help="real runs to attempt before giving up (default 5)")
    a = p.parse_args()

    if a.list:
        for t in pool().values():
            cite = " or ".join(t["expected"]["must_cite_any"])
            print("  %-4s %-82s should be: not COVERED%s" % (
                t["id"], t["hint"], ", cite " + cite if cite else ""))
        return
    if os.path.exists(KEY):
        sys.exit("%s exists - one plant per drill. Delete it to plant again." % KEY)
    if a.trap:
        trap = pool()[a.trap]
        notes, expected = trap["notes"], trap["expected"]
    elif a.notes:
        trap, notes = {"id": "custom"}, a.notes
        expected = {"position_not": ["COVERED"], "must_cite_any": [a.exclusion] if a.exclusion else [],
                    "why": "squadmate's own claim; should not have been covered%s"
                           % (" - excluded under %s" % a.exclusion if a.exclusion else "")}
    else:
        sys.exit("give --trap ID, or --notes (and optionally --exclusion)")

    rows = tracer.read()
    if not rows:
        sys.exit("no logged traffic to plant into - run traffic.py first")
    day = rows[-1]["ts"][:10]
    day_rows = [r for r in rows if r["ts"].startswith(day)]

    # The app is not deterministic on hard claims even at temperature 0 - the same
    # notes have come back COVERED, DENIED and UNDETERMINED on three runs - so a trap
    # may need more than one run before the app actually gets it wrong.
    attempts = []
    for attempt in range(1, a.tries + 1):
        print("running the real app on %s (attempt %d/%d) ..." % (trap["id"], attempt, a.tries), flush=True)
        record = await app.handle(notes, a.user, "file_note", write=False, log=lambda l: None)
        attempts.append(record["position"])
        print("app answered: %s  (grounds: %s)" % (record["position"], record["grounds"]))
        if (record["position"] or "").upper() == "COVERED":
            break
    else:
        sys.exit("The app did not say COVERED in %d run(s) (%s) - nothing planted. Pick another trap "
                 "or raise --tries." % (a.tries, ", ".join(map(str, attempts))))

    real_ts = record["ts"]
    record["ts"] = stamp(day_rows, a.at)
    tracer.write(record)                     # redacted on write, like every other trace
    resort(tracer.log_path(record["ts"]))
    with open(KEY, "w", encoding="utf-8") as f:
        json.dump({"trace_id": record["trace_id"], "stamped_ts": record["ts"], "actually_ran_at": real_ts,
                   "user": a.user, "trap": trap["id"], "expected": expected, "app_position": record["position"],
                   "app_grounds": record["grounds"], "planted_by": a.by,
                   "runs_until_covered": attempts,
                   "note": "planted for the Week 11 drill: a real app run, re-stamped into the traffic window"},
                  f, indent=2, ensure_ascii=False)
    print("\nPLANTED. Key sealed in %s - the finder must not open it." % KEY)
    print('Now tell the finder only: "an adjuster says it told a claimant something was covered '
          'when the policy excludes it, sometime on %s" - and start the clock.' % day)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
