"""The triage agent: the Week 7 hand-built loop, its tools discovered over MCP
(Week 9), every step traced (Week 11).

The model call happens here and only here - llm.chat - never in an MCP server.
A run ends the moment refer_to_adjuster accepts a referral: that tool is the only
way out, and it refuses any payload that states a coverage decision.
"""
import json
import time

import llm
import prompts
from tracer import split_prompt

MAX_ITERS = 10
MAX_TOKENS = 60_000
MAX_COST_USD = 0.02
MAX_WALL_S = 120       # active seconds; rate-limit backoff excluded
MIN_COMPLETION = 512


def assistant_turn(msg):
    turn = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        turn["tool_calls"] = [{"id": c.id, "type": "function",
                               "function": {"name": c.function.name, "arguments": c.function.arguments}}
                              for c in msg.tool_calls]
    return turn


async def triage(claim_id, host, trace, version, log=print):
    """Returns (referral, stop_reason). referral is the accepted refer_to_adjuster
    payload plus its referral id and citation links, or None."""
    messages = [{"role": "system", "content": prompts.get(version)},
                {"role": "user", "content": "Triage claim %s." % claim_id}]
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
        log("lap %d  +%d tok  %.1fs  %s" % (lap, usage["total_tokens"], usage["call_s"],
                                            ", ".join(c.function.name for c in msg.tool_calls or []) or usage["finish_reason"]))

        if usage["finish_reason"] == "tool_use_failed":
            # the provider refused the call - usually arguments that do not match the tool's schema
            log("      provider refused the call: %s" % " ".join((msg.rejected or "")[:240].split()))
            messages.append({"role": "user", "content": "The provider refused your last tool call: its arguments "
                                                        "did not match the tool's schema, or the tool does not "
                                                        "exist. Call a declared tool again with arguments that "
                                                        "match its parameters exactly."})
            continue
        if not msg.tool_calls:
            if usage["finish_reason"] == "length":
                continue
            messages.append({"role": "user", "content": "A triage ends only with refer_to_adjuster. Call it."})
            continue
        for call in msg.tool_calls:
            tool_names[call.id] = call.function.name
            started = clock()
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args, result = {}, {"error": "arguments were not valid JSON"}
            else:
                result, _ = await host.call(call.function.name, args, trace.id)
            trace.tool(call.function.name, started, clock() - started, args, result)
            failed = isinstance(result, dict) and "error" in result
            log("      -> %s%s" % (call.function.name, "  ERROR " + result["error"][:160] if failed else ""))
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result, ensure_ascii=False)})
            if call.function.name == "refer_to_adjuster" and not failed:
                cites = [dict(zip(("chunk_id", "cites"), (x.strip() for x in c.partition(":")[::2])))
                         for c in args.get("citations", [])]
                return {**args, **result, "citations": cites}, None
    return None, "max_iters"
