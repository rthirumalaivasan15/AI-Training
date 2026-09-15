import os
import json
import shutil
import chromadb

CHUNKS = "chunks.jsonl"
DB_PATH = "chroma"
COLLECTION = "endorsements"
META_FIELDS = ("source_file", "form_number", "edition", "policy_line", "edition_date", "title")


def load_chunks():
    with open(CHUNKS, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def build():
    # always rebuild from scratch so the index can never drift from chunks.jsonl
    if os.path.exists(DB_PATH):
        shutil.rmtree(DB_PATH)

    client = chromadb.PersistentClient(path=DB_PATH)
    col = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    rows = load_chunks()
    col.add(
        ids=[r["chunk_id"] for r in rows],
        documents=[r["text"] for r in rows],
        metadatas=[{k: r[k] for k in META_FIELDS} for r in rows],
    )
    return col.count()


if __name__ == "__main__":
    print("indexed %d chunks" % build())
