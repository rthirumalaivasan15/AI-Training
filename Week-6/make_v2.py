"""Build judge_v2.txt: judge_v1.txt plus two of v1's OWN disagreements as worked examples.

    python make_v2.py <case id> <case id>

Refuses unless:
  - runs/judge_v1.jsonl exists, so there are real disagreements to learn from,
  - prediction.txt is committed, so the prediction is on record before the iteration,
  - both ids are cases where v1 disagreed with the hand labels.

The correct verdict and reason in each example are the hand label and the one
line written at labelling time, blind - not a reason written after reading what
the judge said. Nothing else in the prompt moves, so the v1 -> v2 diff is exactly
the two examples.
"""
import os
import sys
import json

import cases as case_store
import summarise
import judge

ANCHOR = "ENDORSEMENTS IN USE"
OUT = "judge_v2.txt"
META = "judge_v2.meta.json"


def example(n, case, summary, judged, label):
    return ("Example %d\n\nADJUSTER NOTES\n%s\n\nSUMMARY\n%s\n\n"
            "The earlier check said: %s - %s\n"
            "The correct verdict is: %s - %s\n"
            % (n, case["notes"], summary, judged["verdict"], judged["reason"],
               label["label"], label["reason"]))


def main(ids):
    if len(ids) != 2:
        raise SystemExit("usage: python make_v2.py <case id> <case id>")
    if os.path.exists(OUT):
        raise SystemExit("%s already exists" % OUT)

    loaded = judge.load_run("v1")
    if loaded is None:
        raise SystemExit("run judge v1 first")
    try:
        prediction_commit, prediction_at = judge.committed(judge.PREDICTION)
    except judge.Locked as exc:
        raise SystemExit("%s - the prediction has to be on record before the iteration" % exc)

    header, verdicts = loaded
    labels = judge.read_labels()["labels"]
    for i in ids:
        if i not in verdicts:
            raise SystemExit("%s is not a case" % i)
        if verdicts[i]["verdict"] == labels[i]["label"]:
            raise SystemExit("%s is not a disagreement - v1 and the hand label both say %s"
                             % (i, labels[i]["label"]))

    cases = {c["id"]: c for c in case_store.load()}
    summaries = summarise.load_summaries()
    block = ("WORKED EXAMPLES\n"
             "These two summaries were checked against the same criterion before, and that "
             "check got both of them wrong. The correct verdicts are a claims reviewer's.\n\n"
             + "\n".join(example(n, cases[i], summaries[i]["summary"], verdicts[i], labels[i])
                         for n, i in enumerate(ids, 1))
             + "\n")

    template = judge.prompt_text("v1")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(template.replace(ANCHOR, block + ANCHOR, 1))
    with open(META, "w", encoding="utf-8") as f:
        json.dump({"few_shot_ids": ids, "built_from_run_started_at": header["started_at"],
                   "prediction_commit": prediction_commit,
                   "prediction_committed_at": prediction_at}, f, indent=2)
        f.write("\n")
    print("wrote %s with few-shot %s, and %s" % (OUT, ", ".join(ids), META))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
