"""Arm 1: the single agent - the Week 9 agent loop, one model, every tool.

    python single_agent.py C02

Same loop, budgets, model and MCP host as Week 9. Two things moved, both forced by
the race: the input is a Week 6 case's adjuster notes rather than a claim number
(the Week 6 cases are not in the claims system), and the final answer is the
Week 6 claim summary, because that is what the Week 6 judge reads. The agent is
offered every tool the policy-docs server lists.
"""
import sys
import json
import time
import asyncio

import llm
import cases
import summary_format
from mcp_host import Host

CONFIG = "mcp_config.json"

MAX_ITERS = 8          # laps (model calls)
MAX_TOKENS = 60_000    # prompt + completion, summed over every lap
MAX_COST_USD = 0.02
MAX_WALL_S = 90        # active seconds; rate-limit backoff excluded, see llm.chat
MIN_COMPLETION = 512

SYSTEM = """You write a claim summary for an insurance claims adjuster from their file notes.

Before you take a position, search the endorsement wording for every exclusion, exception, definition, limit or duty the facts in the notes bring into play. The notes decide which wording matters: if a note reveals a cause, a duration, a vacancy, a business use or a missed duty, search the wording for it.

When you are done, reply with the summary and nothing else.

""" + summary_format.OUTPUT_SPEC + "\n\n" + summary_format.RULES


class Budget:
    def __init__(self, max_iters=MAX_ITERS, max_tokens=MAX_TOKENS,
                 max_cost=MAX_COST_USD, max_wall=MAX_WALL_S, clock=time.perf_counter):
        self.limits = {"max_iters": max_iters, "max_tokens": max_tokens,
                       "max_cost": max_cost, "max_wall": max_wall}
        self.clock = clock
        self.started = clock()
        self.waited = 0.0
        self.laps = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.tokens = 0
        self.cost = 0.0

    def elapsed(self):
        return self.clock() - self.started - self.waited

    def exceeded(self):
        if self.laps >= self.limits["max_iters"]:
            return "max_iters"
        if self.limits["max_tokens"] - self.tokens < MIN_COMPLETION:
            return "max_tokens"
        if self.cost >= self.limits["max_cost"]:
            return "max_cost"
        if self.elapsed() >= self.limits["max_wall"]:
            return "max_wall"
        return None

    def call_caps(self):
        return {"max_completion_tokens": int(min(4096, self.limits["max_tokens"] - self.tokens)),
                "timeout": max(1.0, self.limits["max_wall"] - self.elapsed())}

    def charge(self, usage):
        self.laps += 1
        self.prompt_tokens += usage["prompt_tokens"]
        self.completion_tokens += usage["completion_tokens"]
        self.tokens += usage["total_tokens"]
        self.cost += usage["cost_usd"]
        self.waited += usage["wait_s"]


def assistant_turn(msg):
    turn = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        turn["tool_calls"] = [{"id": c.id, "type": "function",
                               "function": {"name": c.function.name, "arguments": c.function.arguments}}
                              for c in msg.tool_calls]
    return turn


async def run(case, host, budget=None, log=print, chat=llm.chat):
    budget = budget or Budget()
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Adjuster notes:\n%s" % case["notes"]}]
    laps, summary, stop = [], None, None
    log("START single %s  tools: %s" % (case["id"], ", ".join(t["function"]["name"] for t in host.tools)))

    while True:
        stop = budget.exceeded()
        if stop:
            log("STOP  budget=%s" % stop)
            break
        msg, usage = chat(messages, tools=host.tools, **budget.call_caps())
        budget.charge(usage)
        messages.append(assistant_turn(msg))
        lap = {"lap": budget.laps, "prompt_tokens": usage["prompt_tokens"],
               "completion_tokens": usage["completion_tokens"], "call_s": round(usage["call_s"], 3),
               "wait_s": usage["wait_s"], "estimated": bool(usage.get("estimated")), "tools": []}
        laps.append(lap)
        log("lap %d  +%d tok (%d in / %d out)  %.1fs  finish=%s" % (
            budget.laps, usage["total_tokens"], usage["prompt_tokens"], usage["completion_tokens"],
            usage["call_s"], usage["finish_reason"]))

        if usage["finish_reason"] == "tool_use_failed":
            messages.append({"role": "user", "content":
                             "Your last reply called a tool that does not exist. Call one of the "
                             "declared tools, or reply with the summary as plain text."})
            continue
        if not msg.tool_calls:
            if usage["finish_reason"] == "length":
                continue
            summary = (msg.content or "").strip()
            break
        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args, result = {}, {"error": "arguments were not valid JSON"}
            else:
                result, _ = await host.call(call.function.name, args)
            lap["tools"].append({"tool": call.function.name, "args": args})
            log("      -> %s(%s)" % (call.function.name, json.dumps(args)))
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result, ensure_ascii=False)})

    log("DONE  position %s" % summary_format.position(summary))
    return {"id": case["id"], "arm": "single", "summary": summary, "stop_reason": stop,
            "calls": budget.laps, "prompt_tokens": budget.prompt_tokens,
            "completion_tokens": budget.completion_tokens, "tokens": budget.tokens,
            "cost_usd": budget.cost, "latency_s": budget.elapsed(),
            "rate_limit_wait_s": budget.waited, "laps": laps}


async def run_case(case, log=print):
    async with Host(CONFIG) as host:   # a fresh server per case, so no run sees another's evidence
        return await run(case, host, log=log)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    case = next(c for c in cases.load() if c["id"] == sys.argv[1])
    out = asyncio.run(run_case(case))
    print(out["summary"])
