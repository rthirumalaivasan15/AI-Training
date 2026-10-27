"""Re-judge a finished eval run with the wording in force on each claim's loss date.

    python rejudge.py after          -> runs/rejudge_after.jsonl
    python rejudge.py before         -> runs/rejudge_before.jsonl

The suite's judge reads every edition in the library; on the first after-fix case it
applied the 2025 Storm Ingress Allowance to a 2024 loss and failed a correct referral.
This re-runs the same Week 6 judge (prompt sha-checked, same model) on the same stored
referrals, with only the editions in force on the loss date - which is what "the
endorsements" meant in Week 6, when every form had one edition. No app call is repeated:
the referral comes from the run's own trace. Each verdict is appended as it arrives.
"""
import os
import sys
import json

import suite
import tracer


def main(tag):
    with open(os.path.join("runs", "eval_%s.jsonl" % tag), encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
    out = os.path.join("runs", "rejudge_%s.jsonl" % tag)
    done = set()
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            done = {json.loads(l)["id"] for l in f if l.strip()}
    traces = {t["trace_id"]: t for t in tracer.read()}
    for r in rows:
        if r["id"] in done:
            continue
        referral = traces[r["trace_id"]].get("referral")
        claim = suite.CLAIMS[r["id"]]
        if referral is None:
            v, reason, tok = None, "no referral", 0
        else:
            v, reason, tok = suite.judge_case(claim, referral, as_of=claim["date_of_loss"])
        rec = {"id": r["id"], "tag": tag, "trace_id": r["trace_id"], "judge_all_editions": r["judge"],
               "judge_as_of_loss_date": v, "reason": reason, "reference_label": r["reference_label"],
               "judge_tokens": tok}
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print("  %-15s all editions %-4s  as of loss date %-4s  reference %s" % (
            r["id"], r["judge"], v, r["reference_label"]), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1])
