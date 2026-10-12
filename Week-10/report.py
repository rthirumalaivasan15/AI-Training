"""Count the race: race_table.md, handoffs.log and the multiplier line, from the run
and judge files only. No model calls.

    python report.py

Percentiles are nearest-rank over the 10 cases: p50 is the 5th-fastest case, and
p99 is the 10th - the slowest claim. Latency is active seconds: model calls, tool
calls and the orchestrator's own retry backoff, with rate-limit waits left out
(they measure the free-tier quota, not either arm). For the orchestrator it is the
critical path - plan and notes worker run side by side.
"""
import math
import json
from collections import defaultdict

import cases

ARMS = ("single", "multi")


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def nearest_rank(values, p):
    ordered = sorted(values)
    return ordered[max(1, math.ceil(p / 100 * len(ordered))) - 1]


def main():
    ids = cases.CASE_IDS
    runs = {arm: {r["id"]: r for r in load("runs/race_%s.jsonl" % arm)} for arm in ARMS}
    verdicts = {arm: {r["id"]: r for r in load("runs/judge_race_%s.jsonl" % arm)} for arm in ARMS}
    for arm in ARMS:
        missing = [i for i in ids if i not in runs[arm] or i not in verdicts[arm]]
        assert not missing, "%s arm incomplete: %s" % (arm, missing)
        assert {r["cases_sha"] for r in runs[arm].values()} == {cases.source_sha()}

    stats = {}
    for arm in ARMS:
        rows = [runs[arm][i] for i in ids]
        lat = [r["latency_s"] for r in rows]
        stats[arm] = {
            "pass": sum(verdicts[arm][i]["pass"] for i in ids),
            "p50": nearest_rank(lat, 50), "p99": nearest_rank(lat, 99),
            "tokens": sum(r["tokens"] for r in rows),
            "prompt": sum(r["prompt_tokens"] for r in rows),
            "completion": sum(r["completion_tokens"] for r in rows),
            "calls": sum(r["calls"] for r in rows),
            "cost": sum(r["cost_usd"] for r in rows) / len(rows),
            "wait": sum(r["rate_limit_wait_s"] for r in rows),
            "judge_tokens": sum(verdicts[arm][i]["judge_tokens"] for i in ids),
        }
    s, m = stats["single"], stats["multi"]
    multiplier = m["tokens"] / s["tokens"]

    # --- hand-offs -------------------------------------------------------------
    by_hop = defaultdict(lambda: {"tokens": 0, "prompt": 0, "completion": 0, "calls": 0, "payload": 0})
    log = ["# handoffs.log - every hand-off in the claims squad, per case, with the tokens it billed",
           "# tokens = prompt + completion of every model call made to serve that hand-off (Groq usage, not estimated",
           "#          unless marked est.); payload = characters handed over; laps = the coverage worker's search loop",
           ""]
    for i in ids:
        r = runs["multi"][i]
        log.append("%s  mode %d  total %d tok  %d calls" % (i, r["mode"], r["tokens"], r["calls"]))
        for h in r["handoffs"]:
            log.append("  %-38s status %-4s payload %5d ch  %d call%s  %6d tok (%d in / %d out)" % (
                h["name"], h["status"], h["payload_chars"], h["calls"], "" if h["calls"] == 1 else "s",
                h["tokens"], h["prompt_tokens"], h["completion_tokens"]))
            if h["calls"] > 1 or "coverage" in h["name"]:
                for c in h["laps"]:
                    log.append("      %-60s %6d tok (%d in / %d out)%s" % (
                        c["note"][:60], c["prompt_tokens"] + c["completion_tokens"], c["prompt_tokens"],
                        c["completion_tokens"], " est." if c["estimated"] else ""))
            hop = by_hop[h["name"]]
            hop["tokens"] += h["tokens"]
            hop["prompt"] += h["prompt_tokens"]
            hop["completion"] += h["completion_tokens"]
            hop["calls"] += h["calls"]
            hop["payload"] += h["payload_chars"]
        log.append("")

    # within the coverage hand-off: prompt tokens on laps after the first are the
    # system prompt + brief + every earlier result, sent again
    resend = sum(c["prompt_tokens"] for i in ids for h in runs["multi"][i]["handoffs"]
                 if "coverage" in h["name"] for c in h["laps"][1:])
    notes_twice = by_hop["case -> orchestrator (plan)"]["prompt"] + by_hop["orchestrator -> notes worker"]["prompt"]

    ranked = sorted(by_hop.items(), key=lambda kv: -kv[1]["tokens"])
    log.append("TOTALS OVER THE 10 CASES (multi arm %d tokens, single arm %d tokens)" % (m["tokens"], s["tokens"]))
    for name, h in ranked:
        log.append("  %-38s %6d tok  %5.1f%% of all multi tokens  (%d calls, %d in / %d out)" % (
            name, h["tokens"], 100 * h["tokens"] / m["tokens"], h["calls"], h["prompt"], h["completion"]))
    top_name, top = ranked[0]
    line = ("context re-send multiplier = %d / %d = %.1fx; largest share: %s, %.0f%% of all multi tokens"
            % (m["tokens"], s["tokens"], multiplier, top_name, 100 * top["tokens"] / m["tokens"]))
    log += ["", "re-sent inside the coverage worker loop (prompt tokens on laps 2+): %d tok, %.0f%% of all multi tokens"
            % (resend, 100 * resend / m["tokens"]), "", line]
    with open("handoffs.log", "w", encoding="utf-8") as f:
        f.write("\n".join(log) + "\n")

    # --- race table ------------------------------------------------------------
    per_case = ["| case | mode | single: position / verdict / tok / s | multi: position / verdict / tok / s |",
                "|---|---|---|---|"]
    for i in ids:
        cells = []
        for arm in ARMS:
            r, v = runs[arm][i], verdicts[arm][i]
            pos = next((l.split(":", 1)[1].strip() for l in (r["summary"] or "").splitlines()
                        if l.strip().upper().startswith("COVERAGE POSITION")), "-")
            why = "PASS" if v["pass"] else "FAIL (%s)" % ", ".join(
                (["judge " + str(v["verdict"])] if v["verdict"] != "PASS" else []) +
                [c["name"] for c in v["assertions"] if not c["passed"]])
            cells.append("%s / %s / %d / %.2f" % (pos, why, r["tokens"], r["latency_s"]))
        per_case.append("| %s | %d | %s | %s |" % (i, runs["single"][i]["mode"], *cells))

    table = [
        "# race_table.md - single agent vs claims squad, same 10 Week-6 cases, same judge",
        "",
        "Cases (from `../Week-6/cases.jsonl`, sha `%s`): %s - the first two of each Week 5 failure mode."
        % (cases.source_sha(), ", ".join(ids)),
        "Judge: Week 6 `judge_v2.txt` (sha `af8559b5e5e4`) on `openai/gpt-oss-20b` + the 4 Week 6 assertions; "
        "PASS = all four assertions and judge PASS. Both arms: `openai/gpt-oss-120b` on Groq, temperature 0.",
        "",
        "| arm | pass rate | p50 latency | p99 latency | total tokens (10 cases) | cost per claim |",
        "|---|---|---|---|---|---|",
        "| single agent | **%d/10** | %.2f s | %.2f s | %s | $%.6f |" % (s["pass"], s["p50"], s["p99"], format(s["tokens"], ","), s["cost"]),
        "| claims squad (orchestrator) | **%d/10** | %.2f s | %.2f s | %s | $%.6f |" % (m["pass"], m["p50"], m["p99"], format(m["tokens"], ","), m["cost"]),
        "",
        "**%s**" % line.replace("context re-send multiplier", "Context re-send multiplier"),
        "",
        "Model calls: single %d, squad %d. Prompt / completion tokens: single %s / %s, squad %s / %s. "
        "The notes went to two squad calls (plan + notes worker): %s prompt tokens between them. "
        "Rate-limit waits, excluded from latency: single %.0f s, squad %.0f s. "
        "Judge tokens (gpt-oss-20b, not in either arm's bill): single %s, squad %s."
        % (s["calls"], m["calls"], format(s["prompt"], ","), format(s["completion"], ","),
           format(m["prompt"], ","), format(m["completion"], ","), format(notes_twice, ","),
           s["wait"], m["wait"], format(s["judge_tokens"], ","), format(m["judge_tokens"], ",")),
        "",
        "Latency is active seconds (model + tool calls + retry backoff, rate-limit waits excluded); the squad's is "
        "its critical path. Percentiles are nearest-rank over 10 cases, so p99 is the slowest claim. "
        "Cost uses the prices in `llm.py` ($0.15 / $0.60 per 1M input / output tokens).",
        "",
        "## Per case",
        "",
    ] + per_case
    with open("race_table.md", "w", encoding="utf-8") as f:
        f.write("\n".join(table) + "\n")
    print("\n".join(table[5:10]))
    print(line)


if __name__ == "__main__":
    main()
