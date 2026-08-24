import pathlib
import chromadb

ROOT = pathlib.Path(__file__).resolve().parents[1]
client = chromadb.PersistentClient(path=str(ROOT / "chroma_db"))
col = client.get_collection("naive")

question = "A pipe burst in my rental house while it sat empty between tenants for 45 days. Is the damage covered?"

res = col.query(query_texts=[question], n_results=5)

print(f"Q: {question}\n")
for rank, (cid, doc, meta, dist) in enumerate(zip(
        res["ids"][0], res["documents"][0],
        res["metadatas"][0], res["distances"][0]), 1):
    print(f"{rank}. score={1 - dist:.4f}  {cid}  [{meta['form_number']}]")
    print("   ", " ".join(doc.split())[:120], "...")
    print()
