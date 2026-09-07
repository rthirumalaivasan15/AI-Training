"""The Week 4 claims assistant, unchanged, with a trace written around it.

Nothing in the answering logic moved. The retriever, the score floor, the k, the
prompt and the citation check are all the Week 4 behaviour - this file only adds
the recording. That matters because a taxonomy is only about the app it was read
from.
"""
import os
import re
import sys
import time
from dotenv import load_dotenv
from openai import OpenAI

import prompts
import trace as tracer
from search import dense_search
from hybrid import hybrid_search

load_dotenv()

BASE_URL = "https://api.groq.com/openai/v1"
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
SCORE_FLOOR = 0.35
REFUSAL = "NOT_IN_DOCUMENTS"

# Exactly what Week 4 sent - temperature and nothing else. I had a max_tokens in
# here at first and took it out: gpt-oss-120b spends completion tokens on hidden
# reasoning, so a cap I invented would have produced truncation failures that the
# real app does not have, and I would have read them as a finding.
PARAMS = {"temperature": 0}

RETRIEVERS = {"dense": dense_search, "hybrid": hybrid_search}

# answer.py ships with hybrid_search as its default, so that is what is traced
DEFAULT_RETRIEVER = "hybrid"

_client = None
_corpus_sha = tracer.corpus_fingerprint()


def client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url=BASE_URL)
    return _client


def build_context(hits):
    blocks = []
    for h in hits:
        blocks.append("[%s] (%s, %s ed. %s)\n%s"
                      % (h["chunk_id"], h["meta"]["policy_line"], h["meta"]["form_number"],
                         h["meta"]["edition"], h["text"]))
    return "\n\n---\n\n".join(blocks)


def cited_ids(text):
    return sorted(set(re.findall(r"[\[【]([A-Z]{2}-\d{4}_[\d-]+#\d{2})[\]】]", text or "")))


def call_model(system, user, params=PARAMS, model=MODEL):
    """Returns (answer, reasoning). gpt-oss-120b exposes its scratchpad in a
    `reasoning` field; it is kept because it is the only way to see why the model
    landed where it did when reading a trace afterwards."""
    msg = client().chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        **params
    ).choices[0].message
    return (msg.content or "").strip(), (getattr(msg, "reasoning", None) or "").strip()


def answer(question, retriever=DEFAULT_RETRIEVER, k=3,
           prompt_version=prompts.ACTIVE, write=True, path=tracer.TRACE_FILE,
           extra=None):
    started = time.perf_counter()

    hits = RETRIEVERS[retriever](question, k)
    best_dense = dense_search(question, 1)[0]["score"]

    if best_dense < SCORE_FLOOR:
        reply, reasoning, refused_by, error = REFUSAL, "", "score floor", None
    else:
        try:
            reply, reasoning = call_model(
                prompts.get(prompt_version),
                "Context:\n\n%s\n\nQuestion: %s" % (build_context(hits), question))
            refused_by = "model" if reply == REFUSAL else None
            error = None
        except Exception as exc:
            reply, reasoning, refused_by = "", "", None
            error = "%s: %s" % (type(exc).__name__, exc)

    retrieved_ids = {h["chunk_id"] for h in hits}
    citations = cited_ids(reply)

    record = {
        "schema": tracer.SCHEMA,
        "trace_id": tracer.new_trace_id(),
        "ts": tracer.utc_now(),
        "corpus_sha": _corpus_sha,
        "question": question,
        "retriever": retriever,
        "k": k,
        "retrieved": [{"rank": i, "chunk_id": h["chunk_id"], "score": round(h["score"], 4),
                       "form_number": h["meta"]["form_number"], "edition": h["meta"]["edition"]}
                      for i, h in enumerate(hits, 1)],
        "best_dense_score": round(best_dense, 4),
        "model": MODEL,
        "params": PARAMS,
        "prompt_version": prompt_version,
        "prompt_sha": prompts.sha(prompt_version),
        "raw_output": reply,
        "reasoning": reasoning,
        "citations": citations,
        "dangling_citations": sorted(set(citations) - retrieved_ids),
        "refused_by": refused_by,
        "error": error,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }
    record.update(extra or {})

    return tracer.write(record, path) if write else record


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    rec = answer(" ".join(sys.argv[1:]))
    print("trace_id:", rec["trace_id"])
    print("question:", rec["question"])
    print("retrieved:", ", ".join("%s(%.3f)" % (r["chunk_id"], r["score"])
                                  for r in rec["retrieved"]))
    print("\n" + rec["raw_output"])
