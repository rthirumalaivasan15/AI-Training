import os
import sys
import json
import time
import statistics
from search import dense_search
from hybrid import hybrid_search
from rerank import rerank_search

GOLDEN = "golden_set.jsonl"
RUNS_DIR = "runs"
K = 3

RETRIEVERS = {
    "baseline": dense_search,
    "hybrid": hybrid_search,
    "rerank": rerank_search,
}


def load_golden():
    with open(GOLDEN, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def evaluate(name, k=K):
    retriever = RETRIEVERS[name]
    golden = load_golden()

    retriever("warm up the embedding model", k)  # keep model load out of the timings

    rows = []
    for g in golden:
        start = time.perf_counter()
        hits = retriever(g["question"], k)
        elapsed_ms = (time.perf_counter() - start) * 1000

        ids = [h["chunk_id"] for h in hits]
        gold = g["gold_chunk_id"]
        rows.append({
            "id": g["id"],
            "question": g["question"],
            "gold_chunk_id": gold,
            "retrieved": ids,
            "hit": gold in ids,
            "rank": ids.index(gold) + 1 if gold in ids else None,
            "latency_ms": round(elapsed_ms, 1),
        })

    hits = sum(1 for r in rows if r["hit"])
    return {
        "retriever": name,
        "k": k,
        "hit_rate_at_k": round(hits / len(rows), 3),
        "hits": hits,
        "total": len(rows),
        "p50_latency_ms": round(statistics.median(r["latency_ms"] for r in rows), 1),
        "rows": rows,
    }


def report(result):
    print("retriever: %s   hit-rate@%d: %d/%d = %.3f   p50 latency: %.1f ms\n"
          % (result["retriever"], result["k"], result["hits"], result["total"],
             result["hit_rate_at_k"], result["p50_latency_ms"]))
    print("%-5s %-18s %-6s %-6s %s" % ("id", "gold", "hit", "rank", "retrieved top-%d" % result["k"]))
    for r in result["rows"]:
        print("%-5s %-18s %-6s %-6s %s" % (
            r["id"],
            r["gold_chunk_id"] or "(not in corpus)",
            "yes" if r["hit"] else "no",
            r["rank"] or "-",
            ", ".join(r["retrieved"]),
        ))


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    result = evaluate(name)
    report(result)

    os.makedirs(RUNS_DIR, exist_ok=True)
    with open(os.path.join(RUNS_DIR, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
