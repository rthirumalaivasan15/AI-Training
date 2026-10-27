"""The claims triage & coverage assistant - one entry point.

    python app.py triage CLM-2024-30001      one claim end to end: FNOL in -> referral out
    python app.py trace trc_0123abcd4567     one request across every hop: host spans + MCP server spans
    python app.py eval [tag]                 the eval suite against the integrated system (runs/eval_<tag>.*)
    python app.py report [tag] [before]      eval report, trajectory eval, cost and the 10x plan, from the runs

Integrated: RAG (Weeks 3-4: dense retrieval over clause-level chunks), the hand-built
agent loop (Week 7) with its tools discovered over MCP (Week 9) from two servers -
claims-system and our own policy-docs - and per-request tracing (Week 11) with one
trace id carried through every MCP call. The system never states a coverage decision:
it ends only by referring the claim to an adjuster.
"""
import os
import sys
import json
import time
import asyncio
import argparse

import llm                      # loads .env (Groq key, CLAIMS_API_TOKEN) before any server starts
import agent
import prompts
import tracer
from mcp_host import Host

CONFIG = "mcp_config.json"


async def handle(claim_id, user="adj-01", version=None, write=True, log=print):
    """One triage, traced. Returns the trace record (redacted if written)."""
    version = version or prompts.active()
    trace = tracer.Trace(user, "fnol", "Triage claim %s." % claim_id, version, prompts.sha(version))
    started = time.perf_counter()
    error, referral, stop = None, None, None
    async with Host(CONFIG) as host:
        trace.setup(started, time.perf_counter() - started, list(host.sessions))
        try:
            referral, stop = await agent.triage(claim_id, host, trace, version, log)
        except Exception as exc:               # a failed request still gets a trace
            error = "%s: %s" % (type(exc).__name__, exc)
    cites = ", ".join(c.get("cites", "") for c in (referral or {}).get("citations", []))
    record = trace.finish(json.dumps(referral, ensure_ascii=False) if referral else "",
                          {"COVERAGE POSITION": (referral or {}).get("assessment"), "GROUNDS": cites},
                          stop or (None if referral else "no_referral"), error)
    record["referral"] = referral
    if write:
        tracer.write(record)
    log("DONE  %s  %s  %d tok  $%.5f  %.1fs" % (record["trace_id"], record["position"], record["tokens"],
                                                record["cost_usd"], record["latency_s"]))
    return record


def server_spans(trace_id):
    spans = []
    for name in sorted(os.listdir(tracer.LOG_DIR)):
        if name.startswith("mcp_") and name.endswith(".jsonl"):
            with open(os.path.join(tracer.LOG_DIR, name), encoding="utf-8") as f:
                spans += [s for s in (json.loads(l) for l in f if l.strip()) if s.get("trace_id") == trace_id]
    return sorted(spans, key=lambda s: s["ts"])


def end_to_end(trace_id):
    rows = [r for r in tracer.read() if r["trace_id"] == trace_id]
    if not rows:
        sys.exit("no trace %s" % trace_id)
    return {**rows[0], "server_spans": server_spans(trace_id)}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("triage")
    t.add_argument("claim_id")
    t.add_argument("--user", default="adj-01")
    sub.add_parser("trace").add_argument("trace_id")
    e = sub.add_parser("eval")
    e.add_argument("tag", nargs="?", default="run")
    e.add_argument("--modes", help="comma-separated case modes to run, e.g. version-straddle,wording-not-on-file")
    r = sub.add_parser("report")
    r.add_argument("tag", nargs="?", default="run")
    r.add_argument("before", nargs="?", help="a run to compare against on the cases both hold, e.g. before")
    a = p.parse_args()

    if a.cmd == "triage":
        rec = asyncio.run(handle(a.claim_id, a.user))
        md = os.path.join("referrals", "%s.md" % a.claim_id)
        print(open(md, encoding="utf-8").read() if rec["referral"] and os.path.exists(md)
              else "NO REFERRAL - stop: %s, error: %s" % (rec["stop_reason"], rec["error"]))
        print("trace: python app.py trace %s" % rec["trace_id"])
    elif a.cmd == "trace":
        print(json.dumps(end_to_end(a.trace_id), indent=2, ensure_ascii=False))
    elif a.cmd == "eval":
        import suite
        asyncio.run(suite.run(a.tag, a.modes.split(",") if a.modes else None))
    elif a.cmd == "report":
        import report
        report.main(a.tag, a.before)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
