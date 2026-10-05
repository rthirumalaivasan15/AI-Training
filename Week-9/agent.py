"""The claims triage agent, Week 9: the Week 8 loop with its tools moved behind MCP.

    python agent.py CLM-2024-10004
    python agent.py CLM-2024-10004 --config mcp_config.json --log runs/trace.log

The agent holds no tool list of its own. At start-up the host (mcp_host.py)
starts every server in the MCP config and asks each one tools/list; whatever
comes back is what the model is offered, and every call is routed to the server
that listed it. Adding a server is a config change - this module does not move.

The model call happens here, in run() via llm.chat - never in a server.

Four budgets are checked before every lap, as in Weeks 7 and 8. When one fires
the run stops and returns a well-formed UNDETERMINED answer.
"""
import sys
import json
import time
import asyncio
import argparse

import llm
import contract
from mcp_host import Host

CONFIG = "mcp_config.json"

MAX_ITERS = 8          # laps (model calls)
MAX_TOKENS = 60_000    # prompt + completion, summed over every lap
MAX_COST_USD = 0.02    # summed over every lap
MAX_WALL_S = 90        # seconds of active time; rate-limit backoff excluded, see llm.chat
MIN_COMPLETION = 512   # a lap with less completion room than this cannot finish usefully

SYSTEM = """You triage insurance claims for a claims adjuster.

For the claim number you are given: pull the claim, read the adjuster notes, check the endorsement wording for every exclusion, exception, limit or duty the facts in the notes bring into play, and work out the payable amount after the excess.

Rules:
- Rely only on what the tools return. You have no other knowledge of the claim or the policy wording.
- The notes decide which wording matters. If a note reveals a new fact (a cause, a duration, a vacancy, a business use), search the wording for it before deciding.
- If the notes do not establish the facts an exclusion or exception turns on, the position is UNDETERMINED. Never guess.
- If no tool can give you the claim itself, the position is UNDETERMINED.
- Take payable_amount from the payout tool. Do not do the arithmetic yourself.

""" + contract.CONTRACT_TEXT


class Budget:
    def __init__(self, max_iters=MAX_ITERS, max_tokens=MAX_TOKENS,
                 max_cost=MAX_COST_USD, max_wall=MAX_WALL_S, clock=time.perf_counter):
        self.limits = {"max_iters": max_iters, "max_tokens": max_tokens,
                       "max_cost": max_cost, "max_wall": max_wall}
        self.clock = clock
        self.started = clock()
        self.waited = 0.0
        self.laps = 0
        self.tokens = 0
        self.cost = 0.0
        self.estimated_laps = 0

    def elapsed(self):
        return self.clock() - self.started - self.waited

    def used(self):
        return {"max_iters": self.laps, "max_tokens": self.tokens,
                "max_cost": round(self.cost, 6), "max_wall": round(self.elapsed(), 2)}

    def exceeded(self):
        """Name of the first budget that is spent, or None. Checked before every lap."""
        if self.laps >= self.limits["max_iters"]:
            return "max_iters"
        if self.tokens >= self.limits["max_tokens"]:
            return "max_tokens"
        if self.limits["max_tokens"] - self.tokens < MIN_COMPLETION:
            return "max_tokens"
        if self.cost >= self.limits["max_cost"]:
            return "max_cost"
        if self.elapsed() >= self.limits["max_wall"]:
            return "max_wall"
        return None

    def call_caps(self):
        """What is left, pushed down into the next call."""
        return {"max_completion_tokens": int(min(4096, self.limits["max_tokens"] - self.tokens)),
                "timeout": max(1.0, self.limits["max_wall"] - self.elapsed())}

    def charge(self, usage):
        self.laps += 1
        self.tokens += usage["total_tokens"]
        self.cost += usage["cost_usd"]
        self.waited += usage["wait_s"]
        self.estimated_laps += 1 if usage.get("estimated") else 0


def assistant_turn(msg):
    """The assistant message as it must be re-sent on the next lap."""
    turn = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        turn["tool_calls"] = [{"id": c.id, "type": "function",
                               "function": {"name": c.function.name, "arguments": c.function.arguments}}
                              for c in msg.tool_calls]
    return turn


def rejected_answer(generation):
    """The contract answer inside a refused tool call, if that is what it carried."""
    try:
        call = json.loads(generation)
        args = call.get("arguments", call)
        args = json.loads(args) if isinstance(args, str) else args
    except (json.JSONDecodeError, AttributeError):
        return None
    output, _ = contract.validate(args) if isinstance(args, dict) else (None, None)
    return output


def stopped_output(claim_id, fired):
    return {"claim_id": claim_id, "coverage_position": "UNDETERMINED", "grounds": [],
            "payable_amount": None,
            "reasoning": "Triage stopped before a decision: the %s budget was reached." % fired,
            "next_step": "Refer the claim to an adjuster for manual triage."}


async def run(claim_id, host, budget=None, log=print, chat=llm.chat):
    budget = budget or Budget()
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Triage claim %s." % claim_id}]
    calls = []
    log("START %s  limits %s" % (claim_id, json.dumps(budget.limits)))
    log("      offered %d tools: %s" % (len(host.tools), ", ".join(
        "%s@%s" % (t["function"]["name"], host.routes[t["function"]["name"]]) for t in host.tools)))

    while True:
        fired = budget.exceeded()
        if fired:
            log("STOP  budget=%s fired  used=%s  limit=%s"
                % (fired, budget.used()[fired], budget.limits[fired]))
            log("      used %s" % json.dumps(budget.used()))
            return finish(claim_id, stopped_output(claim_id, fired), None, fired, budget, calls, messages)

        msg, usage = chat(messages, tools=host.tools, **budget.call_caps())
        budget.charge(usage)
        messages.append(assistant_turn(msg))
        log("lap %d  +%d tok (%d in / %d out)  total %d tok  $%.5f  %.1fs  finish=%s"
            % (budget.laps, usage["total_tokens"], usage["prompt_tokens"],
               usage["completion_tokens"], budget.tokens, budget.cost,
               budget.elapsed(), usage["finish_reason"]))

        if usage["finish_reason"] == "tool_use_failed":
            output = rejected_answer(msg.rejected)
            if output:
                log("      provider refused a call to an undeclared tool; its arguments are a valid "
                    "answer, accepted (usage estimated)")
                log("DONE  final answer")
                return finish(claim_id, output, None, None, budget, calls, messages)
            log("      provider refused an invalid tool call (usage estimated): %s" % msg.rejected[:200])
            messages.append({"role": "user", "content":
                             "Your last reply called a tool that does not exist. Call one of the "
                             "declared tools, or reply with the JSON object as plain text."})
            continue

        if not msg.tool_calls:
            if usage["finish_reason"] == "length":
                log("      reply cut off at the completion-token cap")
                continue
            output, error = contract.parse(msg.content)
            log("DONE  final answer%s" % ("" if output else "  INVALID: " + error))
            return finish(claim_id, output, error, None, budget, calls, messages)

        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args, result, server = {}, {"error": "arguments were not valid JSON"}, None
            else:
                result, server = await host.call(call.function.name, args)
            failed = isinstance(result, dict) and "error" in result
            calls.append({"tool": call.function.name, "server": server, "args": args,
                          "error": result["error"] if failed else None})
            log("      -> %s(%s)  [server: %s]%s" % (call.function.name, json.dumps(args), server,
                                                     "  ERROR: " + result["error"] if failed else ""))
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result, ensure_ascii=False)})


def finish(claim_id, output, error, stop_reason, budget, calls, messages):
    return {"claim_id": claim_id, "output": output, "error": error,
            "stop_reason": stop_reason, "laps": budget.laps, "tokens": budget.tokens,
            "cost_usd": budget.cost, "latency_s": budget.elapsed(),
            "rate_limit_wait_s": budget.waited, "estimated_laps": budget.estimated_laps,
            "tool_calls": calls, "messages": messages}


async def main(a, log):
    async with Host(a.config, log) as host:
        budget = Budget(a.max_iters, a.max_tokens, a.max_cost, a.max_wall)
        return await run(a.claim_id, host, budget, log)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("claim_id")
    p.add_argument("--config", default=CONFIG)
    p.add_argument("--max-iters", type=int, default=MAX_ITERS)
    p.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    p.add_argument("--max-cost", type=float, default=MAX_COST_USD)
    p.add_argument("--max-wall", type=float, default=MAX_WALL_S)
    p.add_argument("--log", help="also write the run log to this file")
    a = p.parse_args()

    sink = open(a.log, "w", encoding="utf-8") if a.log else None

    def log(line):
        stamped = "%s  %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), line)
        print(stamped, flush=True)
        if sink:
            sink.write(stamped + "\n")

    result = asyncio.run(main(a, log))
    log("OUTPUT %s" % json.dumps(result["output"]))
    if sink:
        sink.close()
