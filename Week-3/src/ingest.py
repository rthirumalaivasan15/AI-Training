import pathlib
import chromadb
from chunkers import parse_header, naive_chunks, structure_chunks

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "endorsements"

client = chromadb.PersistentClient(path=str(ROOT / "chroma_db"))

for name in ("naive", "structure"):
    try:
        client.delete_collection(name)
    except Exception:
        pass

naive_col = client.create_collection("naive", metadata={"hnsw:space": "cosine"})
struct_col = client.create_collection("structure", metadata={"hnsw:space": "cosine"})

n_total = s_total = 0
for f in sorted(DATA.glob("*.txt")):
    text = f.read_text(encoding="utf-8")
    meta = parse_header(text, f.name)

    pieces = naive_chunks(text)
    naive_col.add(
        ids=[f"naive:{meta['form_number']}:{n:03d}" for n in range(len(pieces))],
        documents=pieces,
        metadatas=[dict(meta, chunker="naive", clause="") for _ in pieces],
    )
    n_total += len(pieces)

    sc = structure_chunks(text, meta)
    struct_col.add(
        ids=[f"struct:{meta['form_number']}:{n:03d}" for n in range(len(sc))],
        documents=[c["text"] for c in sc],
        metadatas=[dict(meta, chunker="structure", clause=c["clause"]) for c in sc],
    )
    s_total += len(sc)

    print(f"{f.name}: naive={len(pieces)}  structure={len(sc)}")

print(f"\nnaive total={n_total}   structure total={s_total}")
