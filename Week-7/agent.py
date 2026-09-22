"""The claims triage agent: the model decides which tool to call next, until it
returns the contract JSON or a budget stops it.

    python agent.py CLM-2024-10001
    python agent.py CLM-2024-10006 --max-tokens 6000 --log runs/budget_termination.log

Four budgets are checked before every lap, and two of them are also pushed down
into the call itself (completion tokens and request timeout), so a single lap
cannot overshoot by much. When one fires the run stops, logs which budget fired,
and returns a well-formed UNDETERMINED answer referring the claim to a person.
"""
import sys
import json
import time
import argparse

import llm
import contract
from tools import TOOLS, run_tool

MAX_ITERS = 8          # laps (model calls)
MAX_TOKENS = 60_000    # prompt + completion, summed over every lap
MAX_COST_USD = 0.02    # summed over every lap
MAX_WALL_S = 90        # seconds of active time; rate-limit backoff excluded, see llm.chat
MIN_COMPLETION = 512   # a lap with less completion room than this cannot finish usefully

SYSTEM = """You triage insurance claims for a claims adjuster.

For the claim number you are given: pull the claim, read the adjuster notes, check the endorsement wording for every exclusion, exception, limit or duty the facts in the notes bring into play, and work out the payable amount after the excess.

Rules:
- Rely only on what the tools return. You have no other knowledge of the policy wording.
- The notes decide which wording matters. If a note reveals a new fact (a cause, a duration, a vacancy, a business use), search the wording for it before deciding.
- If the notes do not establish the facts an exclusion or exception turns on, the position is UNDETERMINED. Never guess.
- Take payable_amount from compute_payout. Do not do the arithmetic yourself.

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


def assistant_turn(msg):
    """The assistant message as it must be re-sent on the next lap."""
    turn = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        turn["tool_calls"] = [{"id": c.id, "type": "function",
                               "function": {"name": c.function.name, "arguments": c.function.arguments}}
                              for c in msg.tool_calls]
    return turn


def stopped_output(claim_id, fired):
    return {"claim_id": claim_id, "coverage_position": "UNDETERMINED", "grounds": [],
            "payable_amount": None,
            "reasoning": "Triage stopped before a decision: the %s budget was reached." % fired,
            "next_step": "Refer the claim to an adjuster for manual triage."}


def run(claim_id, budget=None, log=print, chat=llm.chat):
    budget = budget or Budget()
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Triage claim %s." % claim_id}]
    calls = []
    log("START %s  limits %s" % (claim_id, json.dumps(budget.limits)))

    while True:
        fired = budget.exceeded()
        if fired:
            log("STOP  budget=%s fired  used=%s  limit=%s"
                % (fired, budget.used()[fired], budget.limits[fired]))
            log("      used %s" % json.dumps(budget.used()))
            return finish(claim_id, stopped_output(claim_id, fired), None, fired, budget, calls)

        msg, usage = chat(messages, tools=TOOLS, **budget.call_caps())
        budget.charge(usage)
        messages.append(assistant_turn(msg))
        log("lap %d  +%d tok (%d in / %d out)  total %d tok  $%.5f  %.1fs  finish=%s"
            % (budget.laps, usage["total_tokens"], usage["prompt_tokens"],
               usage["completion_tokens"], budget.tokens, budget.cost,
               budget.elapsed(), usage["finish_reason"]))

        if not msg.tool_calls:
            if usage["finish_reason"] == "length":
                # cut off by the completion cap - not an answer, spend nothing more on it
                log("      reply cut off at the completion-token cap")
                continue
            output, error = contract.parse(msg.content)
            log("DONE  final answer%s" % ("" if output else "  INVALID: " + error))
            return finish(claim_id, output, error, None, budget, calls)

        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args, result = {}, {"error": "arguments were not valid JSON"}
            else:
                result = run_tool(call.function.name, args)
            calls.append({"tool": call.function.name, "args": args})
            log("      -> %s(%s)" % (call.function.name, json.dumps(args)))
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result, ensure_ascii=False)})


def finish(claim_id, output, error, stop_reason, budget, calls):
    return {"claim_id": claim_id, "output": output, "error": error,
            "stop_reason": stop_reason, "laps": budget.laps, "tokens": budget.tokens,
            "cost_usd": budget.cost, "latency_s": budget.elapsed(),
            "rate_limit_wait_s": budget.waited, "tool_calls": calls}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("claim_id")
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

    result = run(a.claim_id, Budget(a.max_iters, a.max_tokens, a.max_cost, a.max_wall), log)
    log("OUTPUT %s" % json.dumps(result["output"]))
    if sink:
        sink.close()
