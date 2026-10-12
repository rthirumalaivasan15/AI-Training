"""The 10 eval cases both arms are raced on - read from Week 6, never rewritten.

Rule, fixed before any run: the first two written cases of each of the five
Week 5 failure modes, in id order. That is C01 C02 | C05 C06 | C09 C10 |
C14 C15 | C18 C19. It leaves out the judge's two worked examples (C12, C22), which
sit inside judge_v2.txt and would be marked by a judge that has seen the answer.

The cases are read straight out of ../Week-6/cases.jsonl every time, and the
file's sha is recorded with every run, so "the same Week-6 cases" is something
the code checks rather than something a README promises.
"""
import os
import json
import hashlib

WEEK6 = os.path.join("..", "Week-6")
SOURCE = os.path.join(WEEK6, "cases.jsonl")
CASE_IDS = ["C01", "C02", "C05", "C06", "C09", "C10", "C14", "C15", "C18", "C19"]


def source_sha():
    with open(SOURCE, "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()[:12]


def load():
    with open(SOURCE, encoding="utf-8") as f:
        by_id = {c["id"]: c for c in (json.loads(line) for line in f if line.strip())}
    return [by_id[i] for i in CASE_IDS]


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("source %s sha %s" % (SOURCE, source_sha()))
    for c in load():
        print("  %s mode %d  %s" % (c["id"], c["mode"], c["notes"][:90]))
