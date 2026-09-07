"""Run the week's desk traffic through the assistant and fill the trace file.

    python run_traffic.py            # the 120 desk questions -> traces/traces.jsonl
    python run_traffic.py demo       # the 10 review questions -> traces/demo.jsonl

Desk traffic and the demo set are written to SEPARATE files. If they shared one
file the random sample could pull a demo question, and the whole point of the
bonus is that the two populations are compared, not mixed.
"""
import os
import sys
import time

import trace as tracer
from questions import TRAFFIC, DEMO_SET

DEMO_FILE = os.path.join(tracer.TRACE_DIR, "demo.jsonl")
PAUSE = 0.6      # keep under the Groq free-tier rate limit
RETRIES = 3


def run(questions, path, source):
    import assistant

    if os.path.exists(path):
        print("%s already has %d traces - delete it to re-run"
              % (path, len(tracer.read_all(path))))
        return

    started = time.time()
    for i, q in enumerate(questions, 1):
        for attempt in range(1, RETRIES + 1):
            rec = assistant.answer(q, path=path, extra={"source": source})
            if not rec["error"]:
                break
            print("  retry %d/%d after %s" % (attempt, RETRIES, rec["error"][:60]))
            time.sleep(2 * attempt)

        flag = "ERR" if rec["error"] else ("REF" if rec["refused_by"] else "ok ")
        print("[%3d/%d] %s %s %s" % (i, len(questions), flag, rec["trace_id"],
                                     rec["question"][:58]))
        time.sleep(PAUSE)

    rows = tracer.read_all(path)
    print("\n%d traces in %s, %.0fs" % (len(rows), path, time.time() - started))
    print("errors: %d   refusals: %d"
          % (sum(1 for r in rows if r["error"]),
             sum(1 for r in rows if r["refused_by"])))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        run(DEMO_SET, DEMO_FILE, "demo")
    else:
        run(TRAFFIC, tracer.TRACE_FILE, "desk")
