"""The one command.

    python eval.py

  1. summarises any case not yet in summaries.jsonl - a frozen summary is never redone
  2. runs the 4 assertions over every summary - free and deterministic, always runs
  3. runs judge v1, and v2 once judge_v2.txt exists - only if the labels are
     committed; a finished run is read back from runs/, not re-run
  4. prints pass rate BY MODE, because one overall number hides a mode that regressed
  5. prints agreement with the hand labels, before -> after

Everything printed is also written to runs/eval_output.txt.
"""
import os
import sys

import cases as case_store
import summarise
import assertions
import judge
import agreement

OUT = os.path.join("runs", "eval_output.txt")
JUDGED_CRITERIA = 1   # criterion.txt - one binary question


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for stream in self.streams:
            stream.write(s)
        return len(s)

    def flush(self):
        for stream in self.streams:
            stream.flush()


def frac(k, n):
    return "%d/%d %3d%%" % (k, n, round(100.0 * k / n)) if n else "-"


def main():
    all_cases = case_store.load()
    summaries = summarise.generate_missing()
    labels_doc = judge.read_labels()

    runs, locked = {}, None
    for version in ("v1", "v2"):
        if not os.path.exists("judge_%s.txt" % version):
            continue
        try:
            runs[version] = judge.run(version)
        except judge.Locked as exc:
            locked = "judge %s LOCKED - %s" % (version, exc)
            break
    latest = list(runs)[-1] if runs else None

    results = []
    for case in all_cases:
        summary = summaries[case["id"]]["summary"]
        checks = assertions.run(case, summary)
        row = {
            "case": case,
            "position": assertions.fields(summary).get("COVERAGE POSITION", "?"),
            "checks": checks,
            "asserts_ok": all(c["passed"] for c in checks),
            "judge": {v: runs[v][1][case["id"]]["verdict"] for v in runs},
            "human": (labels_doc["labels"].get(case["id"], {}).get("label")
                      if labels_doc else None),
        }
        row["pass"] = row["asserts_ok"] and (row["judge"][latest] == "PASS" if latest else True)
        results.append(row)

    names = [name for name, _ in assertions.ASSERTIONS]
    regressions = sum(1 for c in all_cases if c.get("source_trace"))
    print("WEEK 6 EVAL - %d cases, %d of them regression cases replayed from Week 5 traces"
          % (len(all_cases), regressions))
    print("checks: %d deterministic assertions (%s) | %d judged criterion"
          % (len(names), ", ".join(names), JUDGED_CRITERIA))
    print("summaries.jsonl sha %s" % summarise.file_sha())
    if locked:
        print(locked)
    pass_rule = ("PASS = all assertions + judge %s" % latest) if latest else \
                "PASS = assertions only (no judge has run)"

    # --- pass rate by mode -------------------------------------------------------
    cols = ["assertions"] + ["judge " + v for v in runs] + (["human"] if labels_doc else []) + ["PASS"]
    print("\nPASS RATE BY MODE   (%s)" % pass_rule)
    print("  %-30s %3s  " % ("mode", "n") + "  ".join("%-12s" % c for c in cols))
    groups = [("%d %s" % (m, name), [r for r in results if r["case"]["mode"] == m])
              for m, name in case_store.MODES.items()]
    groups.append(("ALL", results))
    for label, rows in groups:
        n = len(rows)
        cells = [frac(sum(r["asserts_ok"] for r in rows), n)]
        cells += [frac(sum(r["judge"][v] == "PASS" for r in rows), n) for v in runs]
        if labels_doc:
            cells.append(frac(sum(r["human"] == "PASS" for r in rows), n))
        cells.append(frac(sum(r["pass"] for r in rows), n))
        if label == "ALL":
            print("  " + "-" * (36 + 14 * len(cols)))
        print("  %-30s %3d  " % (label, n) + "  ".join("%-12s" % c for c in cells))

    # --- each assertion by mode ----------------------------------------------------
    print("\nASSERTIONS BY MODE")
    print("  %-30s %3s  " % ("mode", "n") + "  ".join("%-17s" % a for a in names))
    for label, rows in groups:
        cells = [frac(sum(next(c for c in r["checks"] if c["name"] == a)["passed"] for r in rows),
                      len(rows)) for a in names]
        print("  %-30s %3d  " % (label, len(rows)) + "  ".join("%-17s" % c for c in cells))

    # --- per case --------------------------------------------------------------------
    print("\nPER CASE")
    for r in results:
        failed = [c for c in r["checks"] if not c["passed"]]
        verdicts = "  ".join("%s %-4s" % (v, r["judge"][v] or "??") for v in runs)
        print("  %-4s m%d  %-17s %-4s  %s%s  %s"
              % (r["case"]["id"], r["case"]["mode"], r["position"][:17],
                 "PASS" if r["pass"] else "FAIL", verdicts,
                 ("  human %s" % r["human"]) if r["human"] else "",
                 "; ".join("%s: %s" % (c["name"], c["detail"]) for c in failed)))

    if labels_doc and runs:
        agreement.report(labels_doc, runs)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs("runs", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as log:
        sys.stdout = Tee(sys.stdout, log)
        main()
