"""One model client shared by the agent and the workflow, so the race compares
control flow and nothing else: same provider, same model, same parameters.

Every call returns its own usage. Callers sum it themselves - the agent re-sends
the whole message list on every lap, so the only honest token count is the sum
over all laps, not the last call's number.
"""
import os
import re
import time
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIConnectionError

load_dotenv()

BASE_URL = "https://api.groq.com/openai/v1"
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
TEMPERATURE = 0

# USD per 1M tokens, Groq list price for the model above. Check
# https://groq.com/pricing before quoting the cost numbers; change them here only.
PRICE_IN = float(os.getenv("PRICE_IN_PER_M", "0.15"))
PRICE_OUT = float(os.getenv("PRICE_OUT_PER_M", "0.60"))

_client = None


def client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url=BASE_URL, max_retries=0)
    return _client


def cost(prompt_tokens, completion_tokens):
    return (prompt_tokens * PRICE_IN + completion_tokens * PRICE_OUT) / 1_000_000


def retry_after(exc, fallback):
    """Seconds Groq asked us to wait, from the retry-after header or the message."""
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    value = headers.get("retry-after") or ""
    if not value:
        found = re.search(r"try again in ((?:\d+m)?[\d.]+s)", str(exc))
        value = found.group(1) if found else ""
    parsed = re.fullmatch(r"(?:(\d+)m)?([\d.]+)s?", value.strip()) if value else None
    if parsed:
        return min(900, int(parsed.group(1) or 0) * 60 + float(parsed.group(2)) + 1)
    return fallback


def chat(messages, tools=None, max_completion_tokens=4096, timeout=60, retries=10):
    """One chat completion. Returns (message, usage) where usage carries the
    tokens, cost, the seconds spent in the call itself and the seconds spent
    waiting out rate limits.

    Rate-limit backoff is reported separately and kept out of latency: it measures
    the provider's quota, not either system. Any other error stops the run."""
    kwargs = {"model": MODEL, "messages": messages, "temperature": TEMPERATURE,
              "max_completion_tokens": max_completion_tokens, "timeout": timeout}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    waited = 0.0
    for attempt in range(retries):
        started = time.perf_counter()
        try:
            resp = client().chat.completions.create(**kwargs)
        except RateLimitError as exc:
            wait = retry_after(exc, fallback=min(60, 5 * (attempt + 1)))
            print("    rate limited, waiting %.0fs" % wait, flush=True)
            time.sleep(wait)
            waited += wait
            continue
        except APIConnectionError as exc:
            # a dropped TLS handshake, seen once on this machine; retried, not hidden
            print("    connection error (%s), retrying" % exc.__cause__, flush=True)
            waited += time.perf_counter() - started
            continue
        call_s = time.perf_counter() - started
        u = resp.usage
        usage = {
            "prompt_tokens": u.prompt_tokens,
            "completion_tokens": u.completion_tokens,
            "total_tokens": u.prompt_tokens + u.completion_tokens,
            "cost_usd": cost(u.prompt_tokens, u.completion_tokens),
            "call_s": call_s,
            "wait_s": waited,
            "finish_reason": resp.choices[0].finish_reason,
        }
        return resp.choices[0].message, usage
    raise RuntimeError("still rate limited after %d attempts" % retries)
