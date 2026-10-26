"""Search and slice the production logs. No model calls - it only reads logs/.

    python find.py                                   # the day at a glance: counts by every slice
    python find.py --by user                         # one slice: user | input_type | prompt_version | position | hour
    python find.py --position COVERED                # filter on the OUTPUT
    python find.py --user adj-03 --input-type file_note --version claims-agent-v1
    python find.py --between 14:00 15:30             # a time window (local time)
    python find.py --text vacant                     # free text over redacted input and output
    python find.py --cost-outliers                   # cheapest and dearest requests (IQR rule)
    python find.py --show trc_0123abcd4567           # one full trace, every span
    python find.py --day 2026-10-25 ...              # any day; default is the latest day logged

Filters combine. Every listing prints one line per trace: time, id, user, input
type, prompt version, position, grounds, tokens, cost, latency and the start of the
(redacted) input.
"""
import sys
import json
import argparse
from collections import Counter

import tracer

SLICES = ("user", "input_type", "prompt_version", "position", "hour")


def value(r, field):
    return r["ts"][11:13] + ":00" if field == "hour" else (r.get(field) or "-")


def line(r):
    return "%s  %s  %-6s %-13s %-15s %-16s %-24s %6d tok $%.5f %5.1fs  %s" % (
        r["ts"][11:19], r["trace_id"], r["user"], r["input_type"], r["prompt_version"],
        r.get("position") or "-", (r.get("grounds") or "-")[:24], r["tokens"], r["cost_usd"],
        r["latency_s"], (r["input"] or "").replace("\n", " ")[:70])


def quartiles(values):
    v = sorted(values)
    q = lambda p: v[min(len(v) - 1, int(p * (len(v) - 1) + 0.5))]
    return q(0.25), q(0.5), q(0.75)


def cost_outliers(rows):
    q1, med, q3 = quartiles([r["cost_usd"] for r in rows])
    lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    out = [r for r in rows if r["cost_usd"] < lo or r["cost_usd"] > hi]
    print("cost per request: q1 $%.5f  median $%.5f  q3 $%.5f  -> outside [$%.5f, $%.5f]: %d"
          % (q1, med, q3, max(lo, 0), hi, len(out)))
    if not out:
        ranked = sorted(rows, key=lambda r: r["cost_usd"])
        print("no IQR outliers - the 3 cheapest and 3 dearest instead:")
        out = ranked[:3] + ranked[-3:]
    return out


def overview(rows, day):
    print("%s: %d requests, %d users" % (day, len(rows), len({r["user"] for r in rows})))
    for field in SLICES:
        counts = Counter(value(r, field) for r in rows)
        print("  %-15s %s" % (field, "  ".join("%s=%d" % kv for kv in sorted(counts.items()))))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--day")
    p.add_argument("--user")
    p.add_argument("--input-type")
    p.add_argument("--version")
    p.add_argument("--position")
    p.add_argument("--between", nargs=2, metavar=("HH:MM", "HH:MM"))
    p.add_argument("--text")
    p.add_argument("--by", choices=SLICES)
    p.add_argument("--cost-outliers", action="store_true")
    p.add_argument("--show")
    a = p.parse_args()

    if a.show:
        found = [r for r in tracer.read() if r["trace_id"] == a.show]
        print(json.dumps(found[0], indent=2, ensure_ascii=False) if found else "no trace %s" % a.show)
        return

    every = tracer.read()
    if not every:
        sys.exit("no logs yet")
    day = a.day or every[-1]["ts"][:10]
    rows = [r for r in every if r["ts"].startswith(day)]

    if a.by:
        for v, n in sorted(Counter(value(r, a.by) for r in rows).items()):
            print("  %-20s %d" % (v, n))
        return
    filters = [a.user, a.input_type, a.version, a.position, a.between, a.text, a.cost_outliers]
    if not any(filters):
        overview(rows, day)
        return

    if a.user:
        rows = [r for r in rows if r["user"] == a.user]
    if a.input_type:
        rows = [r for r in rows if r["input_type"] == a.input_type]
    if a.version:
        rows = [r for r in rows if r["prompt_version"] == a.version]
    if a.position:
        rows = [r for r in rows if (r.get("position") or "").upper() == a.position.upper()]
    if a.between:
        rows = [r for r in rows if a.between[0] <= r["ts"][11:16] <= a.between[1]]
    if a.text:
        t = a.text.lower()
        rows = [r for r in rows if t in (r["input"] or "").lower() or t in (r["output"] or "").lower()]
    if a.cost_outliers:
        rows = cost_outliers(rows)
    for r in rows:
        print(line(r))
    print("%d trace(s)" % len(rows))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
