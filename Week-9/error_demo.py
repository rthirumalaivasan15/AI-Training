"""The same failing search_policy call, handled by the model before and after the
docstring / error rewrite on our own policy server.

    python error_demo.py before     -> runs/error_before.json   (run at the old server)
    python error_demo.py after      -> runs/error_after.json    (run at the new server)

The failing call is pinned so both runs see exactly the same one: the first time
the model calls search_policy, that call is swapped for PINNED, which writes the
sewer endorsement the way ISO prints form numbers ('HO 08 20') instead of the way
our library keys them ('HO-0820'). Every other turn, before and after, is the
model. The tokens of the swapped-out lap are still counted.
"""
import os
import sys
import json
import asyncio
import datetime
from types import SimpleNamespace

import llm
import agent
import contract
from mcp_host import Host

CONFIG = "mcp_config.json"
CLAIM = "CLM-2024-10004"   # sewer backup: decided by the HO-0820 Clause 2 grant and its 10,000 cap
PINNED = {"query": "sewer or drain backup: exclusion, coverage grant and per-event limit",
          "form_numbers": ["HO-0304", "HO 08 20"]}

with open("expected.json", encoding="utf-8") as f:
    EXPECTED = json.load(f)["claims"][CLAIM]


def pin_first_search(chat, record):
    def pinned(messages, tools=None, **kw):
        msg, usage = chat(messages, tools=tools, **kw)
        calls = msg.tool_calls or []
        searches = [c for c in calls if c.function.name == "search_policy"]
        if record.get("swapped") is None and searches:
            record["swapped"] = [json.loads(c.function.arguments) for c in searches]
            kept = [c for c in calls if c.function.name != "search_policy"]
            swap = SimpleNamespace(id=searches[0].id, type="function", function=SimpleNamespace(
                name="search_policy", arguments=json.dumps(PINNED)))
            msg = SimpleNamespace(content=msg.content, tool_calls=kept + [swap])
        return msg, usage
    return pinned


async def main(tag):
    path = "runs/error_%s.json" % tag
    if os.path.exists(path):
        sys.exit("%s exists - delete it to re-run this tag" % path)
    lines, record = [], {"swapped": None}
    async with Host(CONFIG, lines.append) as host:
        description = next(t["function"] for t in host.tools if t["function"]["name"] == "search_policy")
        result = await agent.run(CLAIM, host, log=lines.append, chat=pin_first_search(llm.chat, record))
    passed, why = contract.grade(result["output"], EXPECTED)
    out = {"tag": tag, "claim_id": CLAIM, "pinned_call": PINNED, "model_search_swapped_out": record["swapped"],
           "search_policy_as_listed": description, "outcome_passed": passed, "outcome_fail_reasons": why,
           "model": llm.MODEL, "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "log": lines, **result}
    os.makedirs("runs", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("\n".join(lines))
    print("outcome %s %s" % ("PASS" if passed else "FAIL", why))
    print("wrote", path)


def render(tag):
    """The run as a markdown transcript: every turn, with passages cut to their
    chunk id and first line, and every error in full."""
    with open("runs/error_%s.json" % tag, encoding="utf-8") as f:
        d = json.load(f)
    out = ["**Model's own first search, swapped for the pinned call:** `%s`"
           % json.dumps(d["model_search_swapped_out"]), ""]
    lap = 0
    for m in d["messages"][2:]:
        if m["role"] == "assistant":
            lap += 1
            for c in m.get("tool_calls", []):
                args = json.loads(c["function"]["arguments"])
                pinned = "  **<- the pinned failing call**" if c["function"]["name"] == "search_policy" \
                    and args == PINNED else ""
                out.append("- lap %d model -> `%s(%s)`%s" % (lap, c["function"]["name"],
                                                          json.dumps(args), pinned))
            if not m.get("tool_calls"):
                out += ["- lap %d model -> final answer:" % lap, "", "```json",
                        json.dumps(d["output"], indent=2, ensure_ascii=False), "```"]
        elif m["role"] == "tool":
            body = json.loads(m["content"])
            if isinstance(body, dict) and "error" in body:
                out.append("  - tool returned **error**: `%s`" % body["error"])
            elif isinstance(body, dict) and "passages" in body:
                out.append("  - tool returned %d passages: %s" % (len(body["passages"]), ", ".join(
                    "`%s` (%s)" % (p["chunk_id"], p["text"].split("\n")[0][:48]) for p in body["passages"])))
            else:
                out.append("  - tool returned `%s`" % json.dumps(body, ensure_ascii=False)[:160])
    out += ["", "Outcome **%s**%s - %d laps, %d tokens, $%.5f, %.1f s active."
            % ("PASS" if d["outcome_passed"] else "FAIL",
               " (%s)" % "; ".join(d["outcome_fail_reasons"]) if d["outcome_fail_reasons"] else "",
               d["laps"], d["tokens"], d["cost_usd"], d["latency_s"])]
    return "\n".join(out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1] == "render":
        print(render(sys.argv[2]))
    else:
        asyncio.run(main(sys.argv[1]))
