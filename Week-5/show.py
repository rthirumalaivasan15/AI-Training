"""Print traces in full, for reading by eye.

    python show.py trc_ab12cd34ef56          one trace
    python show.py --sample                  the seeded 20, in order
    python show.py --sample --file traces/demo.jsonl --n 10

This is a reading tool, not an analysis tool. It deliberately computes nothing
and judges nothing - it lays the trace out and gets out of the way, because any
label it printed would be a label I had not arrived at myself.
"""
import sys
import argparse

import trace as tracer
import sample

RULE = "=" * 78


def render(record, n=None):
    head = "%s%s" % ("[%d] " % n if n else "", record["trace_id"])
    print(RULE)
    print("%s   %s   %s" % (head, record["ts"], record.get("source", "?")))
    print(RULE)
    print("QUESTION\n  %s\n" % record["question"])

    print("RETRIEVED  (%s, k=%d)  best_dense=%.4f"
          % (record["retriever"], record["k"], record["best_dense_score"]))
    for row in record["retrieved"]:
        print("  %d. %-20s %-9s ed.%-7s score %.4f"
              % (row["rank"], row["chunk_id"], row["form_number"],
                 row["edition"], row["score"]))

    print("\nMODEL  %s  %s  prompt=%s"
          % (record["model"], record["params"], record["prompt_version"]))
    print("refused_by=%s  error=%s  latency=%dms  redactions=%s"
          % (record["refused_by"], record["error"], record["latency_ms"],
             record.get("redactions")))

    print("\nANSWER")
    for line in (record["raw_output"] or "(empty)").splitlines():
        print("  " + line)

    print("\nCITATIONS  %s" % (", ".join(record["citations"]) or "none"))
    if record["dangling_citations"]:
        print("DANGLING   %s" % ", ".join(record["dangling_citations"]))

    if record.get("reasoning"):
        print("\nMODEL SCRATCHPAD")
        for line in record["reasoning"].splitlines():
            print("  | " + line)
    print()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("trace_id", nargs="?")
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--seed", type=int, default=sample.SEED)
    ap.add_argument("--n", type=int, default=sample.N)
    ap.add_argument("--file", default=tracer.TRACE_FILE)
    args = ap.parse_args()

    if args.sample:
        rows, total = sample.draw(args.file, args.seed, args.n)
        print("# %d of %d traces, seed %d\n" % (len(rows), total, args.seed))
        for i, r in enumerate(rows, 1):
            render(r, i)
    elif args.trace_id:
        render(tracer.by_id(args.trace_id, args.file))
    else:
        raise SystemExit("give a trace_id or --sample")
