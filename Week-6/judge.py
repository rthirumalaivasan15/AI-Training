"""Run a judge prompt over the frozen summaries - only once the hand labels are committed.

    python judge.py v1
    python judge.py v2

The blind protocol is enforced here rather than promised in a README. The judge
makes no call at all unless labels_25.json:
  - exists and holds a PASS or FAIL for every case,
  - was taken against the summaries.jsonl that exists now (sha match),
  - is committed, with no uncommitted edits on top of that commit.
Every run file then records the labels' commit hash and commit time beside the
time the judge started, so the ordering is in the run itself as well as git log.

v2 additionally refuses to run until prediction.txt is committed.

A finished run is a record: runs/judge_<version>.jsonl is read back, not re-run.
Delete it to run again.
"""
import os
import re
import sys
import json
import glob
import hashlib
import datetime
import subprocess

import cases as case_store
import summarise

LABELS = "labels_25.json"
PREDICTION = "prediction.txt"
CRITERION = "criterion.txt"
RUNS = "runs"

# A smaller model than the summariser's gpt-oss-120b. qwen/qwen3.8-27b was the
# first choice - a different family, so the judge would not be marking its own
# family's homework - and it judged v1 twice (runs/judge_v1_qwen*.jsonl) before its
# free-tier token budget ran out part way through v2. Rather than compare v1 on one
# model against v2 on another, both versions were re-run here on one model.
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "openai/gpt-oss-20b")
JUDGE_PARAMS = {"temperature": 0}
JUDGE_SYSTEM = "You are a careful insurance claims reviewer. Reply with JSON only."

VERDICT = re.compile(r'"verdict"\s*:\s*"?(PASS|FAIL)', re.I)
REASON = re.compile(r'"reason"\s*:\s*"((?:[^"\\]|\\.)*)"', re.S)
THINK = re.compile(r"<think>.*?(</think>|$)", re.S)


class Locked(Exception):
    """The judge is not allowed to run yet."""


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def committed(path):
    """(hash, commit time) of the last commit touching path. Locked if the file is
    uncommitted or has edits on top of its last commit."""
    if not os.path.exists(path):
        raise Locked("%s does not exist" % path)
    if git("status", "--porcelain", "--", path):
        raise Locked("%s has uncommitted changes - commit it first" % path)
    last = git("log", "-1", "--format=%H %cI", "--", path)
    if not last:
        raise Locked("%s is not committed - commit it first" % path)
    commit, when = last.split()
    return commit, when


def read_labels():
    if not os.path.exists(LABELS):
        return None
    with open(LABELS, encoding="utf-8") as f:
        return json.load(f)


def labels_lock():
    data = read_labels()
    if data is None:
        raise Locked("labels_25.json does not exist - run label.py first")
    ids = [c["id"] for c in case_store.load()]
    missing = [i for i in ids if data["labels"].get(i, {}).get("label") not in ("PASS", "FAIL")]
    if missing:
        raise Locked("labels_25.json has no label for %d case(s)" % len(missing))
    if data["summaries_sha"] != summarise.file_sha():
        raise Locked("summaries.jsonl changed since labelling (labelled %s, now %s)"
                     % (data["summaries_sha"], summarise.file_sha()))
    commit, when = committed(LABELS)
    first = git("log", "--diff-filter=A", "--format=%H %cI", "--", LABELS).splitlines()[-1].split()
    return {"labels_first_commit": first[0], "labels_first_committed_at": first[1],
            "labels_commit": commit, "labels_committed_at": when}


def endorsements():
    parts = []
    for path in sorted(glob.glob(os.path.join("data", "*.txt"))):
        with open(path, encoding="utf-8") as f:
            parts.append(f.read().strip())
    return "\n\n==========\n\n".join(parts)


def prompt_text(version):
    if not os.path.exists("judge_%s.txt" % version):
        raise Locked("judge_%s.txt does not exist yet" % version)
    with open("judge_%s.txt" % version, encoding="utf-8") as f:
        template = f.read()
    with open(CRITERION, encoding="utf-8") as f:
        criterion = f.read().strip()
    if criterion not in template:
        raise Locked("judge_%s.txt does not contain criterion.txt word for word - the judge "
                     "and the hand labels would be answering different questions" % version)
    return template


def render(template, case, summary):
    return (template.replace("{{ENDORSEMENTS}}", endorsements())
                    .replace("{{NOTES}}", case["notes"])
                    .replace("{{SUMMARY}}", summary))


def parse(reply):
    # qwen can think out loud before answering, and a draft verdict in there is not the answer
    reply = THINK.sub("", reply or "")
    verdict, reason = VERDICT.search(reply), REASON.search(reply)
    return (verdict.group(1).upper() if verdict else None,
            reason.group(1) if reason else (reply or "")[:300])


def run_path(version, tag=""):
    return os.path.join(RUNS, "judge_%s%s.jsonl" % (version, "_" + tag if tag else ""))


def load_run(version, tag=""):
    path = run_path(version, tag)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return rows[0], {r["id"]: r for r in rows[1:]}


def run(version, tag=""):
    """tag="repeat" runs the same prompt again into its own file, to measure how
    many verdicts flip with nothing changed - the noise any v1 -> v2 move has to beat."""
    template = prompt_text(version)
    lock = labels_lock()
    if version != "v1":
        if load_run("v1") is None:
            raise Locked("run judge v1 before %s" % version)
        pcommit, pwhen = committed(PREDICTION)
        lock.update(prediction_commit=pcommit, prediction_committed_at=pwhen)

    cached = load_run(version, tag)
    if cached:
        return cached

    started = utc_now()
    if datetime.datetime.fromisoformat(lock["labels_committed_at"]) >= started:
        raise Locked("the labels commit is not earlier than now - check the system clock")

    summaries = summarise.load_summaries()
    header = {"type": "header", "version": version, "tag": tag,
              "prompt_file": "judge_%s.txt" % version,
              "prompt_sha": hashlib.sha256(template.encode("utf-8")).hexdigest()[:12],
              "model": JUDGE_MODEL, "params": JUDGE_PARAMS,
              "started_at": started.isoformat(timespec="seconds"),
              "summaries_sha": summarise.file_sha(), **lock}

    # Each verdict is appended as it arrives. A run that dies part way through -
    # a rate limit, a dropped connection - keeps what it had and resumes, instead
    # of throwing away 22 paid-for verdicts the way the first v2 attempt did.
    os.makedirs(RUNS, exist_ok=True)
    partial = run_path(version, tag) + ".partial"
    rows, done = [], set()
    if os.path.exists(partial):
        with open(partial, encoding="utf-8") as f:
            saved = [json.loads(line) for line in f if line.strip()]
        same = (saved and saved[0].get("prompt_sha") == header["prompt_sha"]
                and saved[0].get("summaries_sha") == header["summaries_sha"]
                and saved[0].get("labels_commit") == header["labels_commit"])
        if same:
            header, rows = saved[0], saved[1:]
            done = {r["id"] for r in rows}
            print("resuming %s: %d verdicts already recorded" % (version, len(rows)))
        else:
            os.remove(partial)
    if not os.path.exists(partial):
        with open(partial, "w", encoding="utf-8") as f:
            f.write(json.dumps(header, ensure_ascii=False) + "\n")

    for case in case_store.load():
        if case["id"] in done:
            continue
        prompt = render(template, case, summaries[case["id"]]["summary"])
        reply = summarise.call_model(JUDGE_SYSTEM, prompt, model=JUDGE_MODEL, params=JUDGE_PARAMS)
        verdict, reason = parse(reply)
        if verdict is None:
            # one retry on an unreadable reply; a second miss is recorded as unparsed,
            # and counts as a disagreement rather than being quietly dropped
            reply = summarise.call_model(JUDGE_SYSTEM, prompt, model=JUDGE_MODEL, params=JUDGE_PARAMS)
            verdict, reason = parse(reply)
        row = {"id": case["id"], "verdict": verdict, "reason": reason, "raw": reply}
        rows.append(row)
        with open(partial, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("  judge %s  %s -> %s" % (version, case["id"], verdict), flush=True)

    header["finished_at"] = utc_now().isoformat(timespec="seconds")
    with open(partial, "w", encoding="utf-8") as f:
        for row in [header] + rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(partial, run_path(version, tag))
    return header, {r["id"]: r for r in rows}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    version = sys.argv[1] if len(sys.argv) > 1 else "v1"
    tag = sys.argv[2] if len(sys.argv) > 2 else ""
    try:
        header, verdicts = run(version, tag)
    except Locked as exc:
        raise SystemExit("JUDGE LOCKED - %s" % exc)
    print("\njudge %s  model %s  started %s" % (version, header["model"], header["started_at"]))
    print("labels committed %s at %s" % (header["labels_commit"][:7], header["labels_committed_at"]))
    print("PASS %d  FAIL %d  unparsed %d" % tuple(
        sum(1 for v in verdicts.values() if v["verdict"] == want) for want in ("PASS", "FAIL", None)))
