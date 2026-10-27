"""policy-docs: our MCP server - policy records, coverage in force, wording search,
and the referral queue. stdio; no model is called anywhere in this file.

    python policy_server.py      # normally started by the host from mcp_config.json

Tools:
  policy_lookup(policy_number)                  the policy's terms, forms with editions
  coverage_in_force(policy_number, loss_date)   is there a term covering the loss date; its
                                                forms, deductibles, sub-limits and limits
  search_policy(query, loss_date, form_numbers, product)
                                                wording IN FORCE ON THE LOSS DATE, edition resolved in code
  refer_to_adjuster(...)                        the ONLY way out: queues the claim for an
                                                adjuster with the wording and facts; refuses
                                                any payload that states a coverage decision

Every call logs one server-side span to logs/mcp_policy-docs.jsonl under the trace id
the caller sent in the request _meta. Nothing this server returns carries a claimant's
name, address or injury: policy records hold none, wording holds none, and a referral
is redacted before it is stored or echoed.
"""
import os
import re
import json
import time
import secrets
import datetime
from typing import Annotated, Literal, Optional

from pydantic import Field
from mcp.server.mcpserver import MCPServer, Context
from mcp.server.mcpserver.exceptions import ToolError

import redact
from index import load_chunks
from search import dense_search

HERE = os.path.dirname(os.path.abspath(__file__))
POLICIES = os.path.join(HERE, "policy_admin", "policies.json")
REFERRALS = os.path.join(HERE, "referrals")
SPANS = os.path.join(HERE, "logs", "mcp_policy-docs.jsonl")

with open(POLICIES, encoding="utf-8") as f:
    _policies = json.load(f)
_chunks = {c["chunk_id"]: c for c in load_chunks()}
FORMS = sorted({c["form_number"] for c in _chunks.values()})
COVERED = re.compile(r"\b(?:un)?covered\b", re.I)

mcp = MCPServer("policy-docs", log_level="WARNING")


def _trace_id(ctx):
    meta = ctx.request_context.meta
    return (meta.model_dump() if hasattr(meta, "model_dump") else dict(meta or {})).get("trace_id")


def _span(ctx, tool, started, args, result):
    os.makedirs(os.path.dirname(SPANS), exist_ok=True)
    with open(SPANS, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.datetime.now().astimezone().isoformat(timespec="milliseconds"),
                            "trace_id": _trace_id(ctx), "server": "policy-docs", "tool": tool,
                            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                            "args": args, "result": result}, ensure_ascii=False) + "\n")


def _policy(policy_number):
    p = _policies.get(policy_number)
    if p is None:
        raise ToolError("policy %r not found: policy numbers look like HP-460101 (household) or DF-460134 "
                        "(dwelling-fire); take it from the claim record." % policy_number)
    return p


def _date(text, name="loss_date"):
    try:
        return datetime.date.fromisoformat(text)
    except (TypeError, ValueError):
        raise ToolError("%s %r is not a date: use YYYY-MM-DD, e.g. 2024-08-11." % (name, text))


@mcp.tool()
def policy_lookup(policy_number: Annotated[str, Field(description="Policy number from the claim record, e.g. HP-460101.")],
                  ctx: Context) -> dict:
    """Look up a policy by number: product, policy line, and every term on record with its start and end dates and the endorsement forms attached in that term, each with its edition (e.g. "HO-0304 ed. 03-24"). Does not say whether a given loss date is covered by a term - use coverage_in_force for that."""
    started = time.perf_counter()
    p = _policy(policy_number)
    out = {"policy_number": p["policy_number"], "product": p["product"], "policy_line": p["policy_line"],
           "terms": [{"term_start": t["term_start"], "term_end": t["term_end"], "forms": t["forms"]}
                     for t in p["terms"]]}
    _span(ctx, "policy_lookup", started, {"policy_number": policy_number}, {"terms": len(out["terms"])})
    return out


@mcp.tool()
def coverage_in_force(policy_number: Annotated[str, Field(description="Policy number from the claim record.")],
                      loss_date: Annotated[str, Field(description="The claim's date of loss, YYYY-MM-DD.")],
                      ctx: Context) -> dict:
    """Check whether the policy had a term in force on the loss date. IN_FORCE returns that term: its dates, the forms attached with their editions, the policy deductible, any per-form deductibles (which replace the policy deductible for that form's losses), the sub-limits, and the coverage limits. NOT_IN_FORCE returns the terms on record so the gap can be referred. This is the record of what was in force - it does not decide whether the loss is payable."""
    started = time.perf_counter()
    p = _policy(policy_number)
    day = _date(loss_date)
    term = next((t for t in p["terms"] if _date(t["term_start"], "term_start") <= day
                 <= _date(t["term_end"], "term_end")), None)
    if term is None:
        out = {"status": "NOT_IN_FORCE", "policy_number": policy_number, "loss_date": loss_date,
               "terms_on_record": [{"term_start": t["term_start"], "term_end": t["term_end"]} for t in p["terms"]]}
    else:
        out = {"status": "IN_FORCE", "policy_number": policy_number, "loss_date": loss_date,
               "policy_line": p["policy_line"], **term}
    _span(ctx, "coverage_in_force", started, {"policy_number": policy_number, "loss_date": loss_date},
          {"status": out["status"]})
    return out


def _form(raw):
    """Week 9 behaviour: 'HO-0304' or 'HO-0304 ed. 03-24' -> 'HO-0304' (the edition is dropped)."""
    head = re.sub(r"\s+ed\.?\s*[\d-]+$", "", raw.strip())
    if head in FORMS:
        return head
    guess = "%s-%s" % (re.sub(r"[^A-Z]", "", head.upper()), re.sub(r"\D", "", head))
    raise ToolError("form %r is not in the endorsement library, so nothing was searched. Form numbers look like "
                    "HO-0820.%s Forms held: %s." % (raw, " Did you mean %s?" % guess if guess in FORMS else "",
                                                    ", ".join(FORMS)))


def _resolve(raw, day):
    """'HO-0304 ed. 03-24' -> 'HO-0304', after checking the edition in code: it must be in the
    library and in force on the loss date. 'HO-0304' alone resolves to whichever edition is in
    force on the loss date. Either way the date filter below returns only that edition."""
    head = re.sub(r"\s+ed\.?\s*[\d-]+$", "", raw.strip())
    form = _form(head)
    found = re.search(r"ed\.?\s*([\d-]+)$", raw.strip())
    if not found:
        return form
    edition = found.group(1)
    eds = {(c["edition"], c["in_force_from"], c["in_force_to"]) for c in _chunks.values() if c["form_number"] == form}
    match = next((e for e in eds if e[0] == edition), None)
    if match is None:
        raise ToolError("%s ed. %s is not in the wording library (it holds %s). No other edition of %s may be used "
                        "in its place: refer with assessment WORDING_NOT_ON_FILE." % (
                            form, edition, ", ".join("ed. %s" % e[0] for e in sorted(eds)), form))
    if not match[1] <= day <= match[2]:
        raise ToolError("%s ed. %s is in force %s to %s, not on the loss date %s: the wording in force on that date "
                        "is not in the library. Refer with assessment WORDING_NOT_ON_FILE." % (
                            form, edition, _iso(match[1]), _iso(match[2]), _iso(day)))
    return form


@mcp.tool()
def search_policy(
    query: Annotated[str, Field(description="Plain words for the one fact you need, e.g. 'surface water through a door'.")],
    loss_date: Annotated[str, Field(description="The claim's date of loss, YYYY-MM-DD. Only wording in force on this date is searched.")],
    ctx: Context,
    form_numbers: Annotated[Optional[list[str]], Field(
        description="The forms on the policy term, as coverage_in_force lists them, e.g. ['HO-0304 ed. 03-24']. Omit to search every form.")] = None,
    product: Annotated[Optional[Literal["homeowners", "dwelling-fire"]], Field(
        description="Restrict to one policy line.")] = None,
) -> dict:
    """Search the endorsement wording in force on the loss date and return up to 4 passages, best match first, each with its chunk id, form, edition and in-force dates. The edition is resolved against the loss date in code: an edition that is not in force on that date, or not in the library, is never returned - the call says so instead. Cite the chunk id of every passage you rely on. Never returns claim facts or policy records."""
    started = time.perf_counter()
    day = int(_date(loss_date).strftime("%Y%m%d"))
    where = [{"in_force_from": {"$lte": day}}, {"in_force_to": {"$gte": day}}]
    if form_numbers:
        forms = [_resolve(f, day) for f in form_numbers]
        where.append({"form_number": forms[0]} if len(forms) == 1 else {"form_number": {"$in": forms}})
    if product:
        where.append({"policy_line": product})
    hits = dense_search(query, k=4, where={"$and": where})
    out = {"loss_date": loss_date,
           "passages": [{"chunk_id": h["chunk_id"], "form": h["meta"]["form_number"], "edition": h["meta"]["edition"],
                         "in_force": "%s to %s" % (_iso(h["meta"]["in_force_from"]), _iso(h["meta"]["in_force_to"])),
                         "text": h["text"]} for h in hits]}
    _span(ctx, "search_policy", started, {"query": query, "loss_date": loss_date, "form_numbers": form_numbers,
                                          "product": product},
          {"context_ids": [p["chunk_id"] for p in out["passages"]]})
    return out


def _iso(n):
    return "open" if n == 99991231 else "%04d-%02d-%02d" % (n // 10000, n // 100 % 100, n % 100)


@mcp.tool()
def refer_to_adjuster(
    claim_id: Annotated[str, Field(description="Claim number, CLM-YYYY-NNNNN.")],
    policy_number: str,
    loss_date: Annotated[str, Field(description="The loss date the wording was resolved against, YYYY-MM-DD.")],
    in_force: Literal["IN_FORCE", "NOT_IN_FORCE"],
    assessment: Annotated[Literal["EXCLUSION_APPEARS_TO_APPLY", "NO_EXCLUSION_TRIGGERED", "FACTS_NEEDED",
                                  "POLICY_NOT_IN_FORCE", "WORDING_NOT_ON_FILE"], Field(
        description="What the wording and facts indicate for the adjuster. Not a decision.")],
    wording: Annotated[list[str], Field(description="Forms with edition the assessment rests on, e.g. ['HO-0304 ed. 03-24']; empty if none.")],
    citations: Annotated[list[str], Field(
        description="One entry per clause relied on: the chunk id search_policy returned, a colon, and what it is - e.g. 'HO-0304_03-24#05: E-15' or 'HO-0820_05-24#03: HO-0820 Clause 2'.")],
    deductible: Annotated[Optional[int], Field(description="The deductible that applies to this loss, dollars.")],
    sub_limit: Annotated[Optional[int], Field(description="The sub-limit that caps this loss, dollars; null if none applies.")],
    policy_limit: Annotated[Optional[int], Field(description="The limit of the coverage this loss falls under, dollars.")],
    facts: Annotated[list[str], Field(description="The facts from the notes the adjuster must weigh.")],
    note: Annotated[str, Field(description="Two to four sentences for the adjuster, each ending with the chunk id it relies on in square brackets.")],
    ctx: Context,
) -> dict:
    """Refer the claim to an adjuster - the only way to finish a triage. Hands over the wording the claim turns on (cited by chunk id, which names the edition), the facts, and the three separate numbers: deductible, sub-limit, policy limit. The adjuster decides; this tool refuses any payload that states a coverage decision, including the words "covered" or "not covered"."""
    started = time.perf_counter()
    payload = {"claim_id": claim_id, "policy_number": policy_number, "loss_date": loss_date, "in_force": in_force,
               "assessment": assessment, "wording": wording, "citations": [_citation(c) for c in citations],
               "deductible": deductible, "sub_limit": sub_limit, "policy_limit": policy_limit,
               "facts": facts, "note": note}
    said = [k for k, v in payload.items() if COVERED.search(json.dumps(v))]
    if said:
        raise ToolError("A referral cannot state a coverage decision: the word 'covered' appears in %s. Say what "
                        "the wording and facts indicate (assessment, citations, facts) and refer - the adjuster "
                        "decides." % ", ".join(said))
    _date(loss_date)
    unknown = [c["chunk_id"] for c in payload["citations"] if c["chunk_id"] not in _chunks]
    if unknown:
        raise ToolError("unknown chunk ids %s: cite chunk ids exactly as search_policy returned them." % unknown)
    # the PII line: names, addresses and injuries never leave this server or reach disk
    tokens = set()
    for s in facts + [note]:
        tokens |= redact.name_tokens(s)
    payload["facts"] = [redact.redact(s, also=tokens)[0] for s in facts]
    payload["note"] = redact.redact(note, also=tokens)[0]
    rid = "REF-%s" % secrets.token_hex(4)
    links = [_link(c["chunk_id"], c["cites"], loss_date) for c in payload["citations"]]
    record = {"referral_id": rid, "queued_for": "claims adjuster", "trace_id": _trace_id(ctx), **payload,
              "citation_links": links}
    os.makedirs(REFERRALS, exist_ok=True)
    with open(os.path.join(REFERRALS, "%s.json" % claim_id), "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    with open(os.path.join(REFERRALS, "%s.md" % claim_id), "w", encoding="utf-8") as f:
        f.write(_markdown(record))
    _span(ctx, "refer_to_adjuster", started, {"claim_id": claim_id, "assessment": assessment},
          {"referral_id": rid, "cited": [c["chunk_id"] for c in payload["citations"]]})
    return {"referral_id": rid, "queued_for": "claims adjuster", "citation_links": links}


def _citation(text):
    """'HO-0304_03-24#05: E-15' -> {"chunk_id": ..., "cites": ...}. Plain strings, not a nested
    schema: Groq refused every tool call made against a $ref'd citation object."""
    chunk_id, _, cites = text.partition(":")
    return {"chunk_id": chunk_id.strip(), "cites": cites.strip()}


def _link(chunk_id, cites, loss_date):
    c = _chunks[chunk_id]
    return "[%s ed. %s - %s (in force %s to %s), resolved for loss date %s](../data/%s#L%d)" % (
        c["form_number"], c["edition"], cites, _iso(c["in_force_from"]), _iso(c["in_force_to"]), loss_date,
        c["source_file"], c["line_start"])


def _markdown(r):
    lines = ["# Referral %s - %s" % (r["referral_id"], r["claim_id"]), "",
             "Queued for: **claims adjuster** (no coverage decision is made here). Trace `%s`." % r["trace_id"], "",
             "| | |", "|---|---|",
             "| policy | %s |" % r["policy_number"], "| loss date | %s |" % r["loss_date"],
             "| in force on the loss date | %s |" % r["in_force"], "| assessment | %s |" % r["assessment"],
             "| wording resolved | %s |" % (", ".join(r["wording"]) or "none"),
             "| deductible | %s |" % r["deductible"], "| sub-limit | %s |" % r["sub_limit"],
             "| policy limit | %s |" % r["policy_limit"], "", "## Wording cited", ""]
    lines += ["- %s" % l for l in r["citation_links"]] or ["- none"]
    lines += ["", "## Facts for the adjuster", ""] + ["- %s" % f for f in r["facts"]]
    lines += ["", "## Note", "", r["note"], ""]
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()   # stdio
