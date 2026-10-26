"""The eval suite: the 10 Week-6 cases the app was last measured on (Week 10),
read from ../Week-6/cases.jsonl, plus every case file in evals/ - each one a
failure from production turned into a permanent test.

A case file may carry an "expect" block, checked deterministically on top of the
Week 6 judge and assertions:
    "expect": {"position_not": ["COVERED"], "must_cite_any": ["E-52"]}
"""
import os
import json
import glob
import hashlib

WEEK6_CASES = os.path.join("..", "Week-6", "cases.jsonl")
WEEK6_IDS = ["C01", "C02", "C05", "C06", "C09", "C10", "C14", "C15", "C18", "C19"]
EVALS = "evals"


def week6_sha():
    with open(WEEK6_CASES, "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()[:12]


def load():
    with open(WEEK6_CASES, encoding="utf-8") as f:
        by_id = {c["id"]: c for c in (json.loads(l) for l in f if l.strip())}
    cases = [dict(by_id[i], source="Week-6") for i in WEEK6_IDS]
    for path in sorted(glob.glob(os.path.join(EVALS, "*.json"))):
        with open(path, encoding="utf-8") as f:
            cases.append(dict(json.load(f), source=path.replace("\\", "/")))
    return cases
