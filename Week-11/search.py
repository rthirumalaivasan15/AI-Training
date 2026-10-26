import sys
import chromadb
from index import DB_PATH, COLLECTION

_col = chromadb.PersistentClient(path=DB_PATH).get_collection(COLLECTION)


def dense_search(question, k=3, where=None):
    res = _col.query(query_texts=[question], n_results=k, where=where)
    hits = []
    for i, chunk_id in enumerate(res["ids"][0]):
        hits.append({
            "chunk_id": chunk_id,
            "score": 1 - res["distances"][0][i],
            "text": res["documents"][0][i],
            "meta": res["metadatas"][0][i],
        })
    return hits


def show(question, hits):
    print(question)
    for rank, h in enumerate(hits, 1):
        first_line = h["text"].split("\n")[0][:58]
        print("  %d  %.3f  %-18s %-14s %s" % (
            rank, h["score"], h["chunk_id"], h["meta"]["policy_line"], first_line))


if __name__ == "__main__":
    q = " ".join(sys.argv[1:])
    show(q, dense_search(q, 5))
