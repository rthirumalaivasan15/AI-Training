"""Mechanical checks, no model calls. The model is replaced by a stub that asks
for a tool on every lap and never answers - the worst case, a loop that would
spin forever - and each of the four budgets must be the one that stops it.

    python selftest.py
"""
import ast
import sys
import json
from types import SimpleNamespace

import agent
import contract
from tools import compute_payout, TOOLS

failures = []


def check(name, ok, detail=""):
    print("  %-4s %s%s" % ("ok" if ok else "FAIL", name, ("  - " + detail) if detail and not ok else ""))
    if not ok:
        failures.append(name)


def spinning_chat(tokens_per_lap=1000, cost_per_lap=0.001, seconds_per_lap=1.0, clock=None):
    """A model that calls get_claim forever. Advances the fake clock per lap."""
    def chat(messages, tools=None, max_completion_tokens=None, timeout=None):
        if clock is not None:
            clock["t"] += seconds_per_lap
        call = SimpleNamespace(id="call_%d" % len(messages), function=SimpleNamespace(
            name="get_claim", arguments=json.dumps({"claim_id": "CLM-2024-10001"})))
        msg = SimpleNamespace(content="", tool_calls=[call])
        return msg, {"prompt_tokens": tokens_per_lap - 50, "completion_tokens": 50,
                     "total_tokens": tokens_per_lap, "cost_usd": cost_per_lap,
                     "call_s": seconds_per_lap, "wait_s": 0.0, "finish_reason": "tool_calls"}
    return chat


def run_until_stop(budget_kwargs, chat_kwargs):
    clock = {"t": 0.0}
    budget = agent.Budget(clock=lambda: clock["t"], **budget_kwargs)
    result = agent.run("CLM-2024-10001", budget, log=lambda line: None,
                       chat=spinning_chat(clock=clock, **chat_kwargs))
    return result


print("budgets")
roomy = {"max_iters": 1000, "max_tokens": 10**9, "max_cost": 10**6, "max_wall": 10**6}
cases = {
    "max_iters":  ({**roomy, "max_iters": 5}, {}),
    "max_tokens": ({**roomy, "max_tokens": 7_500}, {"tokens_per_lap": 1000}),
    "max_cost":   ({**roomy, "max_cost": 0.0045}, {"cost_per_lap": 0.001}),
    "max_wall":   ({**roomy, "max_wall": 12}, {"seconds_per_lap": 5.0}),
}
for expected, (limits, chat_kwargs) in cases.items():
    r = run_until_stop(limits, chat_kwargs)
    check("%s stops the spinning loop" % expected, r["stop_reason"] == expected,
          "stopped by %s after %d laps" % (r["stop_reason"], r["laps"]))
    check("%s termination returns a valid UNDETERMINED answer" % expected,
          r["output"] is not None and r["output"]["coverage_position"] == "UNDETERMINED")
    check("%s tokens are summed over every lap" % expected,
          r["tokens"] == r["laps"] * chat_kwargs.get("tokens_per_lap", 1000))

print("compute_payout")
check("covered, capped by limit", compute_payout("covered", 14200, 1000, 10000) == {"payable_amount": 9000})
check("covered, no limit", compute_payout("covered", 8400, 1000) == {"payable_amount": 7400})
check("denied pays zero", compute_payout("denied", 8400, 1000) == {"payable_amount": 0})
check("undetermined pays null", compute_payout("undetermined", 8400, 1000) == {"payable_amount": None})
check("never below zero", compute_payout("covered", 300, 500) == {"payable_amount": 0})
check("status outside the enum is refused", "error" in compute_payout("partial", 100, 0))
schema = next(t for t in TOOLS if t["function"]["name"] == "compute_payout")["function"]["parameters"]
check("claim_status is an enum in the schema", schema["properties"]["claim_status"].get("enum") == ["covered", "denied", "undetermined"])

print("contract")
good = {"claim_id": "X", "coverage_position": "DENIED", "grounds": ["E-18"], "payable_amount": 0,
        "reasoning": "r", "next_step": "n"}
check("grade passes a correct answer", contract.grade(good, {"coverage_position": "DENIED", "payable_amount": 0, "must_cite": ["E-18"]})[0])
check("grade fails a wrong payable", not contract.grade(good, {"coverage_position": "DENIED", "payable_amount": 5, "must_cite": []})[0])
check("grade fails a missing citation", not contract.grade(good, {"coverage_position": "DENIED", "payable_amount": 0, "must_cite": ["E-17"]})[0])
check("parse rejects a bad position", contract.parse(json.dumps({**good, "coverage_position": "PARTIAL"}))[0] is None)

print("workflow")
tree = ast.parse(open("workflow.py", encoding="utf-8").read())
loops = [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While, ast.AsyncFor))]
check("workflow.py contains no for or while loop", not loops,
      "loops at lines %s" % [n.lineno for n in loops])
tool_calls = sorted({n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id in ("get_claim", "search_policy", "compute_payout")})
check("workflow.py calls the same three tools", tool_calls == ["compute_payout", "get_claim", "search_policy"])

print("\n%d failed" % len(failures) if failures else "\nall checks passed")
sys.exit(1 if failures else 0)
