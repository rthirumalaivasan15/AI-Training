import sys
from fastembed.rerank.cross_encoder import TextCrossEncoder
from search import dense_search, show

MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
CANDIDATES = 25   # how many dense results the cross-encoder re-scores

_encoder = TextCrossEncoder(model_name=MODEL)


def rerank_search(question, k=3, where=None):
    # the cross-encoder reads the question and each chunk TOGETHER, which the
    # embedding model never does - that is where the extra accuracy comes from
    candidates = dense_search(question, CANDIDATES, where)
    scores = list(_encoder.rerank(question, [c["text"] for c in candidates]))

    ranked = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)
    return [dict(hit, score=float(score)) for hit, score in ranked[:k]]


if __name__ == "__main__":
    q = " ".join(sys.argv[1:])
    show(q, rerank_search(q, 5))
