"""Blind hand labels on the judge's one criterion, taken BEFORE any judge runs.

    python label.py

For each summary it shows the adjuster notes, the summary, and the full wording
of every endorsement the notes or the summary name. Answer PASS or FAIL against
criterion.txt, then pick the reason by number (the options are the criterion's
own PASS and FAIL conditions) and optionally add the clause or fact it turns on.

Deliberately NOT shown: the case id (an R prefix gives away a regression case),
the mode a case was written for, the assertion results, and anything a judge
said. Each of those hints at an answer. The reasons are offered only after the
PASS/FAIL key is pressed, and both lists are the criterion word for word, so the
menu cannot lean toward either answer.

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
FORM = re.compile(r"\b(HO|DP)-\d{4}\b")
RULE = "=" * 78

PASS_REASONS = [
    "position and grounds are what the wording gives on these facts",
    "wording genuinely does not settle it, and the summary says what is missing",
]
FAIL_REASONS = [
    "invents coverage, an exclusion, an exception, a limit or a consequence the wording does not state",
    "applies an endorsement not on this policy, or the wrong policy line or edition",
    "applies or rejects an exception without testing the definition that decides it",
    "says silent / UNDETERMINED / NOT_IN_DOCUMENTS when the wording answers it",
    "position is wrong on these facts for another reason",
]


def endorsement_files():
    by_form = {}
    for path in sorted(glob.glob(os.path.join("data", "*.txt"))):
        by_form[os.path.basename(path).split("_")[0]] = path
    return by_form


def save(data):
    partial = LABELS + ".partial"
    with open(partial, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(partial, LABELS)


def ask(prompt, allowed=None, blank_ok=False):
    while True:
        try:
            # PowerShell pipes a byte-order mark ahead of the first line
            answer = input(prompt).strip().lstrip("﻿")
        except EOFError:
            raise SystemExit("\ninput closed - progress is saved, run label.py again to continue")
        if allowed is None and (answer or blank_ok):
            return answer
        if allowed and answer.lower() in allowed:
            return answer.lower()


def pick_reason(options):
    for n, text in enumerate(options, 1):
        print("   %d  %s" % (n, text))
    print("   0  type my own reason")
    choice = ask("reason number: ", {str(n) for n in range(len(options) + 1)})
    if choice == "0":
        return ask("your reason, one line: ")
    detail = ask("clause / fact it turns on (optional, Enter to skip): ", blank_ok=True)
    return options[int(choice) - 1] + (" - " + detail if detail else "")


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

    forms = endorsement_files()
    notes = {c["id"]: c["notes"] for c in all_cases}
    order = sorted(notes)
    random.Random(SEED).shuffle(order)

    print(RULE + "\n" + criterion + "\n" + RULE)
    print("p = PASS, f = FAIL, q = stop and resume later.\n")

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

        named = sorted({m.group(0) for m in FORM.finditer(notes[case_id] + " " + summary)}
                       & set(forms))
        print("\nENDORSEMENT WORDING  (forms named in the notes or the summary: %s)"
              % (", ".join(named) or "none - see data/ for all six"))
        for form in named:
            with open(forms[form], encoding="utf-8") as f:
                print("  " + "-" * 40)
                for line in f.read().strip().splitlines():
                    print("  " + line)

        answer = ask("\n[%d/%d] PASS or FAIL? [p/f/q] " % (n, len(order)), {"p", "f", "q"})
        if answer == "q":
            print("stopped - %d of %d labelled, run label.py again to continue"
                  % (len(data["labels"]), len(order)))
            return
        reason = pick_reason(PASS_REASONS if answer == "p" else FAIL_REASONS)
        data["labels"][case_id] = {"label": "PASS" if answer == "p" else "FAIL", "reason": reason,
                                   "at": utc_now().isoformat(timespec="seconds")}
        data["updated_at"] = utc_now().isoformat(timespec="seconds")
        save(data)
        print("saved (%d of %d)" % (len(data["labels"]), len(order)))

    print("\nAll %d labelled. Commit and push them BEFORE any judge runs:\n" % len(data["labels"]))
    print('  git add labels_25.json')
    print('  git commit -m "Week 6: 25 blind hand labels, committed before any judge run"')
    print('  git push')


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
