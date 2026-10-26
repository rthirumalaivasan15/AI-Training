"""The claims app in production: adjuster notes in, a Week 6 claim summary out,
every request traced to logs/.

    python app.py --user adj-03 "CLM-2024-20011. DOL ... notes ..."

The loop is the Week 10 single agent (which beat the squad 8/10 vs 4/10): one
model, every tool the policy-docs MCP server lists, the same four budgets. What
Week 11 adds is the trace around it - see tracer.py.
"""
import sys
import json
import time
import asyncio
import argparse

import llm
import prompts
import assertions
from mcp_host import Host
from tracer import Trace, split_prompt

CONFIG = "mcp_config.json"
MAX_ITERS = 8
MAX_TOKENS = 60_000
MAX_COST_USD = 0.02
MAX_WALL_S = 90        # active seconds; rate-limit backoff excluded
MIN_COMPLETION = 512


def assistant_turn(msg):
    turn = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        turn["tool_calls"] = [{"id": c.id, "type": "function",
                               "function": {"name": c.function.name, "arguments": c.function.arguments}}
                              for c in msg.tool_calls]
    return turn


async def answer(notes, host, trace, version, log=print):
    """One request. Returns the summary text; every step lands in `trace`."""
    messages = [{"role": "system", "content": prompts.get(version)},
                {"role": "user", "content": "Adjuster notes:\n%s" % notes}]
    tool_names, tokens, cost, waited = {}, 0, 0.0, 0.0
    clock = time.perf_counter
    t0 = clock()

    for lap in range(1, MAX_ITERS + 1):
        if MAX_TOKENS - tokens < MIN_COMPLETION:
            return None, "max_tokens"
        if cost >= MAX_COST_USD:
            return None, "max_cost"
        if clock() - t0 - waited >= MAX_WALL_S:
            return None, "max_wall"
        parts = split_prompt(messages, host.tools, tool_names)
        started = clock()
        msg, usage = llm.chat(messages, tools=host.tools,
                              max_completion_tokens=int(min(4096, MAX_TOKENS - tokens)),
                              timeout=max(1.0, MAX_WALL_S - (clock() - t0 - waited)))
        trace.generation(lap, started, usage, parts)
        tokens += usage["total_tokens"]
        cost += usage["cost_usd"]
        waited += usage["wait_s"]
        messages.append(assistant_turn(msg))
        log("lap %d  +%d tok  %.1fs  finish=%s" % (lap, usage["total_tokens"], usage["call_s"],
                                                   usage["finish_reason"]))

        if usage["finish_reason"] == "tool_use_failed":
            messages.append({"role": "user", "content":
                             "Your last reply called a tool that does not exist. Call one of the "
                             "declared tools, or reply with the summary as plain text."})
            continue
        if not msg.tool_calls:
            if usage["finish_reason"] == "length":
                continue
            return (msg.content or "").strip(), None
        for call in msg.tool_calls:
            tool_names[call.id] = call.function.name
            started = clock()
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args, result = {}, {"error": "arguments were not valid JSON"}
            else:
                result, _ = await host.call(call.function.name, args)
            trace.tool(call.function.name, started, clock() - started, args, result)
            log("      -> %s(%s)" % (call.function.name, json.dumps(args)))
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result, ensure_ascii=False)})
    return None, "max_iters"


async def handle(notes, user, input_type, version=None, write=True, log=print):
    """Run one request end to end and (by default) write its trace. Returns the
    trace record - redacted if it was written."""
    version = version or prompts.for_user(user)
    trace = Trace(user, input_type, notes, version, prompts.sha(version))
    started = time.perf_counter()
    async with Host(CONFIG) as host:   # a fresh server per request: no request sees another's evidence
        trace.setup(started, time.perf_counter() - started, list(host.sessions))
        try:
            summary, stop = await answer(notes, host, trace, version, log)
            error = None
        except Exception as exc:          # a failed request still gets a trace
            summary, stop, error = None, None, "%s: %s" % (type(exc).__name__, exc)
    record = trace.finish(summary, assertions.fields(summary), stop, error)
    if write:
        trace.write()
    log("DONE  %s  position %s  %d tok  $%.5f  %.1fs" % (
        record["trace_id"], record["position"], record["tokens"], record["cost_usd"], record["latency_s"]))
    if error:
        raise RuntimeError(error)
    return record


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("notes")
    p.add_argument("--user", default="adj-00")
    p.add_argument("--input-type", default="file_note", choices=["file_note", "desk_question"])
    p.add_argument("--no-log", action="store_true")
    a = p.parse_args()
    rec = asyncio.run(handle(a.notes, a.user, a.input_type, write=not a.no_log))
    print(rec["output"])
