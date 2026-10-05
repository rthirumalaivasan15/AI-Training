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


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main(sys.argv[1]))
