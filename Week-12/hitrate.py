"""What the loss-date filter costs retrieval on cases that do NOT straddle a version boundary.

    python hitrate.py

Week 4's golden set: 12 adjuster questions, each with the one chunk that answers it,
all in 2024 editions. Every question is given a loss date inside 2024 (2024-08-01),
when every 2024 edition is in force and no form has a version boundary - so the
date filter can only change the result by removing chunks, never by choosing a
different edition. hit-rate@3 = the gold chunk is in the top 3. No model calls.
"""
import os
import sys
import json

from search import dense_search

GOLDEN = os.path.join("..", "Week-4", "golden_set.jsonl")
LOSS_DATE = 20240801


def date_filter(day):
    return {"$and": [{"in_force_from": {"$lte": day}}, {"in_force_to": {"$gte": day}}]}


def main():
    with open(GOLDEN, encoding="utf-8") as f:
        golden = [json.loads(l) for l in f if l.strip()]
    rows, hits = [], {"no_filter": 0, "date_filter": 0}
    for g in golden:
        plain = [h["chunk_id"] for h in dense_search(g["question"], k=3)]
        dated = [h["chunk_id"] for h in dense_search(g["question"], k=3, where=date_filter(LOSS_DATE))]
        a, b = g["gold_chunk_id"] in plain, g["gold_chunk_id"] in dated
        hits["no_filter"] += a
        hits["date_filter"] += b
        rows.append((g["id"], g["gold_chunk_id"], a, b, plain, dated))
    out = ["# hit-rate@3 with and without the loss-date filter (Week 4 golden set, loss date 2024-08-01)", "",
           "| q | gold chunk | no filter | date filter | top 3, no filter | top 3, date filter |",
           "|---|---|---|---|---|---|"]
    for q, gold, a, b, plain, dated in rows:
        out.append("| %s | %s | %s | %s | %s | %s |" % (q, gold, "hit" if a else "miss", "hit" if b else "miss",
                                                     ", ".join(plain), ", ".join(dated)))
    n = len(golden)
    out += ["", "**hit-rate@3: Week 4 (6 wordings, no 2025 edition) 9/12; Week 12 library with the 2025 HO-0304 "
            "edition, no filter %d/%d; with the loss-date filter %d/%d.**" % (hits["no_filter"], n, hits["date_filter"], n)]
    with open(os.path.join("runs", "hitrate.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
