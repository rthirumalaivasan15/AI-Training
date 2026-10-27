"""The gates the code enforces, checked over the real MCP stdio connection - no model is called.

    python gates.py

Each check is a failure the eval found (or a rule the brief makes non-negotiable), replayed as
a tool call against policy-docs exactly as the agent would send it. Free and deterministic, so
it runs before every eval: a gate that stops holding fails here, not in a 25-case run.

Referrals the checks write go to a temporary folder, not referrals/; server spans go to
logs/mcp_policy-docs.jsonl under trace ids starting trc_gates.
"""
import os
import sys
import json
import asyncio
import secrets
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client, get_default_environment

SPANS = os.path.join("logs", "mcp_policy-docs.jsonl")

# CLM-2024-30032, run "after", trace trc_d41d68b1a7ad: the policy carries HO-0415 ed. 05-23 (not
# in the library); the agent searched "HO-0415" bare, got ed. 01-24 and referred on it.
WRONG_EDITION = {
    "claim_id": "CLM-2024-30032", "policy_number": "HP-460132", "loss_date": "2024-09-03",
    "in_force": "IN_FORCE", "assessment": "EXCLUSION_APPEARS_TO_APPLY", "wording": ["HO-0415 ed. 01-24"],
    "citations": ["HO-0415_01-24#05: E-22 - Damage to metal roof surfacing consisting solely of denting",
                  "HO-0415_01-24#05: E-21 - Cosmetic damage to roof surfacing caused by hail"],
    "deductible": 2500, "sub_limit": None, "policy_limit": 340000,
    "facts": ["2024-09-03 Hail dented the metal roof panels; the roofer finds no leaks."],
    "note": "Denting without loss of water-shedding function falls under E-22. [HO-0415_01-24#05]"}
NOT_ON_FILE = {**WRONG_EDITION, "assessment": "WORDING_NOT_ON_FILE", "wording": [], "citations": [],
               "note": "The policy carries HO-0415 ed. 05-23, which is not in the wording library."}
INJURY = {
    "claim_id": "CLM-2024-30021", "policy_number": "HP-460121", "loss_date": "2024-07-21",
    "in_force": "IN_FORCE", "assessment": "NO_EXCLUSION_TRIGGERED", "wording": ["HO-0820 ed. 05-24"],
    "citations": ["HO-0820_05-24#01: HO-0820 Clause 1"], "deductible": 1000, "sub_limit": 10000,
    "policy_limit": 380000,
    "facts": ["Sewer backed up through the floor drain into the finished basement.",
              "Insured Mr. Omar Haddad's son cut his hand on broken glass while moving boxes and needed 4 stitches."],
    "note": "Water backup through a drain falls under HO-0820 Clause 1. [HO-0820_05-24#01]"}


def text(res):
    return "\n".join(c.text for c in res.content if c.type == "text")


async def main():
    out = tempfile.mkdtemp(prefix="gates_")
    params = StdioServerParameters(command=sys.executable, args=["policy_server.py"],
                                   env={**get_default_environment(), "REFERRALS_DIR": out})
    trace = "trc_gates%s" % secrets.token_hex(3)
    results = []

    def check(name, ok, detail):
        results.append(ok)
        print("  %-4s %-44s %s" % ("ok" if ok else "FAIL", name, detail))

    async with stdio_client(params) as (read, write), ClientSession(read, write) as s:
        await s.initialize()

        async def call(tool, args):
            return await s.call_tool(tool, args, meta={"trace_id": trace})

        r = await call("search_policy", {"query": "hail dented metal roof", "loss_date": "2024-09-03",
                                         "form_numbers": ["HO-0415 ed. 05-23"]})
        check("edition not in library is refused", r.is_error and "WORDING_NOT_ON_FILE" in text(r), text(r)[:90])

        for day, ed in (("2024-08-11", "03-24"), ("2024-12-31", "03-24"), ("2025-01-01", "01-25")):
            r = await call("search_policy", {"query": "surface water storm wind-driven rain", "loss_date": day,
                                             "form_numbers": ["HO-0304"]})
            eds = sorted({p["edition"] for p in json.loads(text(r))["passages"]}) if not r.is_error else text(r)
            check("HO-0304 on %s returns only ed. %s" % (day, ed), eds == [ed], "editions returned: %s" % eds)

        r = await call("refer_to_adjuster", WRONG_EDITION)
        check("wrong edition referral refused (CLM-2024-30032)", r.is_error and "05-23" in text(r), text(r)[:90])

        r = await call("refer_to_adjuster", NOT_ON_FILE)
        check("WORDING_NOT_ON_FILE referral accepted", not r.is_error, text(r)[:90])

        r = await call("refer_to_adjuster", {**NOT_ON_FILE, "note": "The roof is not covered."})
        check("'covered' in a referral is refused", r.is_error and "covered" in text(r), text(r)[:90])

        r = await call("refer_to_adjuster", INJURY)
        stored = open(os.path.join(out, "CLM-2024-30021.json"), encoding="utf-8").read() if not r.is_error else ""
        leaked = [w for w in ("Haddad", "Omar", "stitches", "cut his hand") if w in stored + text(r)]
        check("name and injury redacted before storing", not r.is_error and not leaked,
              "leaked %s" % leaked if leaked else "stored referral holds no name or injury")

    with open(SPANS, encoding="utf-8") as f:
        spans = [json.loads(l) for l in f if trace in l]
    # 9 calls, 4 refused: a refusal raises before the server logs, so it shows host-side only
    check("trace id carried into server spans", len(spans) == 5, "%d server spans under %s" % (len(spans), trace))
    print("\nGATES %d/%d hold" % (sum(results), len(results)))
    return all(results)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(0 if asyncio.run(main()) else 1)
