"""The Week 6 judge - same prompt file (sha-checked), criterion, model and parse - re-run on
the integrated system's outputs, with the integrated wording library as its reference.

(Week 11 note follows.) The Week 6 judge, unchanged, as a function the Week 11 suite calls.

Same prompt file (../Week-6/judge_v2.txt, refused unless its sha is the one Week 6's
own v2 run recorded), same criterion, same six endorsements, same model
(openai/gpt-oss-20b, temperature 0), same parse, same one retry on an unreadable
reply. A case passes the Week 6 rule when all four assertions pass and the judge
says PASS.
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


def endorsements(as_of=None):
    """The wording library the judge reads. Week 6 always had one edition per form, so the judge
    saw the wording in force. With two HO-0304 editions, `as_of` (YYYY-MM-DD, the loss date) keeps
    that meaning: only the editions in force on that date. Without it, every edition - and the
    judge was seen applying the 2025 Storm Ingress Allowance to a 2024 loss."""
    ranges = {}
    if as_of:
        day = int(as_of.replace("-", ""))
        with open("chunks.jsonl", encoding="utf-8") as f:
            for c in (json.loads(l) for l in f if l.strip()):
                ranges[c["source_file"]] = (c["in_force_from"], c["in_force_to"])
    parts = []
    for path in sorted(glob.glob(os.path.join("data", "*.txt"))):
        if as_of:
            lo, hi = ranges[os.path.basename(path)]
            if not lo <= day <= hi:
                continue
        with open(path, encoding="utf-8") as f:
            parts.append(f.read().strip())
    return "\n\n==========\n\n".join(parts)


def render(tmpl, case, summary):
    return (tmpl.replace("{{ENDORSEMENTS}}", endorsements(case.get("as_of")))
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
