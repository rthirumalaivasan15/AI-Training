"""The Week 6 app: an adjuster's file notes in, a claim summary out.

What decides what the model sees is the Week 5 assistant, unchanged - hybrid
retrieval at k=3 and the 0.35 dense-score floor. Only the output moved, from a
free-text answer to the fixed labelled lines a claim summary needs.

    python summarise.py                 # summarise every case not yet in summaries.jsonl
    python summarise.py "notes ..."     # one-off: print a summary, write nothing

summaries.jsonl is frozen once written. The hand labels are taken against those
exact bytes (label.py records the file's sha), so this never regenerates a case
it already has.
"""
import os
import sys
import json
import time
import hashlib
import datetime
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

import prompts
import cases as case_store
from search import dense_search
from hybrid import hybrid_search
from index import load_chunks, META_FIELDS

load_dotenv()

BASE_URL = "https://api.groq.com/openai/v1"
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
PARAMS = {"temperature": 0}
SCORE_FLOOR = 0.35
K = 3
SUMMARIES = "summaries.jsonl"

# What the shipped floor produces. The model is never called, so nothing from the
# notes reaches the summary either - kept exactly as the app behaves.
FLOOR_SUMMARY = """CLAIM NUMBER: NOT STATED
DATE OF LOSS: NOT STATED
POLICY FORMS: NONE
LOSS: NOT STATED
COVERAGE POSITION: NOT_IN_DOCUMENTS
GROUNDS: NONE
EXCESS: NOT STATED
REASONING: No endorsement passage scored above the retrieval floor.
NEXT STEP: Refer to a senior adjuster."""

_by_id = {r["chunk_id"]: r for r in load_chunks()}
_client = None


def client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url=BASE_URL)
    return _client


def call_model(system, user, model=MODEL, params=PARAMS, retries=8):
    """Shared with judge.py. Retries on rate limiting only - any other error stops
    the run, because a summary or a verdict silently missing is worse than a stop."""
    for attempt in range(retries):
        try:
            msg = client().chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                **params
            ).choices[0].message
            return (msg.content or "").strip()
        except RateLimitError:
            time.sleep(min(60, 10 * (attempt + 1)))
    raise RuntimeError("still rate limited after %d attempts" % retries)


def pinned_hit(chunk_id):
    row = _by_id[chunk_id]
    return {"chunk_id": chunk_id, "text": row["text"],
            "meta": {f: row[f] for f in META_FIELDS}}


def build_context(hits):
    blocks = []
    for h in hits:
        blocks.append("[%s] (%s, %s ed. %s)\n%s"
                      % (h["chunk_id"], h["meta"]["policy_line"], h["meta"]["form_number"],
                         h["meta"]["edition"], h["text"]))
    return "\n\n---\n\n".join(blocks)


def summarise(notes, pinned=None):
    if pinned:
        # a regression replay: the trace's own passages, and the trace already
        # records that the floor did not fire, so there is no floor decision to retake
        hits, best_dense, floored = [pinned_hit(c) for c in pinned], None, False
    else:
        hits = hybrid_search(notes, K)
        best_dense = dense_search(notes, 1)[0]["score"]
        floored = best_dense < SCORE_FLOOR

    if floored:
        text = FLOOR_SUMMARY
    else:
        text = call_model(prompts.get(prompts.ACTIVE),
                          "Adjuster notes:\n%s\n\nContext:\n\n%s" % (notes, build_context(hits)))

    return {
        "summary": text,
        "retrieved": [h["chunk_id"] for h in hits],
        "best_dense_score": None if best_dense is None else round(best_dense, 4),
        "refused_by": "score floor" if floored else None,
        "model": None if floored else MODEL,
        "params": PARAMS,
        "prompt_version": prompts.ACTIVE,
        "prompt_sha": prompts.sha(prompts.ACTIVE),
    }


def load_summaries(path=SUMMARIES):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {r["id"]: r for r in (json.loads(line) for line in f if line.strip())}


def file_sha(path=SUMMARIES):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


def generate_missing(path=SUMMARIES):
    have = load_summaries(path)
    todo = [c for c in case_store.load() if c["id"] not in have]
    for i, case in enumerate(todo, 1):
        row = {"id": case["id"], **summarise(case["notes"], case.get("pinned_chunks")),
               "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("  summarised %s (%d/%d)%s" % (case["id"], i, len(todo),
                                             "  [score floor]" if row["refused_by"] else ""))
    return load_summaries(path)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1:
        out = summarise(" ".join(sys.argv[1:]))
        print("retrieved:", ", ".join(out["retrieved"]), "| best dense:", out["best_dense_score"])
        print(out["summary"])
    else:
        rows = generate_missing()
        print("%d summaries in %s, sha %s" % (len(rows), SUMMARIES, file_sha()))
