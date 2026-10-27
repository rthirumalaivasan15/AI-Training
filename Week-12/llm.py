"""One model client for the claims app. Week 11 adds the quota: every response records
Groq's rate-limit headers, and every 429 records which limit it hit (TPM, RPD...).

Every call returns its own usage. Callers sum it themselves - the agent re-sends
the whole message list on every lap, so the only honest token count is the sum
over all laps, not the last call's number.
"""
import os
import re
import time
from dotenv import load_dotenv
import json
from types import SimpleNamespace
from openai import OpenAI, RateLimitError, APIConnectionError, BadRequestError

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


LIMIT_HEADERS = ("x-ratelimit-limit-requests", "x-ratelimit-remaining-requests",
                 "x-ratelimit-limit-tokens", "x-ratelimit-remaining-tokens")
LIMIT_HIT = re.compile(r"on (?P<kind>[a-z ]+?) \((?P<unit>[A-Z]+)\): Limit (?P<limit>\d+), "
                       r"Used (?P<used>\d+), Requested (?P<requested>\d+)")


def headers_limits(headers):
    """The quota Groq reports on every response, as numbers."""
    out = {}
    for name in LIMIT_HEADERS:
        value = headers.get(name)
        if value is not None and value.isdigit():
            out[name.replace("x-ratelimit-", "")] = int(value)
    return out


def rate_limit_hit(exc):
    """Which limit a 429 hit and how full it was. Only the parsed numbers are kept -
    the raw message also carries the organisation id, which does not belong in a log."""
    found = LIMIT_HIT.search(str(exc))
    if not found:
        return {"unit": "unknown"}
    return {"unit": found["unit"], "limit": int(found["limit"]), "used": int(found["used"]),
            "requested": int(found["requested"])}


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
    limited = []      # Week 11: every 429 this call hit - which limit, and how full it was
    for attempt in range(retries):
        started = time.perf_counter()
        try:
            raw = client().chat.completions.with_raw_response.create(**kwargs)
            resp = raw.parse()
        except RateLimitError as exc:
            wait = retry_after(exc, fallback=min(60, 5 * (attempt + 1)))
            limited.append({**rate_limit_hit(exc), "wait_s": round(wait, 1)})
            print("    rate limited, waiting %.0fs" % wait, flush=True)
            time.sleep(wait)
            waited += wait
            continue
        except BadRequestError as exc:
            body = getattr(exc, "body", None) or {}
            err = body.get("error", body) if isinstance(body, dict) else {}
            if err.get("code") != "tool_use_failed":
                raise
            # The model produced a tool call Groq refused to pass back (seen: a call to
            # an undeclared tool named "json" carrying the final answer). Groq reports
            # no usage for a refused call, so it is estimated at 4 characters a token
            # and flagged, rather than counted as free.
            generation = err.get("failed_generation") or ""
            prompt_est = len(json.dumps(messages)) // 4 + (len(json.dumps(tools)) // 4 if tools else 0)
            completion_est = len(generation) // 4
            usage = {
                "prompt_tokens": prompt_est,
                "completion_tokens": completion_est,
                "total_tokens": prompt_est + completion_est,
                "cost_usd": cost(prompt_est, completion_est),
                "call_s": time.perf_counter() - started,
                "wait_s": waited,
                "finish_reason": "tool_use_failed",
                "estimated": True,
                "rate_limits": {},
                "rate_limited": limited,
            }
            return SimpleNamespace(content=None, tool_calls=None, rejected=generation), usage
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
            "rate_limits": headers_limits(raw.headers),
            "rate_limited": limited,
        }
        return resp.choices[0].message, usage
    raise RuntimeError("still rate limited after %d attempts" % retries)
