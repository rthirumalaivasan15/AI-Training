import json
import pathlib
import chromadb

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

qs = json.loads((ROOT / "questions.json").read_text(encoding="utf-8"))["questions"]
client = chromadb.PersistentClient(path=str(ROOT / "chroma_db"))

lines = ["# Search-only dump - 8 questions x 2 chunking strategies",
         "(score = cosine similarity, higher is better)"]
results = {}

for name in ("naive", "structure"):
    col = client.get_collection(name)
    lines.append(f"\n## Strategy: {name}")
    hits = []

    for q in qs:
        res = col.query(query_texts=[q["question"]], n_results=5)
        ids = res["ids"][0]
        docs = res["documents"][0]
        metas = res["metadatas"][0]
        dists = res["distances"][0]

        hit = any(m["form_number"] == q["expected_form"] and q["marker"] in d
                  for d, m in zip(docs, metas))
        hits.append(hit)

        lines.append(f"\n### {q['id']} - {q['question']}")
        lines.append(f"Expected: {q['expected_form']} {q['expected_clause']}"
                     f" | hit-in-top-5: {'HIT' if hit else 'MISS'}")

        for rank, (cid, d, m, dist) in enumerate(zip(ids, docs, metas, dists), 1):
            ok = m["form_number"] == q["expected_form"] and q["marker"] in d
            tag = "  <-- expected" if ok else ""
            lines.append(f"{rank}. score={1 - dist:.4f}  {cid}  [{m['form_number']}]{tag}")
            lines.append(f"   {' '.join(d.split())[:110]}...")

    results[name] = hits

lines.append("\n## Per-question hit table")
lines.append("| Q | naive | structure |")
lines.append("|---|---|---|")
for i, q in enumerate(qs):
    n = "HIT" if results["naive"][i] else "MISS"
    s = "HIT" if results["structure"][i] else "MISS"
    lines.append(f"| {q['id']} | {n} | {s} |")
lines.append(f"| **total** | **{sum(results['naive'])}/8** | **{sum(results['structure'])}/8** |")

(OUT / "search_dump.md").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines[-13:]))
print(f"\nfull dump written to {OUT / 'search_dump.md'}")
