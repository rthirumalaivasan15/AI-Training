import pathlib
import chromadb

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

client = chromadb.PersistentClient(path=str(ROOT / "chroma_db"))
col = client.get_collection("structure")

query = "is a burst pipe covered if the house sat empty between tenants"
where = {"policy_line": "homeowners"}

lines = ["# Metadata filter demo", "", f'Query: "{query}"', f"Filter: {where}"]


def show(res, title):
    lines.append(f"\n## {title}")
    for rank, (cid, d, m, dist) in enumerate(zip(
            res["ids"][0], res["documents"][0],
            res["metadatas"][0], res["distances"][0]), 1):
        lines.append(f"{rank}. score={1 - dist:.4f}  {cid}  "
                     f"[{m['form_number']} | policy_line={m['policy_line']}]")
        lines.append(f"   {' '.join(d.split())[:110]}...")


show(col.query(query_texts=[query], n_results=5), "Unfiltered")
show(col.query(query_texts=[query], n_results=5, where=where),
     "Filtered where policy_line = homeowners")

(OUT / "filter_demo.md").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
