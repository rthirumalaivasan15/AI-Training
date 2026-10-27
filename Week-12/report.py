"""Reports from the eval runs and their traces - no model calls.

    python app.py report after            # eval_report.md, trajectory.md, cost_10x.md
    python app.py report after before     # ... plus the before -> after comparison

eval_report.md   pass rate overall and per case mode with n, every assertion's failures,
                 the wrong-endorsement-version citation rate, the judge's agreement with the
                 reference decisions, and what the suite does not cover
trajectory.md    per case: the tool path, whether it is an accepted path, tool-choice
                 accuracy, outcome pass vs trajectory pass and the gap
cost_10x.md      cost per claim triaged by stage, and what breaks first in a hailstorm week
                 (18,000 FNOLs) - with the numbers, from Groq's own quota headers and 429s
"""
import os
import json
import math
import datetime
from collections import Counter, defaultdict

import llm
import tracer
import suite

HAIL_WEEK = 18_000
NORMAL_MONTH = 1_800


def load(tag):
    with open(os.path.join("runs", "eval_%s.jsonl" % tag), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def traces():
    return {r["trace_id"]: r for r in tracer.read()}


def pct(a, b):
    return 100.0 * a / b if b else 0.0


def nearest_rank(v, p):
    v = sorted(v)
    return v[max(1, math.ceil(p / 100 * len(v))) - 1] if v else 0


def wrong_edition(rows):
    with_cites = [r for r in rows if any(c["name"] == "edition" for c in r["checks"])
                  and next(c for c in r["checks"] if c["name"] == "edition")["detail"] != "every citation in force on %s"
                  % suite.CLAIMS[r["id"]]["date_of_loss"] or True]
    bad = [r for r in rows if not next(c for c in r["checks"] if c["name"] == "edition")["passed"]]
    return bad, len(rows)


# --- trajectory -----------------------------------------------------------------------
CLAIM_TOOLS = {"get_claim_status", "get_adjuster_notes"}


def trajectory(row, trace, case):
    calls = [s for s in trace["spans"] if s["kind"] in ("tool", "retrieval")]
    names = [s["name"] for s in calls]
    seen, ok_calls, reasons = set(), 0, []
    not_in_force = case["in_force"] == "NOT_IN_FORCE"
    for s in calls:
        n, good = s["name"], True
        if n in CLAIM_TOOLS:
            good = "coverage_in_force" not in seen or n not in seen
        elif n == "policy_lookup":
            good = "get_claim_status" in seen
        elif n == "coverage_in_force":
            good = "get_claim_status" in seen
        elif n == "search_policy":
            good = "coverage_in_force" in seen and not not_in_force
        elif n == "refer_to_adjuster":
            good = "coverage_in_force" in seen
        if not good:
            reasons.append("%s out of order or not needed" % n)
        ok_calls += good
        seen.add(n)
    searches = names.count("search_policy")
    lo = 0 if (not_in_force or case["mode"] == "wording-not-on-file" or case["mode"] == "wrong-property") else 1
    hi = 0 if not_in_force else 3
    if not lo <= searches <= hi:
        reasons.append("%d searches, accepted %d-%d" % (searches, lo, hi))
    if names[-1:] != ["refer_to_adjuster"]:
        reasons.append("does not end in refer_to_adjuster")
    dol = suite.CLAIMS[case["claim_id"]]["date_of_loss"]
    if not any(s["name"] == "coverage_in_force" and (s.get("args") or {}).get("loss_date") == dol for s in calls):
        reasons.append("in-force not checked against the loss date")
    if lo >= 1:
        term = suite.term_for(suite.CLAIMS[case["claim_id"]])
        allowed = {tuple(f.split(" ed. ")) for f in (term or {}).get("forms", [])}
        got = [cid for s in calls for cid in s.get("context_ids", [])]
        if not any((suite.CHUNKS[c]["form_number"], suite.CHUNKS[c]["edition"]) in allowed for c in got if c in suite.CHUNKS):
            reasons.append("never retrieved the edition in force")
    return {"path": names, "calls": len(calls), "ok_calls": ok_calls, "trajectory_pass": not reasons,
            "reasons": reasons}


def eval_report(tag, before=None):
    rows, tr = load(tag), traces()
    cases = {c["id"]: c for c in suite.load_cases()}
    n = len(rows)
    out = ["# eval_report.md - the integrated system, run `%s`" % tag, "",
           "One command: `python app.py eval %s`. Every case runs through the same entry point, agent, MCP servers "
           "and tracing as production. PASS = all 8 assertions and the Week 6 judge." % tag, ""]
    passed = sum(r["pass"] for r in rows)
    bad_ed, _ = wrong_edition(rows)
    agree = sum((r["judge"] or "NONE") == r["reference_label"] for r in rows if r["judge"])
    judged = sum(1 for r in rows if r["judge"])
    out += ["**Pass rate: %d/%d (%.0f%%).** Wrong-endorsement-version citation rate: **%d/%d (%.0f%%)**. "
            "Judge agreement with the reference decisions: **%d/%d = %.0f%%**." % (
                passed, n, pct(passed, n), len(bad_ed), n, pct(len(bad_ed), n), agree, judged, pct(agree, judged)), ""]
    if before:
        b = {r["id"]: r for r in load(before)}
        common = [r for r in rows if r["id"] in b]
        b_bad = sum(not next(c for c in b[r["id"]]["checks"] if c["name"] == "edition")["passed"] for r in common)
        a_bad = sum(not next(c for c in r["checks"] if c["name"] == "edition")["passed"] for r in common)
        out += ["## Before -> after on the same %d cases (`%s` -> `%s`)" % (len(common), before, tag), "",
                "| case | mode | before | after |", "|---|---|---|---|"]
        for r in common:
            fb = [c["name"] for c in b[r["id"]]["checks"] if not c["passed"]] + ([] if b[r["id"]]["judge"] == "PASS" else ["judge"])
            fa = [c["name"] for c in r["checks"] if not c["passed"]] + ([] if r["judge"] == "PASS" else ["judge"])
            out.append("| %s | %s | %s | %s |" % (r["id"], r["mode"], "PASS" if b[r["id"]]["pass"] else "FAIL: " + ", ".join(fb),
                                                "PASS" if r["pass"] else "FAIL: " + ", ".join(fa)))
        out += ["", "**Wrong-endorsement-version citation rate: %d/%d -> %d/%d. Pass: %d/%d -> %d/%d.**" % (
            b_bad, len(common), a_bad, len(common), sum(b[r["id"]]["pass"] for r in common), len(common),
            sum(r["pass"] for r in common), len(common)), ""]
    out += ["## Pass rate per case mode", "", "| mode | n | pass | rate |", "|---|---|---|---|"]
    by = defaultdict(list)
    for r in rows:
        by[r["mode"]].append(r)
    for m, rs in sorted(by.items()):
        out.append("| %s | %d | %d | %.0f%% |" % (m, len(rs), sum(x["pass"] for x in rs), pct(sum(x["pass"] for x in rs), len(rs))))
    fails = Counter(c["name"] for r in rows for c in r["checks"] if not c["passed"])
    out += ["", "## Assertion failures (of %d cases)" % n, "", "| assertion | failed |", "|---|---|"]
    for name in ("no_covered", "referred", "in_force_checked", "assessment", "cites", "edition", "loss_date", "numbers"):
        out.append("| %s | %d |" % (name, fails.get(name, 0)))
    out.append("| judge FAIL | %d |" % sum(1 for r in rows if r["judge"] != "PASS"))
    out += ["", "## Every case", "", "| case | mode | assessment | assertions failed | judge | pass | trace |",
            "|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append("| %s | %s | %s | %s | %s | %s | `%s` |" % (
            r["id"], r["mode"], r["assessment"], ", ".join(c["name"] for c in r["checks"] if not c["passed"]) or "-",
            r["judge"], "PASS" if r["pass"] else "FAIL", r["trace_id"]))
    out += ["", "## Judge agreement", "",
            "The Week 6 judge (prompt sha-checked, `gpt-oss-20b`), re-run on the integrated outputs with the integrated "
            "wording library. Its verdict is compared with a reference label per case: PASS when the referral's "
            "assessment, citation and edition match the reference decision in `evals/cases.jsonl`. Those decisions "
            "were written from the wording before any integrated run; they are not fresh hand labels taken on these "
            "outputs. Agreement **%d/%d = %.0f%%** (target 85%%)." % (agree, judged, pct(agree, judged)), "",
            "## What this suite does NOT cover", "",
            "- **Motor claims**: there is no motor wording or motor case at all; everything here is household.",
            "- **Real claim files**: 25 authored cases, not the brief's 500 anonymised files; no photo captions.",
            "- **Parse quality**: the wordings are clean text, so a badly parsed PDF schedule is never tested.",
            "- **Reproducibility over time**: one run per case at temperature 0; run-to-run variation is not measured "
            "here (it was 3 different positions in 3 runs on one Week 11 case).",
            "- **Payable amounts**: the system never computes a payout, so no case checks one.",
            "- **Adversarial input**: no prompt injection in the notes is tested.",
            "- **Human labels**: judge agreement is against reference decisions, not a person grading these outputs."]
    path = "eval_report.md" if not before else "eval_report.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out[:8]))
    return rows


def trajectory_report(tag):
    rows, tr = load(tag), traces()
    cases = {c["id"]: c for c in suite.load_cases()}
    res = []
    for r in rows:
        t = trajectory(r, tr[r["trace_id"]], cases[r["id"]])
        res.append((r, t))
    calls = sum(t["calls"] for _, t in res)
    ok = sum(t["ok_calls"] for _, t in res)
    out_pass = sum(r["pass"] for r, _ in res)
    traj_pass = sum(t["trajectory_pass"] for _, t in res)
    n = len(res)
    out = ["# trajectory.md - the integrated agent's paths, run `%s`" % tag, "",
           "**Tool-choice accuracy %d/%d = %.0f%%. Outcome pass %d/%d (%.0f%%), trajectory pass %d/%d (%.0f%%): "
           "gap %+.0f points.**" % (ok, calls, pct(ok, calls), out_pass, n, pct(out_pass, n), traj_pass, n,
                                    pct(traj_pass, n), pct(out_pass, n) - pct(traj_pass, n)), "",
           "Accepted path: the claim tools first; `coverage_in_force` with the claim's loss date before any search or "
           "referral; 1-3 searches when the policy is in force and wording is on file (0 when it is not in force, 0-3 "
           "when the wording is not on file); at least one retrieved chunk of an edition the policy term carries; end "
           "in `refer_to_adjuster`. Tool-choice accuracy counts every call that was acceptable at that point.", "",
           "| case | outcome | trajectory | path | why the path fails |", "|---|---|---|---|---|"]
    for r, t in res:
        out.append("| %s | %s | %s | %s | %s |" % (r["id"], "PASS" if r["pass"] else "FAIL",
                                                 "PASS" if t["trajectory_pass"] else "FAIL", " > ".join(t["path"]),
                                                 "; ".join(t["reasons"]) or "-"))
    with open("trajectory.md", "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(out[2])


def cost_report(tag):
    rows, tr = load(tag), traces()
    ts = [tr[r["trace_id"]] for r in rows]
    n = len(ts)
    cost = [t["cost_usd"] for t in ts]
    tok = [t["tokens"] for t in ts]
    laps = [t["laps"] for t in ts]
    stage = {s: sum(t["cost_by_stage"][s]["cost_usd"] for t in ts) / n for s in ("generation", "retrieval", "tools")}
    active = [t["active_s"] for t in ts]
    wall = [t["latency_s"] for t in ts]
    limits = ts[-1]["rate_limits"]
    tpm, rpd = limits.get("limit-tokens"), limits.get("limit-requests")
    hits = Counter(h["unit"] for t in ts for h in t["rate_limited"])
    tpd = next((h["limit"] for t in ts for h in t["rate_limited"] if h["unit"] == "TPD"), None) or 200_000
    mean_tok, mean_laps, mean_cost = sum(tok) / n, sum(laps) / n, sum(cost) / n
    hail_day = HAIL_WEEK / 7
    normal_day = NORMAL_MONTH / 30
    per_min = hail_day / (10 * 60)                    # a 10-hour working day of FNOLs
    out = ["# cost_10x.md - cost per claim triaged, and what breaks first in a hailstorm week", "",
           "From %d integrated triages (run `%s`), `gpt-oss-120b` on Groq at $%.2f / $%.2f per 1M input / output tokens." % (
               n, tag, llm.PRICE_IN, llm.PRICE_OUT), "",
           "| per claim triaged | mean | p50 | max |", "|---|---|---|---|",
           "| cost | $%.5f | $%.5f | $%.5f |" % (mean_cost, nearest_rank(cost, 50), max(cost)),
           "| tokens | %s | %s | %s |" % (format(round(mean_tok), ","), format(nearest_rank(tok, 50), ","), format(max(tok), ",")),
           "| model calls (laps) | %.1f | %d | %d |" % (mean_laps, nearest_rank(laps, 50), max(laps)),
           "| active latency | %.1f s | %.1f s | %.1f s (p99 = max at n=%d) |" % (sum(active) / n, nearest_rank(active, 50), max(active), n),
           "| wall latency incl. rate-limit waits | %.1f s | %.1f s | %.1f s |" % (sum(wall) / n, nearest_rank(wall, 50), max(wall)),
           "", "Cost by stage, mean per claim: generation $%.5f (%.0f%%), retrieval-carried tokens $%.5f (%.0f%%), "
           "tool results $%.5f (%.0f%%)." % (stage["generation"], pct(stage["generation"], mean_cost), stage["retrieval"],
                                            pct(stage["retrieval"], mean_cost), stage["tools"], pct(stage["tools"], mean_cost)),
           "", "## A hailstorm week: 18,000 FNOLs", "",
           "| | normal (1,800 a month) | hailstorm week | limit on this key | breaks? |", "|---|---|---|---|---|",
           "| claims per day | %.0f | %s | - | - |" % (normal_day, format(round(hail_day), ",")),
           "| tokens per day | %s | %s | %s TPD | **yes, %.0fx over - already %.1fx over at normal volume** |" % (
               format(round(normal_day * mean_tok), ","), format(round(hail_day * mean_tok), ","), format(tpd, ","),
               hail_day * mean_tok / tpd, normal_day * mean_tok / tpd),
           "| model calls per day | %s | %s | %s RPD | yes, %.0fx over |" % (
               format(round(normal_day * mean_laps), ","), format(round(hail_day * mean_laps), ","), format(rpd, ","),
               hail_day * mean_laps / rpd),
           "| tokens per minute (10-hour day) | %s | %s | %s TPM | yes, %.0fx over |" % (
               format(round(normal_day / 600 * mean_tok), ","), format(round(per_min * mean_tok), ","), format(tpm, ","),
               per_min * mean_tok / tpm),
           "| cost | $%.2f a day | $%.2f a day, $%s a week | - | no |" % (normal_day * mean_cost, hail_day * mean_cost,
                                                                  format(round(HAIL_WEEK * mean_cost, 2), ",")),
           "", "**First to break: the daily token cap.** %s tokens a day against %s - and it breaks before any hailstorm: "
           "normal volume alone needs %.1fx the cap. Cost is not the problem ($%s for the whole hailstorm week)." % (
               format(round(hail_day * mean_tok), ","), format(tpd, ","), normal_day * mean_tok / tpd,
               format(round(HAIL_WEEK * mean_cost, 2), ",")),
           "", "During these %d runs the key met %s rate-limit responses (%s). TPM and RPD are Groq's own response "
           "headers; the daily token cap is not in the headers and shows only in a TPD 429 (Week 11 measured it at "
           "200,000 on this key)." % (n, sum(hits.values()), ", ".join("%s x%d" % kv for kv in hits.items()) or "none"),
           "", "## The plan, ranked and costed", "",
           "1. **Move off the free tier** (the binding constraint at every volume): pay-as-you-go on the same model; at "
           "$%.5f a claim a hailstorm week is about $%s. Re-measure TPM/RPD from the new headers before trusting it." % (
               mean_cost, format(round(HAIL_WEEK * mean_cost, 2), ",")),
           "2. **Cut laps per claim** (%.1f now): fetch the claim, notes and in-force term in the first lap - every lap "
           "re-sends the system prompt and six tool definitions, so one lap fewer saves about %.0f%% of tokens." % (
               mean_laps, 100.0 / mean_laps),
           "3. **Queue and prioritise** at catastrophe volume: triage is not real-time for an adjuster's first 20 "
           "minutes; a queue that drains under the token cap turns 429s into latency the adjuster does not see."]
    with open("cost_10x.md", "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(out[-9])


def main(tag, before=None):
    eval_report(tag, before)
    trajectory_report(tag)
    cost_report(tag)
