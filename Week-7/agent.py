"""The claims triage agent: the model decides which tool to call next, until it
returns the contract JSON.

    python agent.py CLM-2024-10001
"""
import sys
import json
import time

import llm
import contract
from tools import TOOLS, run_tool

MAX_ITERS = 8

SYSTEM = """You triage insurance claims for a claims adjuster.

For the claim number you are given: pull the claim, read the adjuster notes, check the endorsement wording for every exclusion, exception, limit or duty the facts in the notes bring into play, and work out the payable amount after the excess.

Rules:
- Rely only on what the tools return. You have no other knowledge of the policy wording.
- The notes decide which wording matters. If a note reveals a new fact (a cause, a duration, a vacancy, a business use), search the wording for it before deciding.
- If the notes do not establish the facts an exclusion or exception turns on, the position is UNDETERMINED. Never guess.

""" + contract.CONTRACT_TEXT


def assistant_turn(msg):
    """The assistant message as it must be re-sent on the next lap."""
    turn = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        turn["tool_calls"] = [{"id": c.id, "type": "function",
                               "function": {"name": c.function.name, "arguments": c.function.arguments}}
                              for c in msg.tool_calls]
    return turn


def run(claim_id, log=print):
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": "Triage claim %s." % claim_id}]
    started = time.perf_counter()
    for lap in range(1, MAX_ITERS + 1):
        msg, usage = llm.chat(messages, tools=TOOLS)
        messages.append(assistant_turn(msg))
        if not msg.tool_calls:
            output, error = contract.parse(msg.content)
            log("lap %d  final answer%s" % (lap, "" if output else "  INVALID: " + error))
            return {"output": output, "error": error, "laps": lap,
                    "elapsed_s": time.perf_counter() - started}
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            result = run_tool(call.function.name, args)
            log("lap %d  %s(%s)" % (lap, call.function.name, json.dumps(args)))
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result, ensure_ascii=False)})
    log("stopped after %d laps without an answer" % MAX_ITERS)
    return {"output": None, "error": "max iterations", "laps": MAX_ITERS,
            "elapsed_s": time.perf_counter() - started}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    result = run(sys.argv[1])
    print(json.dumps(result["output"], indent=2))
