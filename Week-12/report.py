"""Reports from the eval runs and their traces - no model calls.

    python app.py report after            # eval_report.md, taxonomy.md, trajectory.md, cost_10x.md
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
# seam 11: refer_to_adjuster checks every citation against the policy term from here on. A case whose
# trace started earlier ran without that gate (the servers start fresh per request).
GATE_SINCE = "2026-10-27T18:19:44+05:30"


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
    total = len(cases)
    gated = [r for r in rows if tr[r["trace_id"]]["ts"] >= GATE_SINCE]
    out += ["**Cases run: %d of %d%s.** %d ran before the edition gate in `refer_to_adjuster` (seam 11, %s), "
            "%d after it." % (n, total, "" if n == total else " - the run is still going; this report is rebuilt "
                              "from whatever has finished", n - len(gated), GATE_SINCE[:16].replace("T", " "),
                              len(gated)), ""]
    out += ["**Pass rate: %d/%d (%.0f%%).** Wrong-endorsement-version citation rate: **%d/%d (%.0f%%)**. "
            "Judge agreement with the reference decisions: **%d/%d = %.0f%%**." % (
                passed, n, pct(passed, n), len(bad_ed), n, pct(len(bad_ed), n), agree, judged, pct(agree, judged)), ""]
    if os.path.exists(os.path.join("runs", "eval_gate.jsonl")):
        g = {r["id"]: r for r in load("gate")}
        fin = [g.get(r["id"], r) for r in rows]
        out += ["With the cases that ran before the edition gate re-run (`gate`): **pass %d/%d (%.0f%%), wrong-endorsement-"
                "version citation rate %d/%d (%.0f%%).**" % (
                    sum(r["pass"] for r in fin), n, pct(sum(r["pass"] for r in fin), n), len(wrong_edition(fin)[0]), n,
                    pct(len(wrong_edition(fin)[0]), n)), ""]
    if before:
        b = {r["id"]: r for r in load(before)}
        g = {r["id"]: r for r in load("gate")} if os.path.exists(os.path.join("runs", "eval_gate.jsonl")) else {}
        common = [r for r in rows if r["id"] in b]
        # the final state of each case: its `gate` re-run if it has one, else its `after` row
        final = {r["id"]: g.get(r["id"], r) for r in common}

        def bad(row):
            return not next(c for c in row["checks"] if c["name"] == "edition")["passed"]

        def cell(row):
            f = [c["name"] for c in row["checks"] if not c["passed"]] + ([] if row["judge"] == "PASS" else ["judge"])
            return "PASS" if row["pass"] else "FAIL: " + ", ".join(f)

        out += ["## Before -> after on the same %d cases (`%s` -> `%s`%s)" % (
                    len(common), before, tag, " -> `gate`" if g else ""), "",
                "`gate` re-runs a case that ran before the seam-11 edition check in `refer_to_adjuster` existed; "
                "every other case in `%s` already ran with it." % tag if g else "", "",
                "| case | mode | before | after | after, with the edition gate |", "|---|---|---|---|---|"]
        for r in common:
            out.append("| %s | %s | %s | %s | %s |" % (r["id"], r["mode"], cell(b[r["id"]]), cell(r),
                                                     cell(g[r["id"]]) if r["id"] in g else
                                                     "not re-run yet" if bad(r) else
                                                     "not re-run: no wrong edition cited, nothing for the gate to refuse"))
        out += ["", "**Wrong-endorsement-version citation rate: %d/%d -> %d/%d -> %d/%d. Pass: %d/%d -> %d/%d -> "
                "%d/%d.**" % (sum(bad(b[r["id"]]) for r in common), len(common), sum(bad(r) for r in common),
                              len(common), sum(bad(final[r["id"]]) for r in common), len(common),
                              sum(b[r["id"]]["pass"] for r in common), len(common), sum(r["pass"] for r in common),
                              len(common), sum(final[r["id"]]["pass"] for r in common), len(common)), ""]
    rj = os.path.join("runs", "rejudge_%s.jsonl" % tag)
    if os.path.exists(rj):
        with open(rj, encoding="utf-8") as f:
            rr = [json.loads(l) for l in f if l.strip()]
        rr = [x for x in rr if x["judge_as_of_loss_date"]]
        a_all = sum(x["judge_all_editions"] == x["reference_label"] for x in rr)
        a_dol = sum(x["judge_as_of_loss_date"] == x["reference_label"] for x in rr)
        out += ["## Judge agreement, re-measured on the integrated outputs (`rejudge.py %s`)" % tag, "",
                "The same Week 6 judge on the same stored referrals, two ways. **Reading every edition in the library: "
                "%d/%d = %.0f%%. Reading only the wording in force on each loss date: %d/%d = %.0f%%.** Target 85%%." % (
                    a_all, len(rr), pct(a_all, len(rr)), a_dol, len(rr), pct(a_dol, len(rr))), "",
                "| case | reference | judge, every edition | judge, wording in force on the loss date |",
                "|---|---|---|---|"]
        out += ["| %s | %s | %s | %s |" % (x["id"], x["reference_label"], x["judge_all_editions"],
                                          x["judge_as_of_loss_date"]) for x in rr]
        out.append("")
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
    with open("eval_report.md", "w", encoding="utf-8") as f:
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


# --- taxonomy ------------------------------------------------------------------------
def _failed(row, name):
    return not next(c for c in row["checks"] if c["name"] == name)["passed"]


# (name, severity, where it comes from, test on one eval row + its case)
MODES = [
    ("A second edition crowds the one in force out of the top 4, so wording that is on file is reported as "
     "WORDING_NOT_ON_FILE", "High - the adjuster is told there is no wording and the exclusion is never put to them",
     "**NEW - created by integration**: no form had two editions until the 2025 HO-0304 joined the library",
     lambda r, c: r["assessment"] == "WORDING_NOT_ON_FILE" and "WORDING_NOT_ON_FILE" not in c["assessment_in"]),
    ("Cites an edition the policy did not carry on the loss date", "Critical - the brief's live wound: a loss "
     "assessed against wording that was not its contract", "Week 5 mode 3 (answers from whichever endorsement came "
     "back), now across editions", lambda r, c: _failed(r, "edition")),
    ("The judge fails a correct referral: it applies a newer edition to an older loss, or does not accept an "
     "assessment that is not a coverage position", "Medium - no claim is harmed, but the eval reports a correct "
     "system as broken", "**NEW - created by integration**: the Week 6 judge reads the whole library (one edition per "
     "form until now) and was validated on COVERED / DENIED summaries, not referrals (seams 6, 10)",
     lambda r, c: r["judge"] == "FAIL" and r["reference_label"] == "PASS"),
    ("The judge passes a referral the reference decision fails", "High - a wrong referral reaches the report as a "
     "pass", "Week 11 (the judge passed the planted wrong answer)",
     lambda r, c: r["judge"] == "PASS" and r["reference_label"] == "FAIL"),
    ("Misreads the notes: wrong assessment with the right wording", "High - the wrong exclusion question is put to "
     "the adjuster", "Week 5 modes 2 and 4",
     lambda r, c: _failed(r, "assessment") and r["assessment"] != "WORDING_NOT_ON_FILE" and not _failed(r, "edition")),
    ("Deductible, sub-limit and policy limit confused", "High - the number juniors mix up weekly, now in a referral",
     "Week 7", lambda r, c: _failed(r, "numbers")),
    ("Ends without a valid referral, or never checks in-force against the loss date", "Critical - nothing reaches "
     "the adjuster, or the term is assumed", "Week 7 / Week 9 agent stops",
     lambda r, c: _failed(r, "referred") or _failed(r, "in_force_checked") or _failed(r, "loss_date")),
]


def taxonomy_report(tag, before=None):
    cases = {c["id"]: c for c in suite.load_cases()}
    runs = [(before, load(before))] if before else []
    runs.append((tag, load(tag)))
    head = " | ".join("`%s` n=%d" % (t, len(rs)) for t, rs in runs)
    out = ["# taxonomy.md - the Week 5 taxonomy re-scored on the integrated system", "",
           "Built by `python app.py report %s%s` from the eval rows and their traces; a case can sit in more than one "
           "mode. Frequency is the share of the run's cases. Rebuilt whenever the run grows." % (
               tag, " " + before if before else ""), "",
           "| # | mode | origin | severity | %s | example trace |" % head,
           "|---|---|---|---|%s---|" % ("---|" * len(runs))]
    for i, (name, sev, origin, test) in enumerate(MODES, 1):
        cells, example = [], None
        for t, rs in runs:
            hit = [r for r in rs if test(r, cases[r["id"]])]
            cells.append("%d (%.0f%%)" % (len(hit), pct(len(hit), len(rs))))
            example = example if example and not hit else (hit[0]["trace_id"] if hit else example)
        out.append("| %d | %s | %s | %s | %s | %s |" % (i, name, origin, sev, " | ".join(cells),
                                                      "`%s`" % example if example else "not seen"))
    clean = [r for r in runs[-1][1] if not any(test(r, cases[r["id"]]) for _, _, _, test in MODES)]
    out += ["", "Clean in `%s`: %d of %d. Never seen in any run: the word \"covered\" in a referral - "
            "`refer_to_adjuster` refuses it in code, and `gates.py` replays that refusal." % (
                tag, len(clean), len(runs[-1][1])), "",
            "## Traces read by hand", "",
            "- `trc_c66b247d566d` (CLM-2024-30001, after): assertions all pass; the judge cited the 2025 Storm Ingress "
            "Allowance against an August 2024 loss. Mode 3 - seam 10.",
            "- `trc_d41d68b1a7ad` (CLM-2024-30032, after): `search_policy` was called with the bare form `HO-0415`, the "
            "seam-1 fix resolved it to ed. 01-24 (in force on the date) though the policy carries ed. 05-23. Mode 2 - "
            "seam 11, gate added to `refer_to_adjuster`.",
            "- The two `before` storm losses (CLM-2024-30001/30002): retrieval returned three 2025 chunks out of four, "
            "the 2024 E-15 row never reached the model, and it referred as WORDING_NOT_ON_FILE. Mode 1 - seam 1.",
            "- `trc_25e1c00926de` (CLM-2024-30011, after): a correct POLICY_NOT_IN_FORCE referral (term ended "
            "2024-09-30, loss 2024-10-12); the judge failed it because the policy number is not in the endorsement "
            "wording. Mode 3 - the judge has no idea what a referral without a coverage position is (seam 6).",
            "- `trc_351855794fb0` (CLM-2024-10008, after): FACTS_NEEDED, right assessment, but `policy_limit` left "
            "null where the record holds 300,000; the judge passed it, the `numbers` assertion did not. Mode 6 - the "
            "assertion caught what the judge missed."]
    with open("taxonomy.md", "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def main(tag, before=None):
    eval_report(tag, before)
    taxonomy_report(tag, before)
    trajectory_report(tag)
    cost_report(tag)
