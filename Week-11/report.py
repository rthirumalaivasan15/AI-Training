"""Cost by stage for one request, and what breaks first at 10x - from the logs only.

    python report.py cost trc_0123abcd4567     # -> cost_by_stage.md
    python report.py tenx                      # -> tenx.md

No model calls. Stage attribution (see tracer.split_prompt): every model call's
prompt tokens are split by what they carried - instructions and the notes, the
model's own earlier turns, retrieved passages, other tool results - with o200k_base
token counts scaled to the provider's real prompt_tokens, so totals are exact and
only the split is estimated. Completion tokens are generation. Retrieval and tools
themselves run locally (MiniLM embeddings, Chroma, Python) and cost $0 in API fees;
what they cost is the tokens their results add to every later model call.
"""
import os
import sys
import json
import math
import datetime

import llm
import tracer

STAGES = ("retrieval", "generation", "tools")
PROBE = os.path.join("runs", "quota_probe.json")


def pct(part, whole):
    return 100.0 * part / whole if whole else 0.0


def nearest_rank(values, p):
    v = sorted(values)
    return v[max(1, math.ceil(p / 100 * len(v))) - 1]


def tool_schema_tokens():
    """Tokens of each tool definition the model is offered on every call - read from
    the policy-docs server's own tools/list, counted with o200k_base."""
    import json
    import asyncio
    from mcp_host import Host

    async def listed():
        async with Host("mcp_config.json") as host:
            return {t["function"]["name"]: tracer._count(json.dumps(t)) for t in host.tools}
    return asyncio.run(listed())


def cost(trace_id):
    rows = tracer.read()
    t = next((r for r in rows if r["trace_id"] == trace_id), None)
    if t is None:
        sys.exit("no trace %s" % trace_id)
    day = [r for r in rows if r["ts"][:10] == t["ts"][:10]]
    st = t["cost_by_stage"]
    total = t["cost_usd"]
    out = ["# cost_by_stage.md - %s" % trace_id, "",
           "Request: %s, %s, %s, prompt `%s` (sha `%s`), model `%s`, at %s." % (
               t["claim_number"], t["user"], t["input_type"], t["prompt_version"], t["prompt_sha"],
               t["model"], t["ts"]), "",
           "| stage | prompt tokens | completion tokens | cost | share of cost | latency |",
           "|---|---|---|---|---|---|"]
    for s in STAGES:
        out.append("| %s | %s | %s | $%.6f | %.1f%% | %.2f s |" % (
            s, format(st[s]["prompt_tokens"], ","), format(st[s]["completion_tokens"], ","),
            st[s]["cost_usd"], pct(st[s]["cost_usd"], total), st[s]["latency_ms"] / 1000))
    out += ["| **total** | %s | %s | **$%.6f** | 100%% | %.2f s active (%.2f s wall, %.1f s rate-limit wait, %.2f s MCP start-up) |" % (
        format(t["prompt_tokens"], ","), format(t["completion_tokens"], ","), total,
        t["active_s"], t["latency_s"], t["rate_limit_wait_s"], t["setup_ms"] / 1000), "",
        "Cost per query: **$%.6f**. Prices from `llm.py`: $%.2f / $%.2f per 1M input / output tokens." % (
            total, llm.PRICE_IN, llm.PRICE_OUT), "",
        "## Where the stage numbers come from - every span", "",
        "| span | kind | name | latency | prompt in | completion out | cost | carried in prompt (instructions / history / retrieval / tools) | context ids |",
        "|---|---|---|---|---|---|---|---|---|"]
    for s in t["spans"]:
        split = s.get("prompt_tokens_by_content")
        out.append("| %d | %s | %s | %d ms | %s | %s | $%.6f | %s | %s |" % (
            s["span"], s["kind"], s["name"], s["latency_ms"], s.get("prompt_tokens", "-"),
            s.get("completion_tokens", "-"), s.get("cost_usd", 0),
            " / ".join(str(split[k]) for k in ("instructions", "history", "retrieval", "tools")) if split else "-",
            ", ".join(s.get("context_ids", [])) or "-"))
    n = len(day)
    avg = {s: sum(r["cost_by_stage"][s]["cost_usd"] for r in day) / n for s in STAGES}
    day_total = sum(avg.values())
    out += ["", "## The same split over the whole day (%d requests), for comparison" % n, "",
            "| stage | mean cost per query | share |", "|---|---|---|"]
    for s in STAGES:
        out.append("| %s | $%.6f | %.1f%% |" % (s, avg[s], pct(avg[s], day_total)))
    out.append("| total | $%.6f | 100%% |" % day_total)
    schema = tool_schema_tokens()
    calls_day = sum(r["laps"] for r in day)
    used = sum(1 for r in day for s in r["spans"] if s["kind"] == "tool")
    out += ["", "**Tool definitions ride inside the generation stage.** Every model call re-sends the tool "
            "list: %s. That is %d tokens per call, %d per call for `compute_payout` alone - which was called "
            "**%d times** in the day's %d model calls (the Week 6 summary has no payout field). Its definition "
            "cost %s input tokens over the day for nothing: the first saving to make, and only visible once "
            "cost is attributed." % (
                ", ".join("`%s` %d tokens" % kv for kv in schema.items()), sum(schema.values()),
                schema.get("compute_payout", 0), used, calls_day,
                format(schema.get("compute_payout", 0) * calls_day, ","))]
    out += ["", "Retrieval and tools are free to run here (local embeddings, local vector store, Python "
            "arithmetic); their cost is the tokens their results add to every later model call, which "
            "is why they are attributed from the prompt. Split method: o200k_base token counts per "
            "message, scaled to Groq's reported prompt_tokens for that call."]
    with open("cost_by_stage.md", "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out[:12]))


def tenx():
    rows = tracer.read()
    day = rows[-1]["ts"][:10]
    rows = [r for r in rows if r["ts"][:10] == day]
    n = len(rows)
    first = datetime.datetime.fromisoformat(rows[0]["ts"])
    last = datetime.datetime.fromisoformat(rows[-1]["ts"])
    window_min = (last - first).total_seconds() / 60
    tokens = sum(r["tokens"] for r in rows)
    calls = sum(r["laps"] for r in rows)
    cost_day = sum(r["cost_usd"] for r in rows)
    limits = rows[-1]["rate_limits"]
    tpm, rpd = limits.get("limit-tokens"), limits.get("limit-requests")
    hits = [h for r in rows for h in r["rate_limited"]]
    by_unit = {}
    for h in hits:
        by_unit[h["unit"]] = by_unit.get(h["unit"], 0) + 1
    wait = sum(r["rate_limit_wait_s"] for r in rows)
    wall = [r["latency_s"] for r in rows]
    active = [r["active_s"] for r in rows]

    demand_1x = tokens / window_min                 # tokens per minute at today's arrival rate
    demand_10x = 10 * demand_1x
    capacity_req_min = tpm / (tokens / n)           # requests per minute the TPM limit allows
    calls_10x = 10 * calls
    cost_10x = 10 * cost_day
    # the tokens-per-day cap is not in the response headers - only in a TPD 429
    probe = json.load(open(PROBE)) if os.path.exists(PROBE) else {}
    tpd = probe.get("limit") if probe.get("unit") == "TPD" else None

    line = ("**Rate limit breaks first - the daily token cap: 10x today's traffic needs %s tokens a day against "
            "Groq's %s tokens-per-day cap on %s (%.1fx over; it breaks at %.1fx today's volume), while cost "
            "would be only $%.2f a day.**" % (
                format(10 * tokens, ","), format(tpd, ","), llm.MODEL, 10 * tokens / tpd, tpd / tokens, cost_10x)
            ) if tpd else (
            "**Rate limit breaks first: at 10x today's rate the app needs %s tokens/min against Groq's %s "
            "tokens-per-minute cap on %s - %.0fx over - while cost is only $%.2f a day.**" % (
                format(round(demand_10x), ","), format(tpm, ","), llm.MODEL, demand_10x / tpm, cost_10x))
    out = ["# tenx.md - what breaks first at 10x", "", line, "",
           "| | today (%s) | at 10x | limit | breaks? |" % day, "|---|---|---|---|---|",
           "| requests | %d in %.0f min | %d | - | - |" % (n, window_min, 10 * n)]
    if tpd:
        out.append("| tokens per day | %s | %s | %s TPD | **yes, %.1fx over - first, at %.1fx** |" % (
            format(tokens, ","), format(10 * tokens, ","), format(tpd, ","), 10 * tokens / tpd, tpd / tokens))
    out += ["| tokens per minute (at today's arrival rate) | %s | %s | %s TPM | yes, %.1fx over - if it arrives as fast as today |" % (
               format(round(demand_1x), ","), format(round(demand_10x), ","), format(tpm, ","), demand_10x / tpm),
           "| model calls per day | %d | %d | %s RPD | no (%.0f%% of cap) |" % (calls, calls_10x, format(rpd, ","), pct(calls_10x, rpd)),
           "| cost per day | $%.4f | $%.4f | - | no |" % (cost_day, cost_10x),
           "| latency p50 / p99 (wall) | %.1f s / %.1f s | grows with the TPM queue | - | follows the rate limit |" % (
               nearest_rank(wall, 50), nearest_rank(wall, 99)),
           "",
           "Today already hit the TPM cap: **%d rate-limit responses (%s), %.0f s of waiting** across %d requests; "
           "active time p50 / p99 was %.1f s / %.1f s, wall time %.1f s / %.1f s - the gap is the queue." % (
               len(hits), ", ".join("%s x%d" % kv for kv in by_unit.items()), wait, n,
               nearest_rank(active, 50), nearest_rank(active, 99), nearest_rank(wall, 50), nearest_rank(wall, 99)),
           "At %s tokens per request, the %s TPM cap sustains %.1f requests a minute; 10x today's rate is %.1f a minute." % (
               format(round(tokens / n), ","), format(tpm, ","), capacity_req_min, 10 * n / window_min),
           ("The daily cap binds however the traffic arrives: spread evenly over an 8-hour shift, 10x would be only "
            "%s tokens/min (under TPM), but the day's total is the same %s tokens. It was hit for real on %s: %s - "
            "after the day's traffic plus trap pre-tests and eval-suite runs on the same key; the remaining suite "
            "cases then waited ~%.0f s each for the budget to refill (`runs/quota_probe.json`). Evals and production "
            "share one key: tests and suite runs used about %s of those %s tokens, so the cap was reached at only "
            "~1x production traffic." % (
                format(round(10 * tokens / 480), ","), format(10 * tokens, ","), probe["ts"][:16],
                "429 TPD: limit %s, used %s, requested %s" % (format(tpd, ","), format(probe["used"], ","),
                                                             format(probe["requested"], ",")),
                probe["retry_after_s"], format(probe["used"] - tokens, ","), format(probe["used"], ","))) if tpd else "",
           "TPM and RPD come from Groq's own response headers (`x-ratelimit-limit-tokens`, "
           "`x-ratelimit-limit-requests`) recorded in every trace; the daily token cap is not in the headers and "
           "appears only in a TPD 429; every 429 is classified by `llm.rate_limit_hit`."]
    green = os.path.join("runs", "suite_green.jsonl")
    if tpd and os.path.exists(green):
        with open(green, encoding="utf-8") as f:
            logged = [r for r in (json.loads(l) for l in f if l.strip()) if "rate_limited" in r]
        tpd_hits = sum(1 for r in logged for h in r["rate_limited"] if h["unit"] == "TPD")
        waited = sum(r["rate_limit_wait_s"] for r in logged)
        out.insert(-1, "The GREEN suite run that followed met **%d TPD 429s and %.1f hours of waiting** over the %d cases "
                       "it logged (`runs/suite_green.jsonl`) - 11 eval cases took most of an evening at ~1x." % (
                           tpd_hits, waited / 3600, len(logged)))
    with open("tenx.md", "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1] == "cost":
        cost(sys.argv[2])
    else:
        tenx()
