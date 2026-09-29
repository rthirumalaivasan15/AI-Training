"""The same claims triage as agent.py, as a fixed workflow: five hard-coded steps,
the same three tools, the same model, the same output contract. No loop - the
model never chooses what runs next, it only fills in the two steps that need
language.

    python workflow.py CLM-2024-10001

    1. get_claim        (code)   pull the claim record and notes
    2. read the notes   (model)  state the facts that matter and one wording query
    3. search_policy    (code)   that query, restricted to the forms on the policy
    4. decide           (model)  position, grounds, and the figures for the payout
    5. compute_payout   (code)   payable amount after the excess

Step 3 depends on what step 2 found, but only through data: the query changes
with the notes, the path never does.
"""
import re
import sys
import json
import time

import llm
import contract
from tools import get_claim, search_policy, compute_payout

SEARCH_K = 5

READ_NOTES = """You read an insurance claim file for a claims adjuster. From the claim record and the adjuster's notes, state the facts that decide coverage (cause of loss, how long it went on, occupancy or vacancy, business use, anything the insured did or failed to do) and write one search query for the endorsement wording that those facts bring into play.

Return one JSON object and nothing else:
{"facts": "<two to four sentences>", "search_query": "<one query for the endorsement wording>"}"""

DECIDE = """You triage insurance claims for a claims adjuster. You are given the claim record, the adjuster's notes, and endorsement passages retrieved for this claim.

Rules:
- Rely only on the claim record and the passages. You have no other knowledge of the policy wording.
- Check every exclusion, exception, limit or duty the facts in the notes bring into play.
- If the notes do not establish the facts an exclusion or exception turns on, the position is UNDETERMINED. Never guess.
- Do not compute the payable amount. Give the figures it will be computed from.

Return one JSON object and nothing else, with exactly these keys:
{
  "coverage_position": "COVERED" | "DENIED" | "UNDETERMINED",
  "grounds": ["<exclusion codes such as E-17 and form clauses such as HO-0820 Clause 2 the position rests on>"],
  "loss_amount": <integer dollars of loss the position applies to>,
  "excess": <integer dollars of excess or deductible that applies to this loss>,
  "limit": <integer dollars of per-event limit or sublimit that caps this loss, or null if none>,
  "reasoning": "<two to four sentences, each citing the chunk id it relies on in square brackets>",
  "next_step": "<one sentence for the adjuster>"
}"""


def json_reply(text):
    found = re.search(r"\{.*\}", text or "", re.S)
    if not found:
        raise ValueError("no JSON object in reply")
    return json.loads(found.group(0))


def ask(system, user, totals):
    msg, usage = llm.chat([{"role": "system", "content": system},
                           {"role": "user", "content": user}])
    totals["tokens"] += usage["total_tokens"]
    totals["cost_usd"] += usage["cost_usd"]
    totals["rate_limit_wait_s"] += usage["wait_s"]
    totals["model_calls"] += 1
    return msg.content


def run(claim_id, log=print):
    started = time.perf_counter()
    totals = {"tokens": 0, "cost_usd": 0.0, "rate_limit_wait_s": 0.0, "model_calls": 0}
    calls = []

    def done(output, error):
        return {"claim_id": claim_id, "output": output, "error": error, "stop_reason": None,
                "laps": totals["model_calls"], "tokens": totals["tokens"],
                "cost_usd": totals["cost_usd"],
                "latency_s": time.perf_counter() - started - totals["rate_limit_wait_s"],
                "rate_limit_wait_s": totals["rate_limit_wait_s"], "tool_calls": calls}

    try:
        # 1. pull the claim
        claim = get_claim(claim_id)
        calls.append({"tool": "get_claim", "args": {"claim_id": claim_id}})
        if "error" in claim:
            return done(None, claim["error"])
        record = json.dumps(claim, ensure_ascii=False, indent=1)
        log("step 1  get_claim(%s)" % claim_id)

        # 2. read the notes
        read = json_reply(ask(READ_NOTES, "Claim record:\n" + record, totals))
        log("step 2  facts: %s" % read["facts"])

        # 3. search the wording the notes point at, on this policy's forms only
        passages = search_policy(read["search_query"], claim["forms_attached"], k=SEARCH_K)
        calls.append({"tool": "search_policy",
                      "args": {"query": read["search_query"], "form_numbers": claim["forms_attached"]}})
        log("step 3  search_policy(%r) -> %s"
            % (read["search_query"], ", ".join(p["chunk_id"] for p in passages)))
        context = "\n\n---\n\n".join("[%s]\n%s" % (p["chunk_id"], p["text"]) for p in passages)

        # 4. decide
        decision = json_reply(ask(DECIDE, "Claim record:\n%s\n\nEndorsement passages:\n\n%s"
                                  % (record, context), totals))
        log("step 4  %s %s" % (decision["coverage_position"], decision["grounds"]))

        # 5. compute the payout
        payout_args = {"claim_status": str(decision["coverage_position"]).lower(),
                       "loss_amount": int(decision["loss_amount"] or 0),
                       "excess": int(decision["excess"] or 0),
                       "limit": None if decision.get("limit") is None else int(decision["limit"])}
        payout = compute_payout(**payout_args)
        calls.append({"tool": "compute_payout", "args": payout_args})
        log("step 5  compute_payout(%s) -> %s" % (json.dumps(payout_args), payout))
        if "error" in payout:
            return done(None, payout["error"])

    except (ValueError, KeyError, TypeError) as exc:
        return done(None, "%s: %s" % (type(exc).__name__, exc))

    output, error = contract.validate({
        "claim_id": claim_id,
        "coverage_position": decision["coverage_position"],
        "grounds": decision["grounds"],
        "payable_amount": payout["payable_amount"],
        "reasoning": decision["reasoning"],
        "next_step": decision["next_step"],
    })
    return done(output, error)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    result = run(sys.argv[1])
    print(json.dumps(result["output"], indent=2))
    print("tokens %d  cost $%.5f  latency %.2fs" % (result["tokens"], result["cost_usd"], result["latency_s"]))
