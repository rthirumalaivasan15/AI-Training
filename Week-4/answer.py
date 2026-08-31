import os
import re
import sys
from dotenv import load_dotenv
from openai import OpenAI
from search import dense_search
from hybrid import hybrid_search

load_dotenv()

BASE_URL = "https://api.groq.com/openai/v1"
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
SCORE_FLOOR = 0.35   # below this the corpus almost certainly does not hold the answer
REFUSAL = "NOT_IN_DOCUMENTS"

SYSTEM = """You answer questions about insurance endorsements for a claims adjuster.

Rules you must follow:
- Use only the numbered context passages provided. You have no other knowledge.
- End every sentence that makes a claim with the chunk id it came from, in square
  brackets, for example [HO-0304_03-24#03].
- Exclusion codes and edition dates are not interchangeable. E-17 under one edition
  is not E-17 under another. If the context does not contain the exact form and
  edition asked about, say so.
- If the context does not contain the answer, reply with exactly NOT_IN_DOCUMENTS
  and nothing else. Never guess and never fill a gap from general knowledge.
"""


def build_context(hits):
    blocks = []
    for h in hits:
        blocks.append("[%s] (%s, %s ed. %s)\n%s"
                      % (h["chunk_id"], h["meta"]["policy_line"], h["meta"]["form_number"],
                         h["meta"]["edition"], h["text"]))
    return "\n\n---\n\n".join(blocks)


def cited_ids(text):
    # the model sometimes uses full-width brackets, so match on the id itself
    return set(re.findall(r"[\[【]([A-Z]{2}-\d{4}_[\d-]+#\d{2})[\]】]", text))


def answer(question, retriever=hybrid_search, k=3):
    hits = retriever(question, k)

    # hard guard: refuse before the model ever sees the question
    best_dense = dense_search(question, 1)[0]["score"]
    if best_dense < SCORE_FLOOR:
        return {"answer": REFUSAL, "hits": hits, "refused_by": "score floor",
                "best_dense_score": round(best_dense, 3), "citations": set()}

    client = OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url=BASE_URL)
    reply = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Context:\n\n%s\n\nQuestion: %s"
                                        % (build_context(hits), question)},
        ],
    ).choices[0].message.content.strip()

    return {"answer": reply, "hits": hits,
            "refused_by": "model" if reply == REFUSAL else None,
            "best_dense_score": round(best_dense, 3),
            "citations": cited_ids(reply)}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # the model returns unicode spaces cp1252 cannot print
    question = " ".join(sys.argv[1:])
    result = answer(question)

    print("Q:", question)
    print("\nretrieved:")
    for h in result["hits"]:
        print("  %-18s %s" % (h["chunk_id"], h["text"].split("\n")[0][:56]))

    print("\nanswer:\n%s" % result["answer"])

    retrieved_ids = {h["chunk_id"] for h in result["hits"]}
    dangling = result["citations"] - retrieved_ids
    if result["answer"] == REFUSAL:
        print("\ncitations: none needed (refused)")
    elif not result["citations"]:
        print("\ncitations: NONE - answer is uncited")
    elif dangling:
        print("\ncitations: %d, but these do not resolve: %s" % (len(result["citations"]), ", ".join(dangling)))
    else:
        print("\ncitations: %d, all resolve to retrieved chunks" % len(result["citations"]))
