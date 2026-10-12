"""The Week 6 judge, unchanged, over both arms' summaries.

    python judge.py runs/race_single.jsonl runs/race_multi.jsonl

Same prompt file (../Week-6/judge_v2.txt, sha checked against the sha Week 6's
own v2 run recorded), same criterion, same six endorsements, same model
(openai/gpt-oss-20b, temperature 0), same parse, same one retry on an unreadable
reply. PASS for a case = all four Week 6 assertions + judge PASS - the Week 6 rule.

Verdicts are appended to runs/judge_<run>.jsonl as they arrive; a finished
verdict is never re-asked.
"""
import os
import re
import sys
import glob
import json
import time
import hashlib

from openai import RateLimitError

import llm
import cases
import assertions

WEEK6 = os.path.join("..", "Week-6")
PROMPT_FILE = os.path.join(WEEK6, "judge_v2.txt")
CRITERION = os.path.join(WEEK6, "criterion.txt")
WEEK6_V2_SHA = "af8559b5e5e4"          # prompt_sha in Week-6/runs/judge_v2.jsonl
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "openai/gpt-oss-20b")
JUDGE_PARAMS = {"temperature": 0}
JUDGE_SYSTEM = "You are a careful insurance claims reviewer. Reply with JSON only."

VERDICT = re.compile(r'"verdict"\s*:\s*"?(PASS|FAIL)', re.I)
REASON = re.compile(r'"reason"\s*:\s*"((?:[^"\\]|\\.)*)"', re.S)
THINK = re.compile(r"<think>.*?(</think>|$)", re.S)


def template():
    with open(PROMPT_FILE, encoding="utf-8") as f:
        text = f.read()
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    if sha != WEEK6_V2_SHA:
        raise SystemExit("judge prompt sha %s is not the Week 6 v2 sha %s" % (sha, WEEK6_V2_SHA))
    with open(CRITERION, encoding="utf-8") as f:
        assert f.read().strip() in text
    return text


def endorsements():
    parts = []
    for path in sorted(glob.glob(os.path.join(WEEK6, "data", "*.txt"))):
        with open(path, encoding="utf-8") as f:
            parts.append(f.read().strip())
    return "\n\n==========\n\n".join(parts)


def render(tmpl, case, summary):
    return (tmpl.replace("{{ENDORSEMENTS}}", endorsements())
                .replace("{{NOTES}}", case["notes"])
                .replace("{{SUMMARY}}", summary))


def parse(reply):
    reply = THINK.sub("", reply or "")
    verdict, reason = VERDICT.search(reply), REASON.search(reply)
    return (verdict.group(1).upper() if verdict else None,
            reason.group(1) if reason else (reply or "")[:300])


def ask(prompt, retries=12):
    for attempt in range(retries):
        try:
            resp = llm.client().chat.completions.create(
                model=JUDGE_MODEL, messages=[{"role": "system", "content": JUDGE_SYSTEM},
                                             {"role": "user", "content": prompt}], **JUDGE_PARAMS)
            u = resp.usage
            return (resp.choices[0].message.content or "").strip(), u.prompt_tokens + u.completion_tokens
        except RateLimitError as exc:
            wait = llm.retry_after(exc, fallback=min(120, 10 * (attempt + 1)))
            print("    rate limited, waiting %.0fs" % wait, flush=True)
            time.sleep(wait)
    raise RuntimeError("judge still rate limited after %d attempts" % retries)


def judge_file(run_path):
    tmpl = template()
    by_id = {c["id"]: c for c in cases.load()}
    out_path = os.path.join("runs", "judge_" + os.path.basename(run_path))
    done = set()
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            done = {json.loads(l)["id"] for l in f if l.strip()}
    with open(run_path, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
    for row in rows:
        if row["id"] in done:
            continue
        case, summary = by_id[row["id"]], row["summary"] or ""
        prompt = render(tmpl, case, summary)
        reply, tokens = ask(prompt)
        verdict, reason = parse(reply)
        if verdict is None:     # Week 6 rule: one retry, then recorded as unparsed
            reply, more = ask(prompt)
            tokens += more
            verdict, reason = parse(reply)
        checks = assertions.run(case, summary)
        rec = {"id": row["id"], "arm": row["arm"], "verdict": verdict, "reason": reason,
               "assertions": checks, "asserts_ok": all(c["passed"] for c in checks),
               "pass": verdict == "PASS" and all(c["passed"] for c in checks),
               "judge_tokens": tokens, "judge_model": JUDGE_MODEL, "prompt_sha": WEEK6_V2_SHA,
               "cases_sha": cases.source_sha()}
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print("  judge %-6s %s  judge %-4s asserts %s  -> %s" % (
            row["arm"], row["id"], verdict, "ok" if rec["asserts_ok"] else "FAIL",
            "PASS" if rec["pass"] else "FAIL"), flush=True)
    return out_path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for path in sys.argv[1:]:
        print("wrote", judge_file(path))
