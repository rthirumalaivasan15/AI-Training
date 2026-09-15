"""Blind hand labels on the judge's one criterion, taken BEFORE any judge runs.

    python label.py

For each summary it shows the adjuster notes, the summary, and the text of every
passage the summary cites, then asks PASS or FAIL against criterion.txt and one
line of why. Keep the six endorsements in data/ open alongside - the judge is
given all six in full, so the labeller should have them too.

Deliberately NOT shown: the case id (an R prefix gives away a regression case),
the mode a case was written for, the assertion results, and anything a judge
said. Each of those hints at an answer.

Progress is saved after every label, so it can be stopped and resumed. It refuses
to start at all if a judge run already exists.
"""
import os
import re
import sys
import json
import glob
import random
import textwrap

import cases as case_store
import summarise
from judge import LABELS, CRITERION, RUNS, utc_now

SEED = 20260915   # shuffled, so the modes do not arrive in blocks of five
CITED = re.compile(r"[\[【]([A-Z]{2}-\d{4}_[\d-]+#\d{2})[\]】]")
RULE = "=" * 78


def save(data):
    partial = LABELS + ".partial"
    with open(partial, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(partial, LABELS)


def ask(prompt, allowed=None):
    while True:
        answer = input(prompt).strip()
        if allowed is None and answer:
            return answer
        if allowed and answer.lower() in allowed:
            return answer.lower()


def main():
    if glob.glob(os.path.join(RUNS, "judge_*.jsonl")):
        raise SystemExit("A judge run already exists in runs/. Labels taken now would not be blind.")

    all_cases = case_store.load()
    summaries = summarise.load_summaries()
    missing = [c["id"] for c in all_cases if c["id"] not in summaries]
    if missing:
        raise SystemExit("no summary yet for %d case(s) - run summarise.py first" % len(missing))

    sha = summarise.file_sha()
    with open(CRITERION, encoding="utf-8") as f:
        criterion = f.read().strip()

    if os.path.exists(LABELS):
        with open(LABELS, encoding="utf-8") as f:
            data = json.load(f)
        if data["summaries_sha"] != sha:
            raise SystemExit("summaries.jsonl changed since labelling started - labels would not match")
    else:
        data = {"criterion": criterion, "summaries_sha": sha,
                "started_at": utc_now().isoformat(timespec="seconds"), "labels": {}}

    notes = {c["id"]: c["notes"] for c in all_cases}
    order = sorted(notes)
    random.Random(SEED).shuffle(order)

    print(RULE + "\n" + criterion + "\n" + RULE)
    print("Endorsement wording: data/*.txt.  Answer p = PASS, f = FAIL, q = stop and resume later.\n")

    for n, case_id in enumerate(order, 1):
        if case_id in data["labels"]:
            continue
        summary = summaries[case_id]["summary"]

        print("\n" + RULE)
        print("SUMMARY %d of %d" % (n, len(order)))
        print(RULE)
        print("ADJUSTER NOTES")
        print(textwrap.fill(notes[case_id], 78, initial_indent="  ", subsequent_indent="  "))
        print("\nSUMMARY")
        for line in summary.splitlines():
            print(textwrap.fill(line, 78, initial_indent="  ", subsequent_indent="      "))
        cited = sorted(set(CITED.findall(summary)))
        if cited:
            print("\nPASSAGES THE SUMMARY CITES")
            for chunk_id in cited:
                chunk = summarise._by_id.get(chunk_id)
                print("  [%s]" % chunk_id)
                for line in (chunk["text"] if chunk else "(not a chunk in the corpus)").splitlines():
                    print("    " + line)

        answer = ask("\nPASS or FAIL? [p/f/q] ", {"p", "f", "q"})
        if answer == "q":
            print("stopped - %d of %d labelled, run label.py again to continue"
                  % (len(data["labels"]), len(order)))
            return
        reason = ask("why, in one line: ")
        data["labels"][case_id] = {"label": "PASS" if answer == "p" else "FAIL", "reason": reason,
                                   "at": utc_now().isoformat(timespec="seconds")}
        data["updated_at"] = utc_now().isoformat(timespec="seconds")
        save(data)

    print("\nAll %d labelled. Commit them BEFORE running any judge:\n" % len(data["labels"]))
    print('  git add labels_25.json')
    print('  git commit -m "Week 6: 25 blind hand labels, committed before any judge run"')


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
