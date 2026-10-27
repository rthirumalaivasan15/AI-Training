"""The eval suite, run against the INTEGRATED system - one command: python app.py eval <tag>

Every case goes through app.handle - the same entry point, agent, MCP servers and
tracing as production (traces land in logs/ under user "eval"). Then, per case:

1. Assertions - deterministic, free, run first:
   no_covered        the word "covered" appears nowhere in the referral
   referred          the run ended with an accepted refer_to_adjuster
   in_force_checked  coverage_in_force was called with the claim's own loss date, and the
                     referral's in_force matches the policy record
   assessment        the referral's assessment is one the reference decision allows
   cites             a required exclusion code / clause / form is cited
   edition           every cited chunk is the edition the policy term carries AND in force
                     on the loss date - the wrong-endorsement-version check
   loss_date         the wording was resolved against the claim's loss date
   numbers           deductible, sub-limit and policy limit each match the record for this loss
2. The Week 6 judge (judge.py) on the referral, with the claim's notes and policy term.

PASS = every assertion and judge PASS. A case already in runs/eval_<tag>.jsonl is
never run again; delete the file to re-run a tag.
"""
import os
import re
import json
import datetime

import app
import judge
import prompts

CASES = os.path.join("evals", "cases.jsonl")
COVERED = re.compile(r"\b(?:un)?covered\b", re.I)
HYPHENS = re.compile("[‐‑‒–—−]")

with open("chunks.jsonl", encoding="utf-8") as f:
    CHUNKS = {c["chunk_id"]: c for c in (json.loads(l) for l in f if l.strip())}
with open(os.path.join("claims_system", "claims.json"), encoding="utf-8") as f:
    CLAIMS = {c["claim_id"]: c for c in json.load(f)}
with open(os.path.join("policy_admin", "policies.json"), encoding="utf-8") as f:
    POLICIES = json.load(f)


def load_cases(modes=None):
    with open(CASES, encoding="utf-8") as f:
        cases = [json.loads(l) for l in f if l.strip()]
    return [c for c in cases if not modes or c["mode"] in modes]


def term_for(claim):
    dol = claim["date_of_loss"]
    return next((t for t in POLICIES[claim["policy_number"]]["terms"]
                 if t["term_start"] <= dol <= t["term_end"]), None)


def edition_violations(referral, claim):
    """Cited chunks that are not (a) an edition the policy term carries, and (b) in force on the loss date."""
    term = term_for(claim)
    allowed = {tuple(f.split(" ed. ")) for f in (term or {}).get("forms", [])}
    dol = int(claim["date_of_loss"].replace("-", ""))
    bad = []
    for c in (referral or {}).get("citations", []):
        ch = CHUNKS.get(c.get("chunk_id"))
        if ch is None:
            bad.append(c.get("chunk_id"))
        elif (ch["form_number"], ch["edition"]) not in allowed or not ch["in_force_from"] <= dol <= ch["in_force_to"]:
            bad.append(c["chunk_id"])
    return bad


def checks(case, rec):
    r = rec.get("referral")
    claim = CLAIMS[case["claim_id"]]
    out = []

    def add(name, ok, detail):
        out.append({"name": name, "passed": bool(ok), "detail": detail})

    blob = json.dumps(r or {}, ensure_ascii=False)
    hit = COVERED.search(blob)
    add("no_covered", not hit, "said %r" % hit.group(0) if hit else "never said covered")
    add("referred", r is not None, "referral %s" % ((r or {}).get("referral_id") or "missing - %s" % rec["stop_reason"]))
    calls = [s for s in rec["spans"] if s["kind"] in ("tool", "retrieval") and s["name"] == "coverage_in_force"]
    checked = any((s.get("args") or {}).get("loss_date") == claim["date_of_loss"] for s in calls)
    add("in_force_checked", checked and r is not None and r.get("in_force") == case["in_force"],
        "coverage_in_force(%s) %s; referral says %s, record %s" % (
            claim["date_of_loss"], "called" if checked else "NOT called with the loss date",
            (r or {}).get("in_force"), case["in_force"]))
    add("assessment", r is not None and r.get("assessment") in case["assessment_in"],
        "%s, expected %s" % ((r or {}).get("assessment"), " or ".join(case["assessment_in"])))
    cited = HYPHENS.sub("-", " ".join("%s %s" % (c.get("chunk_id", ""), c.get("cites", "")) for c in (r or {}).get("citations", [])))
    need = case["must_cite_any"]
    add("cites", not need or any(code in cited for code in need),
        "cited %r; needs one of %s" % (cited[:120], need) if need else "no citation required")
    bad = [] if case["in_force"] == "NOT_IN_FORCE" else edition_violations(r, claim)
    add("edition", not bad, "wrong edition for the loss date: %s" % bad if bad else "every citation in force on %s"
        % claim["date_of_loss"])
    add("loss_date", r is not None and r.get("loss_date") == claim["date_of_loss"],
        "resolved for %s, loss date %s" % ((r or {}).get("loss_date"), claim["date_of_loss"]))
    wrong = []
    for k in ("deductible", "sub_limit", "policy_limit"):
        if case[k] is not None and (r or {}).get(k) != case[k]:
            wrong.append("%s %s (record %s)" % (k, (r or {}).get(k), case[k]))
    add("numbers", r is not None and not wrong, "; ".join(wrong) if wrong else "deductible %s, sub-limit %s, limit %s"
        % ((r or {}).get("deductible"), (r or {}).get("sub_limit"), (r or {}).get("policy_limit")))
    return out


def judge_case(claim, r):
    term = term_for(claim)
    record = ("Policy %s (%s); term in force on the loss date: %s." % (
        claim["policy_number"], POLICIES[claim["policy_number"]]["policy_line"],
        "%s to %s, forms %s, deductible %s, sub-limits %s, limits %s" % (
            term["term_start"], term["term_end"], ", ".join(term["forms"]), term["deductible"], term["sub_limits"],
            term["limits"]) if term else "NONE - no term covers the loss date"))
    notes = "%s. DOL %s. %s First notice: %s %s" % (claim["claim_id"], claim["date_of_loss"], record,
                                                    claim["first_notice"], " ".join(claim["adjuster_notes"]))
    summary = "\n".join([
        "CLAIM NUMBER: %s" % (r or {}).get("claim_id"), "DATE OF LOSS: %s" % (r or {}).get("loss_date"),
        "POLICY FORMS: %s" % ", ".join((r or {}).get("wording", [])) or "NONE",
        "COVERAGE POSITION: %s" % (r or {}).get("assessment"),
        "GROUNDS: %s" % ", ".join("%s (%s)" % (c.get("cites"), c.get("chunk_id")) for c in (r or {}).get("citations", [])),
        "DEDUCTIBLE / SUB-LIMIT / POLICY LIMIT: %s / %s / %s" % ((r or {}).get("deductible"), (r or {}).get("sub_limit"),
                                                                (r or {}).get("policy_limit")),
        "REASONING: %s" % (r or {}).get("note"), "NEXT STEP: referred to a claims adjuster for the decision."])
    reply, tokens = judge.ask(judge.render(judge.template(), {"notes": notes}, summary))
    v, reason = judge.parse(reply)
    if v is None:                      # Week 6 rule: one retry, then recorded as unparsed
        reply, more = judge.ask(judge.render(judge.template(), {"notes": notes}, summary))
        tokens += more
        v, reason = judge.parse(reply)
    return v, reason, tokens


async def run(tag, modes=None):
    path = os.path.join("runs", "eval_%s.jsonl" % tag)
    os.makedirs("runs", exist_ok=True)
    done = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            done = {r["id"]: r for r in (json.loads(l) for l in f if l.strip())}
    cases = load_cases(modes)
    for case in cases:
        if case["id"] in done:
            continue
        rec = await app.handle(case["claim_id"], user="eval", log=lambda l: None)
        cs = checks(case, rec)
        asserts_ok = all(c["passed"] for c in cs)
        v, reason, jt = judge_case(CLAIMS[case["claim_id"]], rec.get("referral")) if rec.get("referral") else (None, "no referral", 0)
        row = {"id": case["id"], "mode": case["mode"], "tag": tag, "trace_id": rec["trace_id"],
               "prompt_version": rec["prompt_version"], "prompt_sha": rec["prompt_sha"],
               "assessment": (rec.get("referral") or {}).get("assessment"), "checks": cs, "asserts_ok": asserts_ok,
               "judge": v, "judge_reason": reason, "judge_tokens": jt,
               "reference_label": "PASS" if all(c["passed"] for c in cs if c["name"] in ("assessment", "cites", "edition"))
               else "FAIL",
               "pass": asserts_ok and v == "PASS", "tokens": rec["tokens"], "cost_usd": rec["cost_usd"],
               "latency_s": rec["latency_s"], "active_s": rec["active_s"], "rate_limit_wait_s": rec["rate_limit_wait_s"],
               "rate_limited": rec["rate_limited"],
               "ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
        done[case["id"]] = row
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("  %-15s %-24s %-26s asserts %-4s judge %-4s -> %s  %s" % (
            case["id"], case["mode"], row["assessment"], "ok" if asserts_ok else "FAIL", v,
            "PASS" if row["pass"] else "FAIL", "; ".join(c["name"] for c in cs if not c["passed"])), flush=True)
    rows = [done[c["id"]] for c in cases if c["id"] in done]
    print("\nEVAL %s - prompt %s (%s) - %d/%d pass" % (tag.upper(), prompts.active(), prompts.sha(prompts.active()),
                                                      sum(r["pass"] for r in rows), len(rows)))
    return rows
