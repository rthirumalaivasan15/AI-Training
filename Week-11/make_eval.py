"""Turn a production trace into a permanent eval case in evals/.

    python make_eval.py trc_0123abcd4567 --must-cite E-52 --why "vacant > 60 days, E-52 suspends HO-0820"
    python make_eval.py trc_0123abcd4567 --position-in NOT_IN_DOCUMENTS UNDETERMINED --why "..."

The case is the trace's own (redacted) input, so the test exercises exactly what
failed. The fields the Week 6 assertions check - claim number, date of loss,
excess - are read from the notes; pass --dol / --excess when the notes are not in
the usual "DOL YYYY-MM-DD ... Excess N" shape. The "expect" block is the failure,
stated as a rule: the position the app must not give, and a code it must cite.
"""
import os
import re
import sys
import json
import argparse

import tracer

DOL = re.compile(r"\bDOL\s+(\d{4}-\d{2}-\d{2})")
EXCESS = re.compile(r"\bExcess\s+([\d,]+)", re.I)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("trace_id")
    p.add_argument("--must-cite", nargs="*", default=[])
    p.add_argument("--position-in", nargs="+", help="the positions that are right, when only some are")
    p.add_argument("--position-not", nargs="+", default=["COVERED"])
    p.add_argument("--why", required=True)
    p.add_argument("--dol")
    p.add_argument("--excess", type=int)
    p.add_argument("--how-found", required=True, help="how this trace was found: the complaint and the slice")
    a = p.parse_args()

    found = [r for r in tracer.read() if r["trace_id"] == a.trace_id]
    if not found:
        sys.exit("no trace %s" % a.trace_id)
    t = found[0]
    notes = t["input"]
    dol = a.dol or (DOL.search(notes) or [None, None])[1]
    exc = EXCESS.search(notes)
    excess = a.excess if a.excess is not None else (int(exc.group(1).replace(",", "")) if exc else None)
    case = {"id": "P-%s" % a.trace_id, "mode": None, "claim_number": t.get("claim_number"),
            "date_of_loss": dol, "excess": excess, "input_type": t["input_type"], "notes": notes,
            "expect": {"position_not": a.position_not, "position_in": a.position_in or [],
                       "must_cite_any": a.must_cite, "why": a.why},
            "from_trace": a.trace_id, "trace_ts": t["ts"], "trace_prompt_version": t["prompt_version"],
            "trace_position": t["position"], "trace_grounds": t["grounds"],
            "how_found": a.how_found}
    os.makedirs("evals", exist_ok=True)
    path = os.path.join("evals", "%s.json" % case["id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(case, f, indent=2, ensure_ascii=False)
    print("wrote", path)
    print(json.dumps({k: case[k] for k in ("claim_number", "date_of_loss", "excess", "expect")}, indent=1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
