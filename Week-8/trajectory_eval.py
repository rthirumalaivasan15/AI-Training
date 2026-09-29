"""Score the path the agent took, not just the answer it reached.

    python trajectory_eval.py before                 # score one run
    python trajectory_eval.py before after           # score both and diff them

Reads runs/traj_<tag>.jsonl (written by run_trace.py) and writes
trajectory_<tag>.csv per claim plus trajectory_summary.csv. No model calls, so a
run can be re-scored for free after the eval itself changes.

WHAT COUNTS AS A CORRECT PATH
Each case asserts a *set* of accepted tool sequences, not one sequence, because
more than one order is genuinely right:

  - get_claim runs first and once. Nothing can be decided before the claim and
    its notes are in hand.
  - search_policy runs at least once and may run up to three times. One search or
    three is a judgement call, not an error; what matters is that the wording
    which decides the claim was actually opened (DECISIVE below).
  - compute_payout is REQUIRED when the answer states a payable amount above
    zero, and OPTIONAL when the answer is DENIED (zero) or UNDETERMINED (null) -
    there is no arithmetic to do, and calling the tool to be told "0" is not a
    better path than not calling it.
  - a second compute_payout is accepted when an earlier one was refused: going
    back to the wording and retrying is the correction the refusal asks for, and
    scoring that as a wrong path would punish the agent for recovering.

accepted_sequences() enumerates that set in code; report() prints it.

ATTEMPTED vs LANDED
A tool call the tool itself refused did not happen to the claim. Mode counts are
of calls that landed, so a mitigation that blocks bad arguments shows up as the
mode falling. The count of attempts is reported alongside it, unblocked, because
a blocked attempt still means the model tried - the behaviour did not change,
only its consequence.
"""
import os
import re
import csv
import sys
import json
import statistics
from itertools import product

CLAIMS = {c["claim_id"]: c for c in json.load(open("claims.json", encoding="utf-8"))}
CHUNKS = {r["chunk_id"]: r["text"] for r in
          (json.loads(l) for l in open("chunks.jsonl", encoding="utf-8"))}
FORMS = sorted({cid.split("_")[0] for cid in CHUNKS})
CODES = set(re.findall(r"\bE-\d{2}\b", " ".join(CHUNKS.values())))
MAX_SEARCHES = 3

# The wording each claim actually turns on. A run that reaches the right answer
# without opening these did not decide the claim, it guessed it.
DECISIVE = {
    "CLM-2024-10001": {"chunks": ["HO-0304_03-24#05", "HO-0304_03-24#02"],
                       "why": "E-17 table row, and the Clause 1(a) definition of sudden and accidental the exception turns on"},
    "CLM-2024-10002": {"chunks": ["HO-0304_03-24#05", "HO-0304_03-24#02"],
                       "why": "E-18 table row, and the Clause 1(a) definition of continuous seepage (over 14 days)"},
    "CLM-2024-10003": {"chunks": ["HO-0304_03-24#05", "HO-0304_03-24#02"],
                       "why": "E-15 table row, and the Clause 1(a) definition of surface water"},
    "CLM-2024-10004": {"chunks": ["HO-0304_03-24#05", "HO-0820_05-24#03"],
                       "why": "E-16 table row, and HO-0820 Clause 2, which both overrides it and caps the payout at 10,000"},
    "CLM-2024-10005": {"chunks": ["HO-0820_05-24#05", "HO-0820_05-24#03"],
                       "why": "E-51 table row with its power-outage exception, and HO-0820 Clause 2 for the limit and deductible"},
    "CLM-2024-10006": {"chunks": ["DP-0703_02-24#05", "DP-0703_02-24#06"],
                       "why": "E-61 table row with its exception, and Clause 4, which voids that exception on a late inspection"},
    "CLM-2024-10007": {"chunks": ["HO-0415_01-24#05"],
                       "why": "E-22 table row; it excludes denting absolutely, so no definition or exception is in play"},
    "CLM-2024-10008": {"chunks": ["HO-0304_03-24#05"],
                       "why": "with no notes the answer is UNDETERMINED, but the exclusions still have to be opened to know that nothing in them can be applied"},
    "CLM-2024-10009": {"chunks": ["HO-0509_06-24#03", "HO-0509_06-24#02"],
                       "why": "Clause 2 sublimit of 2,500, and the Clause 1(a) definition of home business the sublimit depends on"},
    "CLM-2024-10010": {"chunks": ["HO-0304_03-24#05", "HO-0304_03-24#02"],
                       "why": "E-17 and E-18 table rows, and the 14-day definition that separates them"},
}

MODES = {
    "M1_exclusions_never_opened": "answered without calling search_policy at all",
    "M2_decisive_clause_missed": "searched, but never retrieved the wording the claim turns on",
    "M3_ungrounded_limit": "passed a limit to compute_payout that no retrieved passage states",
    "M4_fabricated_reference": "cited a claim id, form, chunk id or exclusion code that does not exist",
    "M5_payout_skipped": "stated a payable amount above zero without calling compute_payout",
    "M6_step_inefficiency": "took more steps than the longest accepted path for the case",
}


def accepted_sequences(payout_required, retry_allowed):
    """Every tool sequence this case accepts, as a set of tuples. Enumerated from
    the rules in the module docstring rather than written out one by one."""
    seqs = set()
    max_payouts = 2 if retry_allowed else 1
    alphabet = ("search_policy", "compute_payout")
    for length in range(1, MAX_SEARCHES + max_payouts + 1):
        for tail in product(alphabet, repeat=length):
            searches = tail.count("search_policy")
            payouts = tail.count("compute_payout")
            if not 1 <= searches <= MAX_SEARCHES or payouts > max_payouts:
                continue
            if payout_required and payouts == 0:
                continue
            if tail[0] != "search_policy":
                continue                      # nothing can be computed before the wording is open
            if payouts == 2:
                first, second = [i for i, t in enumerate(tail) if t == "compute_payout"]
                if "search_policy" not in tail[first:second]:
                    continue                  # a retry has to go back to the wording first
            seqs.add(("get_claim",) + tail)
    return seqs


def numbers_in(text):
    """Every number a passage states, with thousands separators removed."""
    return {int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", text)}


def refused(call):
    return "error" in (call.get("returned") or {})


def check_args(row, opened_text):
    """Referential validity of every argument that LANDED. Returns
    (checks, failures, attempts) - attempts counts ungrounded limits the tool
    refused, which are not failures of the claim but are still model behaviour."""
    claim = CLAIMS[row["claim_id"]]
    checks, bad, blocked = 0, [], 0
    for call in row["tool_calls"]:
        a = call["args"]
        if call["tool"] == "compute_payout" and refused(call):
            if a.get("limit") is not None and a["limit"] not in numbers_in(opened_text):
                blocked += 1
            continue    # refused: it never reached the claim, so it is not scored as a landed argument
        if call["tool"] == "get_claim":
            checks += 1
            if a.get("claim_id") not in CLAIMS:
                bad.append("get_claim: claim id %r does not exist" % a.get("claim_id"))
        elif call["tool"] == "search_policy":
            for form in a.get("form_numbers") or []:
                checks += 1
                short = form.split()[0]
                if short not in FORMS:
                    bad.append("search_policy: form %r does not exist" % form)
                elif short not in [f.split()[0] for f in claim["forms_attached"]]:
                    bad.append("search_policy: form %s is not on this policy" % short)
        elif call["tool"] == "compute_payout":
            checks += 1
            if a.get("loss_amount", 0) > claim["claimed_amount"]:
                bad.append("compute_payout: loss_amount %s exceeds the claimed %s"
                           % (a.get("loss_amount"), claim["claimed_amount"]))
            checks += 1
            if a.get("excess") != claim["excess"] and a.get("excess") not in numbers_in(opened_text):
                bad.append("compute_payout: excess %s is neither the policy excess nor stated in any passage opened"
                           % a.get("excess"))
            if a.get("limit") is not None:
                checks += 1
                if a["limit"] not in numbers_in(opened_text):
                    bad.append("compute_payout: limit %s is stated in no passage opened" % a["limit"])
    # citations in the answer
    out = row["output"] or {}
    cited = " ".join(str(g) for g in out.get("grounds", [])) + " " + str(out.get("reasoning", ""))
    for chunk_id in set(re.findall(r"[A-Z]{2}-\d{4}_\d{2}-\d{2}#\d{2}", cited)):
        checks += 1
        if chunk_id not in CHUNKS:
            bad.append("answer cites chunk %s, which does not exist" % chunk_id)
    for code in set(re.findall(r"\bE-\d{2}\b", cited)):
        checks += 1
        if code not in CODES:
            bad.append("answer cites exclusion %s, which does not exist" % code)
    return checks, bad, blocked


def score(row):
    claim_id = row["claim_id"]
    out = row["output"] or {}
    payable = out.get("payable_amount")
    payout_required = isinstance(payable, (int, float)) and payable > 0
    taken = tuple(c["tool"] for c in row["tool_calls"])
    retried = any(refused(c) for c in row["tool_calls"])
    accepted = accepted_sequences(payout_required, retry_allowed=retried)

    searched = [c for c in row["tool_calls"] if c["tool"] == "search_policy"]
    opened = [cid for c in searched for cid in (c.get("returned") or {}).get("chunk_ids", [])]
    opened_text = " ".join(CHUNKS.get(cid, "") for cid in opened)
    decisive = DECISIVE[claim_id]["chunks"]
    missed = [cid for cid in decisive if cid not in opened]

    checks, arg_failures, blocked = check_args(row, opened_text)
    steps_needed = min(len(s) for s in accepted_sequences(payout_required, retry_allowed=False))
    steps_max = max(len(s) for s in accepted)

    modes = []
    if not searched:
        modes.append("M1_exclusions_never_opened")
    elif missed:
        modes.append("M2_decisive_clause_missed")
    if any("limit" in f for f in arg_failures):
        modes.append("M3_ungrounded_limit")
    if any(f.startswith("answer cites") or "does not exist" in f for f in arg_failures):
        modes.append("M4_fabricated_reference")
    accepted_payouts = [c for c in row["tool_calls"]
                        if c["tool"] == "compute_payout" and not refused(c)]
    if payout_required and not accepted_payouts:
        # a refused call is not a payout: the figure in the answer was the model's own arithmetic
        modes.append("M5_payout_skipped")
    if len(taken) > steps_max:
        modes.append("M6_step_inefficiency")

    return {
        "claim_id": claim_id,
        "class": row["class"],
        "outcome_passed": row["outcome_passed"],
        "taken": " > ".join(taken),
        "sequence_accepted": taken in accepted,
        "payout_required": payout_required,
        "decisive_opened": not missed,
        "decisive_missed": missed,
        "arg_checks": checks,
        "arg_failures": arg_failures,
        "blocked_attempts": blocked,
        "steps_taken": len(taken),
        "steps_needed": steps_needed,
        "step_efficiency": round(len(taken) / steps_needed, 2),
        "modes": modes,
        "trajectory_passed": (taken in accepted) and not missed and not arg_failures and not modes,
        "tokens": row["tokens"],
        "cost_usd": row["cost_usd"],
        "latency_s": row["latency_s"],
    }


def summarise(tag, scored):
    n = len(scored)
    costs = sorted(s["cost_usd"] for s in scored)
    return {
        "tag": tag,
        "cases": n,
        "outcome_pass_rate": sum(s["outcome_passed"] for s in scored) / n,
        "trajectory_pass_rate": sum(s["trajectory_passed"] for s in scored) / n,
        "gap": (sum(s["outcome_passed"] for s in scored) - sum(s["trajectory_passed"] for s in scored)) / n,
        "tool_choice_accuracy": sum(s["sequence_accepted"] for s in scored) / n,
        "argument_validity_rate": (sum(s["arg_checks"] - len(s["arg_failures"]) for s in scored)
                                   / max(1, sum(s["arg_checks"] for s in scored))),
        "step_efficiency_p50": statistics.median(s["step_efficiency"] for s in scored),
        "cost_p50_usd": statistics.median(costs),
        "cost_max_usd": max(costs),
        "tokens_total": sum(s["tokens"] for s in scored),
        "latency_p50_s": statistics.median(s["latency_s"] for s in scored),
        "ungrounded_limit_landed": sum("M3_ungrounded_limit" in s["modes"] for s in scored),
        "ungrounded_limit_attempts": sum("M3_ungrounded_limit" in s["modes"] for s in scored)
                                     + sum(s["blocked_attempts"] for s in scored),
    }


def mode_counts(scored):
    return {m: sum(m in s["modes"] for s in scored) for m in MODES}


def load(tag):
    path = "runs/traj_%s.jsonl" % tag
    if not os.path.exists(path):
        sys.exit("%s not found - run: python run_trace.py %s" % (path, tag))
    return [score(json.loads(line)) for line in open(path, encoding="utf-8") if line.strip()]


def write_csv(tag, scored):
    with open("trajectory_%s.csv" % tag, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["claim_id", "class", "outcome", "trajectory", "path_taken", "sequence_accepted",
                    "decisive_opened", "decisive_missed", "arg_failures", "steps_taken", "steps_needed",
                    "step_efficiency", "modes", "tokens", "cost_usd", "latency_s"])
        for s in scored:
            w.writerow([s["claim_id"], s["class"], "PASS" if s["outcome_passed"] else "FAIL",
                        "PASS" if s["trajectory_passed"] else "FAIL", s["taken"], s["sequence_accepted"],
                        s["decisive_opened"], "; ".join(s["decisive_missed"]), "; ".join(s["arg_failures"]),
                        s["steps_taken"], s["steps_needed"], s["step_efficiency"], "; ".join(s["modes"]),
                        s["tokens"], round(s["cost_usd"], 6), round(s["latency_s"], 2)])


def report(tag, scored):
    s = summarise(tag, scored)
    print("\n=== %s ===" % tag)
    print("  outcome pass %.0f%%   trajectory pass %.0f%%   GAP %.0f points"
          % (s["outcome_pass_rate"] * 100, s["trajectory_pass_rate"] * 100, s["gap"] * 100))
    print("  tool-choice accuracy   %.0f%%" % (s["tool_choice_accuracy"] * 100))
    print("  argument validity      %.1f%%" % (s["argument_validity_rate"] * 100))
    print("  step efficiency (p50)  %.2f  (taken / needed)" % s["step_efficiency_p50"])
    print("  cost per claim         p50 $%.5f   max $%.5f" % (s["cost_p50_usd"], s["cost_max_usd"]))
    print("  tokens total %d   latency p50 %.2fs" % (s["tokens_total"], s["latency_p50_s"]))
    print("  ungrounded limits: %d landed, %d attempted (the rest refused by the tool)"
          % (s["ungrounded_limit_landed"], s["ungrounded_limit_attempts"]))
    print("  modes:")
    for mode, count in mode_counts(scored).items():
        print("    %-28s %d   %s" % (mode, count, MODES[mode]))
    print("  per claim:")
    for r in scored:
        print("    %s  outcome %-4s  trajectory %-4s  eff %.2f  %-46s %s"
              % (r["claim_id"], "PASS" if r["outcome_passed"] else "FAIL",
                 "PASS" if r["trajectory_passed"] else "FAIL", r["step_efficiency"],
                 r["taken"], ",".join(m.split("_")[0] for m in r["modes"])))
    return s


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    tags = sys.argv[1:] or ["before"]
    summaries = []
    for tag in tags:
        scored = load(tag)
        write_csv(tag, scored)
        summaries.append(report(tag, scored))

    with open("trajectory_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summaries[0].keys()))
        w.writeheader()
        for s in summaries:
            w.writerow({k: (round(v, 6) if isinstance(v, float) else v) for k, v in s.items()})

    if len(tags) == 2:
        a, b = (load(tags[0]), load(tags[1]))
        print("\n=== regression check: %s -> %s ===" % tuple(tags))
        before, after = mode_counts(a), mode_counts(b)
        for mode in MODES:
            arrow = "same"
            if after[mode] > before[mode]:
                arrow = "WORSE"
            elif after[mode] < before[mode]:
                arrow = "better"
            print("    %-28s %d -> %d   %s" % (mode, before[mode], after[mode], arrow))
        sa, sb = summaries
        print("    %-28s %d -> %d   (behaviour unchanged where equal: the tool refuses, the model still tries)"
              % ("ungrounded limit ATTEMPTS", sa["ungrounded_limit_attempts"], sb["ungrounded_limit_attempts"]))
        print("  price paid per claim:  tokens %+d   cost %+.6f   latency p50 %+.2fs"
              % ((sb["tokens_total"] - sa["tokens_total"]) / 10,
                 (sb["cost_p50_usd"] - sa["cost_p50_usd"]),
                 sb["latency_p50_s"] - sa["latency_p50_s"]))
