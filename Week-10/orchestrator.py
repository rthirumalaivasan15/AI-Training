r"""Arm 2: the claims squad - an orchestrator that decomposes the claim, delegates
to two workers, and synthesises the summary.

    python orchestrator.py C02
    python orchestrator.py C02 --fail coverage_worker      # inject a 500 from that worker

    case notes --> orchestrator.plan -----------------brief--> coverage worker --+
          \                                                    (search_policy)   |
           +--> notes worker --facts---------------------------------------------+--> orchestrator.synthesis --> summary

Context strategy, chosen so the race tests the pattern and not a wasteful hand-off:
- the notes go to two calls only (plan and notes worker), which run in parallel;
- the coverage/exclusions worker never sees the notes, only the orchestrator's brief,
  and it gets one tool (search_policy), not everything the single agent had;
- synthesis sees only the two workers' results, never the notes or the wording.

Every delegation is a hand-off with its own token ledger: what was handed over,
how many model calls it triggered, and the tokens and cost they billed.

Workers answer in an HTTP-style envelope {"status", "body"}. The orchestrator's
policy for any worker error is generic and was written before any failure was
injected: retry once after RETRY_BACKOFF_S on a 5xx, then hand the error envelope
to synthesis as that worker's result.
"""
import re
import sys
import json
import asyncio
import argparse

import llm
import cases
import summary_format
from mcp_host import Host

CONFIG = "mcp_config.json"
COVERAGE_TOOLS = ("search_policy",)
COVERAGE_MAX_LAPS = 6
RETRY_BACKOFF_S = 1.0

PLAN_SYSTEM = """You are the orchestrator of a claims squad. Read the adjuster's file notes and write the brief for your coverage and exclusions worker. The worker never sees the notes - only your brief - so every fact the coverage could turn on must be in it. Do not decide coverage yourself.

Reply with one JSON object and nothing else:
{"coverage_question": "the coverage question this claim raises, one sentence",
 "forms": ["each endorsement form and edition the notes name, e.g. HO-0304 ed. 03-24"],
 "policy": "policy type, policy line and occupancy as the notes give them",
 "facts": ["every fact an exclusion, exception, definition, limit or duty could turn on: the cause, how long it went on, when it was discovered, vacancy, business use, maintenance, what the insured did and when, the amounts claimed"]}"""

NOTES_SYSTEM = """You are the adjuster-note summary worker in a claims squad. Read the adjuster's file notes and pull out the claim facts. Do not judge coverage.

Reply with one JSON object and nothing else:
{"claim_number": "the claim number exactly as written in the notes, in the form CLM-YYYY-NNNNN, or NOT STATED",
 "date_of_loss": "YYYY-MM-DD, or NOT STATED",
 "loss": "one sentence describing what happened",
 "excess": "the excess or deductible in dollars as digits only, or NOT STATED"}"""

COVERAGE_SYSTEM = """You are the coverage and exclusions worker in a claims squad. You receive a brief from the orchestrator: the coverage question, the endorsement forms attached, and the facts from the adjuster's notes. You never see the notes themselves.

Search the endorsement wording with search_policy for every exclusion, exception, definition, limit or duty the facts bring into play - including the definition any exception depends on - then reply with one JSON object and nothing else:
{"position": "COVERED" | "DENIED" | "PARTIAL" | "UNDETERMINED" | "NOT_IN_DOCUMENTS",
 "grounds": ["exclusion codes such as E-17, or form clauses such as HO-0820 Clause 2"],
 "forms": ["form number and edition the position rests on"],
 "subject_to": "anything the position is conditional on, from the wording, or an empty string",
 "reasoning": "two to four sentences, each ending with the chunk id it relies on in square brackets",
 "missing": "facts the wording turns on that the brief does not establish, or an empty string"}

""" + summary_format.RULES

SYNTH_SYSTEM = """You are the orchestrator of a claims squad, writing the final claim summary for the adjuster from your two workers' results. You see neither the notes nor the wording - only what each worker returned, with its status.

- CLAIM NUMBER, DATE OF LOSS, LOSS and EXCESS come from the notes worker.
- COVERAGE POSITION, GROUNDS and POLICY FORMS come from the coverage worker, exactly as it gave them. Do not upgrade, downgrade or round its position: if it says the position is subject to something, the position stays as the worker gave it and the condition goes into REASONING.
- REASONING restates the coverage worker's reasoning with its chunk ids.

""" + summary_format.OUTPUT_SPEC + "\n\n" + summary_format.RULES


class WorkerError(Exception):
    pass


def parse_json(text):
    found = re.search(r"\{.*\}", text or "", re.S)
    if not found:
        raise WorkerError("reply was not a JSON object: %r" % (text or "")[:200])
    try:
        return json.loads(found.group(0))
    except json.JSONDecodeError as exc:
        raise WorkerError("reply was not valid JSON (%s)" % exc)


class Handoff:
    """One delegation edge and everything it billed."""

    def __init__(self, name, payload):
        self.name = name
        self.payload_chars = len(payload)
        self.calls = []        # one entry per model call made to serve this hand-off
        self.tool_s = 0.0
        self.backoff_s = 0.0
        self.status = None

    def charge(self, usage, note=""):
        self.calls.append({"prompt_tokens": usage["prompt_tokens"],
                           "completion_tokens": usage["completion_tokens"],
                           "cost_usd": usage["cost_usd"], "call_s": round(usage["call_s"], 3),
                           "wait_s": usage["wait_s"], "estimated": bool(usage.get("estimated")),
                           "note": note})

    def totals(self):
        p = sum(c["prompt_tokens"] for c in self.calls)
        o = sum(c["completion_tokens"] for c in self.calls)
        return {"name": self.name, "status": self.status, "payload_chars": self.payload_chars,
                "calls": len(self.calls), "prompt_tokens": p, "completion_tokens": o, "tokens": p + o,
                "cost_usd": sum(c["cost_usd"] for c in self.calls),
                "active_s": round(sum(c["call_s"] for c in self.calls) + self.tool_s + self.backoff_s, 3),
                "wait_s": sum(c["wait_s"] for c in self.calls), "laps": self.calls}


def one_call(handoff, system, user, note=""):
    msg, usage = llm.chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
    handoff.charge(usage, note)
    return msg.content or ""


async def delegate(handoff, worker, payload, fail=None, log=print):
    """Send one hand-off to a worker. 5xx -> one retry after RETRY_BACKOFF_S."""
    for attempt in (1, 2):
        if fail == worker:
            envelope = {"status": 500, "body": "Internal Server Error"}     # injected, worker not run
        else:
            try:
                envelope = {"status": 200, "body": await WORKERS[worker](handoff, payload, log)}
            except WorkerError as exc:
                envelope = {"status": 500, "body": "worker error: %s" % exc}
        envelope["attempts"] = attempt
        log("      %s -> status %d (attempt %d)" % (handoff.name, envelope["status"], attempt))
        if envelope["status"] < 500 or attempt == 2:
            handoff.status = envelope["status"]
            return envelope
        await asyncio.sleep(RETRY_BACKOFF_S)
        handoff.backoff_s += RETRY_BACKOFF_S


async def notes_worker(handoff, notes, log):
    text = await asyncio.to_thread(one_call, handoff, NOTES_SYSTEM, "Adjuster notes:\n%s" % notes)
    return parse_json(text)


async def coverage_worker(handoff, brief, log):
    host = brief["_host"]
    tools = [t for t in host.tools if t["function"]["name"] in COVERAGE_TOOLS]
    messages = [{"role": "system", "content": COVERAGE_SYSTEM},
                {"role": "user", "content": "Brief from the orchestrator:\n%s" % brief["text"]}]
    for lap in range(1, COVERAGE_MAX_LAPS + 1):
        msg, usage = await asyncio.to_thread(llm.chat, messages, tools=tools)
        searches = [c for c in (msg.tool_calls or [])]
        handoff.charge(usage, "lap %d%s" % (lap, ": " + ", ".join(
            c.function.arguments for c in searches) if searches else ": answer"))
        if usage["finish_reason"] == "tool_use_failed":
            messages.append({"role": "user", "content": "That tool does not exist. Call search_policy "
                                                        "or reply with the JSON object."})
            continue
        turn = {"role": "assistant", "content": msg.content or ""}
        if not searches:
            return parse_json(msg.content)
        turn["tool_calls"] = [{"id": c.id, "type": "function", "function": {
            "name": c.function.name, "arguments": c.function.arguments}} for c in searches]
        messages.append(turn)
        for c in searches:
            loop = asyncio.get_running_loop()
            started = loop.time()
            try:
                result, _ = await host.call(c.function.name, json.loads(c.function.arguments or "{}"))
            except json.JSONDecodeError:
                result = {"error": "arguments were not valid JSON"}
            handoff.tool_s += loop.time() - started
            log("      coverage worker -> %s(%s)" % (c.function.name, c.function.arguments))
            messages.append({"role": "tool", "tool_call_id": c.id,
                             "content": json.dumps(result, ensure_ascii=False)})
    raise WorkerError("no answer after %d laps" % COVERAGE_MAX_LAPS)


WORKERS = {"notes_worker": notes_worker, "coverage_worker": coverage_worker}


async def run(case, fail=None, log=print):
    notes = case["notes"]
    log("START multi %s%s" % (case["id"], "  (injecting 500 from %s)" % fail if fail else ""))
    plan = Handoff("case -> orchestrator (plan)", notes)
    to_notes = Handoff("orchestrator -> notes worker", notes)

    async with Host(CONFIG) as host:
        plan_text, notes_env = await asyncio.gather(
            asyncio.to_thread(one_call, plan, PLAN_SYSTEM, "Adjuster notes:\n%s" % notes),
            delegate(to_notes, "notes_worker", notes, fail, log))
        plan.status = 200
        try:
            brief_text = json.dumps(parse_json(plan_text), ensure_ascii=False)
        except WorkerError:
            brief_text = plan_text      # the plan was not JSON; hand it over as written
        log("      brief: %s" % brief_text[:300])

        to_cov = Handoff("orchestrator -> coverage worker", brief_text)
        cov_env = await delegate(to_cov, "coverage_worker", {"text": brief_text, "_host": host}, fail, log)

    results = json.dumps({"notes_worker": notes_env, "coverage_worker": cov_env}, ensure_ascii=False, indent=1)
    synth = Handoff("workers -> orchestrator (synthesis)", results)
    summary = (await asyncio.to_thread(one_call, synth, SYNTH_SYSTEM,
                                       "Worker results:\n%s" % results)).strip()
    synth.status = 200
    log("DONE  position %s" % summary_format.position(summary))

    handoffs = [h.totals() for h in (plan, to_notes, to_cov, synth)]
    # the critical path: plan and notes worker run side by side
    latency = max(handoffs[0]["active_s"], handoffs[1]["active_s"]) + handoffs[2]["active_s"] + handoffs[3]["active_s"]
    return {"id": case["id"], "arm": "multi", "summary": summary, "injected_failure": fail,
            "brief": brief_text, "worker_results": {"notes_worker": notes_env, "coverage_worker": cov_env},
            "calls": sum(h["calls"] for h in handoffs),
            "prompt_tokens": sum(h["prompt_tokens"] for h in handoffs),
            "completion_tokens": sum(h["completion_tokens"] for h in handoffs),
            "tokens": sum(h["tokens"] for h in handoffs),
            "cost_usd": sum(h["cost_usd"] for h in handoffs),
            "latency_s": latency, "rate_limit_wait_s": sum(h["wait_s"] for h in handoffs),
            "handoffs": handoffs}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("case_id")
    p.add_argument("--fail", choices=list(WORKERS))
    a = p.parse_args()
    case = next(c for c in cases.load() if c["id"] == a.case_id)
    out = asyncio.run(run(case, a.fail))
    print(out["summary"])
    for h in out["handoffs"]:
        print("%-38s %d calls %6d tok" % (h["name"], h["calls"], h["tokens"]))
