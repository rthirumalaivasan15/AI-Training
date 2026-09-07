"""Draw a seeded random sample of traces, and print it so it can be pasted.

    python sample.py                 # 20 traces, seed 20250907
    python sample.py --seed 12345 --n 20
    python sample.py --replay-pick   # the one trace_id to replay, same seed

The seed is the whole point. Anyone can re-run this against the same trace file
and get the same 20 ids, which is what makes "I did not cherry-pick these"
checkable rather than something I merely assert.
"""
import sys
import random
import argparse

import trace as tracer

SEED = 20250907          # today's date, chosen before the file was read
N = 20


def draw(path=tracer.TRACE_FILE, seed=SEED, n=N):
    rows = tracer.read_all(path)
    ids = sorted(r["trace_id"] for r in rows)      # sort first: dict order must not matter
    rng = random.Random(seed)
    picked = rng.sample(ids, n)
    index = {r["trace_id"]: r for r in rows}
    return [index[i] for i in picked], len(rows)


def replay_pick(path=tracer.TRACE_FILE, seed=SEED):
    """A second, independent draw for the replay evidence, from the same seed."""
    rows = tracer.read_all(path)
    ids = sorted(r["trace_id"] for r in rows)
    return random.Random(seed + 1).choice(ids)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--n", type=int, default=N)
    ap.add_argument("--file", default=tracer.TRACE_FILE)
    ap.add_argument("--replay-pick", action="store_true")
    args = ap.parse_args()

    if args.replay_pick:
        print("seed %d + 1 -> replay trace_id: %s"
              % (args.seed, replay_pick(args.file, args.seed)))
        raise SystemExit

    picked, total = draw(args.file, args.seed, args.n)
    print("population: %d traces in %s" % (total, args.file))
    print("seed: %d    sample: %d\n" % (args.seed, args.n))
    for i, r in enumerate(picked, 1):
        print("%2d. %s  %s" % (i, r["trace_id"], r["question"][:88]))
