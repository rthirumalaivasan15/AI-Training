"""Production traces for the claims app: one JSON line per request, in
logs/<local date>.jsonl, redacted before it is written.

A trace carries everything needed to find a bad answer and explain it in one hop:
- who / when / which prompt: ts, user, input_type, prompt_version + prompt_sha, model;
- the input AND the output, both redacted, plus the output's coverage position and
  grounds as their own fields - a complaint describes the output ("said it was
  covered"), so the output has to be searchable, not just the question;
- retrieved context ids, so "did retrieval miss the clause or did the model ignore
  it" is answerable from the trace;
- spans: every model call (generation), every search_policy call (retrieval) and
  every other tool call (tools), each with its own latency, tokens and cost;
- cost by stage: every prompt token of every model call is attributed to what it
  carried - instructions and the notes, the model's own earlier turns, retrieved
  passages, or other tool results - see split_prompt().

The PII line: claimant names, phones, emails, addresses and policy numbers are
redacted on write (redact.py, from Week 5). Claim numbers are kept: they are the
business key, and they identify no one without access to the claims system.
"""
import os
import re
import json
import time
import secrets
import datetime

import tiktoken

import llm
import redact

LOG_DIR = "logs"
TEXT_FIELDS = ("input", "output")
CLAIM = re.compile(r"\bCLM-\d{4}-\d{5}\b")
CODE = re.compile(r"\bE-\d{2}\b")
DAY_FILE = re.compile(r"\d{4}-\d{2}-\d{2}\.jsonl")
_enc = tiktoken.get_encoding("o200k_base")   # gpt-oss's tokenizer family; used only to split a known total


def now():
    return datetime.datetime.now().astimezone()


def _count(text):
    return len(_enc.encode(text or "", disallowed_special=()))


def split_prompt(messages, tools, tool_names):
    """Estimated tokens of one call's prompt by what they carry. Scaled to the
    provider's real prompt_tokens afterwards, so the totals stay exact and only
    the split is an estimate."""
    parts = {"instructions": _count(json.dumps(tools)) if tools else 0,
             "history": 0, "retrieval": 0, "tools": 0}
    for m in messages:
        n = _count(m.get("content") or "") + _count(json.dumps(m.get("tool_calls", "")))
        if m["role"] in ("system", "user"):
            parts["instructions"] += n
        elif m["role"] == "assistant":
            parts["history"] += n
        elif tool_names.get(m.get("tool_call_id")) == "search_policy":
            parts["retrieval"] += n
        else:
            parts["tools"] += n
    return parts


def _scale(parts, total):
    est = sum(parts.values()) or 1
    scaled = {k: round(v * total / est) for k, v in parts.items()}
    scaled["instructions"] += total - sum(scaled.values())   # rounding remainder
    return scaled


class Trace:
    def __init__(self, user, input_type, notes, prompt_version, prompt_sha):
        self.id = "trc_" + secrets.token_hex(6)
        self.started_at = now()
        self.t0 = time.perf_counter()
        self.record = {"trace_id": self.id, "user": user, "input_type": input_type,
                       "prompt_version": prompt_version, "prompt_sha": prompt_sha,
                       "model": llm.MODEL, "input": notes}
        self.spans = []
        self.rate_limits = {}
        self.rate_limited = []

    def _offset_ms(self, started):
        return round((started - self.t0) * 1000)

    def generation(self, lap, started, usage, parts):
        split = _scale(parts, usage["prompt_tokens"])
        self.spans.append({
            "span": len(self.spans) + 1, "kind": "generation", "name": "model call %d" % lap,
            "start_ms": self._offset_ms(started), "latency_ms": round(usage["call_s"] * 1000),
            "rate_limit_wait_ms": round(usage["wait_s"] * 1000),
            "prompt_tokens": usage["prompt_tokens"], "completion_tokens": usage["completion_tokens"],
            "cost_usd": round(usage["cost_usd"], 8), "finish_reason": usage["finish_reason"],
            "estimated_usage": bool(usage.get("estimated")),
            "prompt_tokens_by_content": split})
        if usage.get("rate_limits"):
            self.rate_limits = usage["rate_limits"]
        self.rate_limited += usage.get("rate_limited", [])

    def setup(self, started, latency_s, servers):
        self.spans.append({"span": len(self.spans) + 1, "kind": "setup",
                           "name": "start MCP servers: %s" % ", ".join(servers),
                           "start_ms": self._offset_ms(started), "latency_ms": round(latency_s * 1000),
                           "cost_usd": 0.0})

    def tool(self, name, started, latency_s, args, result):
        kind = "retrieval" if name == "search_policy" else "tool"
        span = {"span": len(self.spans) + 1, "kind": kind, "name": name,
                "start_ms": self._offset_ms(started), "latency_ms": round(latency_s * 1000),
                "args": args, "cost_usd": 0.0, "error": result.get("error") if isinstance(result, dict) else None}
        if kind == "retrieval":
            span["context_ids"] = [p["chunk_id"] for p in (result.get("passages") or [])] \
                if isinstance(result, dict) else []
        span["result_tokens"] = _count(json.dumps(result, ensure_ascii=False))
        self.spans.append(span)

    def finish(self, output, fields, stop_reason=None, error=None):
        gens = [s for s in self.spans if s["kind"] == "generation"]
        p = sum(s["prompt_tokens"] for s in gens)
        c = sum(s["completion_tokens"] for s in gens)
        wait = sum(s["rate_limit_wait_ms"] for s in gens) / 1000
        wall = time.perf_counter() - self.t0
        context = []
        for s in self.spans:
            for cid in s.get("context_ids", []):
                if cid not in context:
                    context.append(cid)

        price_in, price_out = llm.PRICE_IN / 1e6, llm.PRICE_OUT / 1e6
        by = {k: sum(s["prompt_tokens_by_content"][k] for s in gens)
              for k in ("instructions", "history", "retrieval", "tools")}
        stage = {
            "retrieval": {"prompt_tokens": by["retrieval"], "completion_tokens": 0,
                          "cost_usd": round(by["retrieval"] * price_in, 8),
                          "latency_ms": sum(s["latency_ms"] for s in self.spans if s["kind"] == "retrieval")},
            "generation": {"prompt_tokens": by["instructions"] + by["history"], "completion_tokens": c,
                           "cost_usd": round((by["instructions"] + by["history"]) * price_in + c * price_out, 8),
                           "latency_ms": sum(s["latency_ms"] for s in gens)},
            "tools": {"prompt_tokens": by["tools"], "completion_tokens": 0,
                      "cost_usd": round(by["tools"] * price_in, 8),
                      "latency_ms": sum(s["latency_ms"] for s in self.spans if s["kind"] == "tool")},
        }
        self.record.update({
            "ts": self.started_at.isoformat(timespec="milliseconds"),
            "output": output or "",
            "claim_number": (CLAIM.search(self.record["input"] or "") or [None])[0],
            "position": fields.get("COVERAGE POSITION"),
            "grounds": fields.get("GROUNDS"),
            "context_ids": context,
            "laps": len(gens), "tool_calls": len(self.spans) - len(gens),
            "prompt_tokens": p, "completion_tokens": c, "tokens": p + c,
            "cost_usd": round(sum(s["cost_usd"] for s in gens), 8),
            "latency_s": round(wall, 3), "active_s": round(wall - wait, 3), "rate_limit_wait_s": round(wait, 1),
            "cost_by_stage": stage,
            "setup_ms": sum(s["latency_ms"] for s in self.spans if s["kind"] == "setup"),
            "rate_limits": self.rate_limits, "rate_limited": self.rate_limited,
            "stop_reason": stop_reason, "error": error, "spans": self.spans,
        })
        return self.record

    def write(self, log_dir=LOG_DIR):
        return write(self.record, log_dir)


def scrub(record):
    """Redact every free-text field in place, and refuse if anything survived."""
    tokens = set()
    for field in TEXT_FIELDS:
        tokens |= redact.name_tokens(record.get(field, ""))
    counts = {}
    for field in TEXT_FIELDS:
        clean, hits = redact.redact(record.get(field, ""), also=tokens)
        record[field] = clean
        for label, n in hits.items():
            counts[label] = counts.get(label, 0) + n
    for field in TEXT_FIELDS:
        if not redact.looks_clean(record.get(field, ""), also=tokens):
            raise AssertionError("identifier survived redaction in %s of %s - refusing to write"
                                 % (field, record["trace_id"]))
    record["redactions"] = counts
    return record


def log_path(ts, log_dir=LOG_DIR):
    return os.path.join(log_dir, "%s.jsonl" % ts[:10])


def write(record, log_dir=LOG_DIR):
    scrub(record)
    os.makedirs(log_dir, exist_ok=True)
    with open(log_path(record["ts"], log_dir), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read(day=None, log_dir=LOG_DIR):
    """Every trace, or one day's, oldest first."""
    rows = []
    if not os.path.isdir(log_dir):
        return rows
    for name in sorted(os.listdir(log_dir)):
        # only the day files (YYYY-MM-DD.jsonl) - logs/ also holds verdicts.jsonl from sweep.py
        if DAY_FILE.fullmatch(name) and (day is None or name.startswith(day)):
            with open(os.path.join(log_dir, name), encoding="utf-8") as f:
                rows += [json.loads(l) for l in f if l.strip()]
    return sorted(rows, key=lambda r: r["ts"])
