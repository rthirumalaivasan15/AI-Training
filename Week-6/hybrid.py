import re
import sys
from rank_bm25 import BM25Okapi
from index import load_chunks, META_FIELDS
from search import dense_search, show

RRF_K = 60         # the constant in the RRF formula, 1 / (RRF_K + rank)
CANDIDATES = 25    # how deep each list goes before we fuse them

_rows = load_chunks()
_by_id = {r["chunk_id"]: r for r in _rows}


def tokenize(text):
    # keep the hyphen: "E-17" must stay one token, or the code signal is lost
    return re.findall(r"[a-z0-9\-]+", text.lower())


_bm25 = BM25Okapi([tokenize(r["text"]) for r in _rows])
_ids = [r["chunk_id"] for r in _rows]


def bm25_search(question, k=3):
    scores = _bm25.get_scores(tokenize(question))
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return [as_hit(_ids[i], float(scores[i])) for i in order]


def as_hit(chunk_id, score):
    row = _by_id[chunk_id]
    return {
        "chunk_id": chunk_id,
        "score": score,
        "text": row["text"],
        "meta": {f: row[f] for f in META_FIELDS},
    }


def rrf(result_lists, rrf_k=RRF_K):
    # fuse on RANK, not score - cosine and BM25 are on different scales
    fused = {}
    for hits in result_lists:
        for rank, hit in enumerate(hits, 1):
            fused[hit["chunk_id"]] = fused.get(hit["chunk_id"], 0.0) + 1.0 / (rrf_k + rank)
    return sorted(fused.items(), key=lambda pair: pair[1], reverse=True)


def hybrid_search(question, k=3, where=None):
    dense = dense_search(question, CANDIDATES, where)
    lexical = bm25_search(question, CANDIDATES)
    return [as_hit(chunk_id, score) for chunk_id, score in rrf([dense, lexical])[:k]]


if __name__ == "__main__":
    q = " ".join(sys.argv[1:])
    show(q, hybrid_search(q, 5))
