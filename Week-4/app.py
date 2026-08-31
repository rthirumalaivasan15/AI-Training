import json
import streamlit as st
from search import dense_search
from hybrid import hybrid_search
from rerank import rerank_search
from answer import answer, REFUSAL

RETRIEVERS = {
    "baseline (dense only)": dense_search,
    "rerank (cross-encoder over top 25)": rerank_search,
    "hybrid (BM25 + RRF, rejected)": hybrid_search,
}


@st.cache_data
def golden():
    with open("golden_set.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


st.set_page_config(page_title="Claims assistant - inspection view", layout="wide")
st.title("Claims assistant - inspection view")

rows = golden()
labels = ["(type my own)"] + ["%s  %s" % (g["id"], g["question"]) for g in rows]
picked = st.selectbox("Question", labels)

if picked == "(type my own)":
    question, gold = st.text_input("Ask something"), None
else:
    g = rows[labels.index(picked) - 1]
    question, gold = g["question"], g["gold_chunk_id"]

name = st.radio("Retriever", list(RETRIEVERS), horizontal=True)
k = st.slider("top-k", 1, 10, 3)
run = st.button("Search")

if run and question:
    hits = RETRIEVERS[name](question, k)
    left, right = st.columns(2)

    with left:
        st.subheader("What was fetched")
        if gold:
            got = gold in [h["chunk_id"] for h in hits]
            st.success("HIT - gold chunk %s is in the top %d" % (gold, k)) if got \
                else st.error("MISS - gold chunk %s is not in the top %d" % (gold, k))
        elif gold is None and picked != "(type my own)":
            st.warning("This question has no answer in the corpus. It must be refused.")

        for rank, h in enumerate(hits, 1):
            is_gold = h["chunk_id"] == gold
            head = "%d.  %s   score %.3f%s" % (rank, h["chunk_id"], h["score"],
                                               "   <- gold" if is_gold else "")
            with st.expander(head, expanded=is_gold):
                st.caption("%s | %s ed. %s | %s" % (h["meta"]["policy_line"], h["meta"]["form_number"],
                                                    h["meta"]["edition"], h["meta"]["source_file"]))
                st.text(h["text"])

    with right:
        st.subheader("What it answered")
        with st.spinner("asking the model..."):
            result = answer(question, RETRIEVERS[name], k)

        if result["answer"] == REFUSAL:
            st.info("Refused: %s (best dense score %.3f)" % (result["refused_by"], result["best_dense_score"]))
        else:
            st.write(result["answer"])

        retrieved_ids = {h["chunk_id"] for h in result["hits"]}
        dangling = result["citations"] - retrieved_ids
        if result["answer"] == REFUSAL:
            pass
        elif not result["citations"]:
            st.error("No citations in the answer")
        elif dangling:
            st.error("Citations do not resolve: %s" % ", ".join(dangling))
        else:
            st.success("All %d citations resolve to fetched chunks" % len(result["citations"]))
