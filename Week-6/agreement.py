"""Agreement between the hand labels and each judge run.

    python agreement.py

Agreement is an exact PASS/FAIL match - there is no tolerance band to hide in.
It is reported with the two ways of disagreeing split out, because they do not
cost the same: a judge PASS on a summary the hand label failed is a wrong coverage
position routed through as fine, and that is the one claims ops pays for.

After v2 it also reports agreement with the two few-shot cases held out. Those
two are in v2's prompt with their answers, so counting them flatters v2.
"""
import os
import sys
import json

import cases as case_store
import judge

META = "judge_v2.meta.json"
OUT = "agreement.json"


def kappa(pairs):
    n = len(pairs)
    observed = sum(h == j for h, j in pairs) / n
    human_pass = sum(h == "PASS" for h, _ in pairs) / n
    judge_pass = sum(j == "PASS" for _, j in pairs) / n
    expected = human_pass * judge_pass + (1 - human_pass) * (1 - judge_pass)
    return None if expected == 1 else round((observed - expected) / (1 - expected), 2)


def compare(labels, verdicts, ids):
    pairs = [(labels[i]["label"], verdicts[i]["verdict"]) for i in ids]
    agree = sum(h == j for h, j in pairs)
    return {
        "n": len(ids),
        "agree": agree,
        "pct": round(100.0 * agree / len(ids), 1),
        "kappa": kappa(pairs),
        "judge_pass_human_fail": sum(h == "FAIL" and j == "PASS" for h, j in pairs),
        "judge_fail_human_pass": sum(h == "PASS" and j == "FAIL" for h, j in pairs),
        "unparsed": sum(j is None for _, j in pairs),
        "disagreements": [i for i, (h, j) in zip(ids, pairs) if h != j],
    }


def few_shot_ids():
    if not os.path.exists(META):
        return []
    with open(META, encoding="utf-8") as f:
        return json.load(f)["few_shot_ids"]


def line(name, r):
    return ("%-9s %2d/%d = %5.1f%%   kappa %s   judge-PASS/human-FAIL %d   judge-FAIL/human-PASS %d%s"
            % (name, r["agree"], r["n"], r["pct"], r["kappa"], r["judge_pass_human_fail"],
               r["judge_fail_human_pass"], "   unparsed %d" % r["unparsed"] if r["unparsed"] else ""))


def report(labels_doc, runs):
    """runs is {version: (header, verdicts)}. Prints, and writes agreement.json."""
    labels = labels_doc["labels"]
    ids = [c["id"] for c in case_store.load()]
    out = {}

    print("\nAGREEMENT WITH THE HAND LABELS  (exact PASS/FAIL match over %d labels)" % len(ids))
    commits = {v: h["labels_commit"] for v, (h, _) in runs.items()}
    if len(set(commits.values())) > 1:
        print("  !! LABELS CHANGED BETWEEN JUDGE RUNS %s - before/after is not comparable" % commits)

    for version, (header, verdicts) in runs.items():
        r = compare(labels, verdicts, ids)
        out[version] = r
        print("  " + line("judge " + version, r))
        print("            labels committed %s at %s, judge started %s"
              % (header["labels_commit"][:7], header["labels_committed_at"], header["started_at"]))
        for i in r["disagreements"]:
            print("            %s  human %s, judge %s - %s"
                  % (i, labels[i]["label"], verdicts[i]["verdict"], (verdicts[i]["reason"] or "")[:90]))

    if "v1" in runs and "v2" in runs:
        shots = few_shot_ids()
        held = [i for i in ids if i not in shots]
        r = compare(labels, runs["v2"][1], held)
        out["v2_held_out"] = r
        print("  " + line("v2 held", r) + "   (without few-shot %s)" % ", ".join(shots))
        before, after = set(out["v1"]["disagreements"]), set(out["v2"]["disagreements"])
        print("            fixed by v2: %s" % (", ".join(sorted(before - after)) or "none"))
        print("            broken by v2: %s" % (", ".join(sorted(after - before)) or "none"))

    summary = {"agreement_before": out.get("v1", {}).get("pct"),
               "agreement_after": out.get("v2", {}).get("pct"),
               "agreement_after_held_out": out.get("v2_held_out", {}).get("pct"),
               "detail": out}
    print("\n  agreement_before = %s   agreement_after = %s   (held out: %s)"
          % (summary["agreement_before"], summary["agreement_after"],
             summary["agreement_after_held_out"]))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    labels_doc = judge.read_labels()
    runs = {v: judge.load_run(v) for v in ("v1", "v2") if judge.load_run(v)}
    if not labels_doc or not runs:
        raise SystemExit("needs labels_25.json and at least one judge run")
    report(labels_doc, runs)
