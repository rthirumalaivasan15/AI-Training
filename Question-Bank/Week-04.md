# Week 4 — Debugging Retrieval: Hybrid, Reranking & Failure Separation

Module 2 · Retrieval & RAG · build week

Topics: retrieval vs generation failures · the inspection view · keyword search (BM25) ·
keyword vs semantic search · hybrid search (RRF) · reranking (cross-encoder) ·
Cohere Rerank / BGE-Reranker · MMR · query rewriting · HyDE · hit-rate@k, recall@k, MRR

---

### Q1. What are the two kinds of RAG failure, and how do you tell them apart?

- **Retrieval failure:** the information needed was not in the retrieved chunks. The model
  never had a chance.
- **Generation failure:** the right chunk *was* retrieved and the answer is still wrong —
  ignored, misread, condition not applied.

**The R/G rule** for each failed question: *was the needed information in the top-k?* No →
R. Yes → G. Add a third label, **not in corpus**, where the right behaviour is to refuse.

It matters because the fixes are completely different: retrieval failures need chunking,
hybrid search, reranking or rewriting; generation failures need prompt, context format or
model changes. Swapping to a smarter model fixes nothing if retrieval missed.

**In this project:** Week 4 labelled 2 retrieval, 0 generation, 1 not-in-corpus — then ran 8
pinned-context probes and generation answered all 8, the evidence that a model swap would
have changed nothing.

### Q2. What is an inspection view, and what should it show?

A side-by-side debug view for one question: the question and any rewritten query; the
retrieved chunks in rank order with ids, source and scores; the final prompt sent; the
answer with its citations; and the expected chunk with whether retrieval hit it.

Most bugs are obvious in seconds once you see all of it together: "the right clause was 7th",
"an old edition was retrieved", "the table header is missing from the chunk". Without it,
people tweak prompts blindly.

**In this project:** Week 4 has a Streamlit inspection app (`app.py`), later extended to
include the reranker.

### Q3. How does BM25 score a document?

For each query term it adds up:
- **term frequency** in the document, with diminishing returns (the 10th mention adds little);
- **inverse document frequency** — rare terms count more ("E-43" in two chunks beats "water"
  in hundreds);
- **length normalisation** — long documents don't win just by containing more words.

Two tuning knobs: `k1` (how fast term frequency saturates) and `b` (strength of length
normalisation). **Tokenisation decides everything:** if "E-43" is split into "e" and "43",
the exact match is lost.

### Q4. Keyword vs semantic search — where does each fail?

| | keyword (BM25) | semantic (embeddings) |
|---|---|---|
| strong on | exact codes, IDs, names, rare terms | paraphrase, synonyms, meaning |
| fails on | different wording for the same idea ("pipe split" vs "discharge") | exact identifiers and look-alikes (E-17 vs E-18), rare jargon |

They fail on different questions, which is why combining them (hybrid search) usually helps
in domains full of codes — but "usually" is a hypothesis to measure, not a fact.

### Q5. How does Reciprocal Rank Fusion merge two result lists?

```
RRF(d) = Σ over each list  1 / (k + rank(d)),   k = 60 by default
```

A chunk ranked well in both lists rises to the top; a chunk found by only one list still
gets some credit. It uses **ranks, not scores**, which is why it is popular: BM25 scores are
unbounded and corpus-dependent while cosine similarity sits between −1 and 1, so adding raw
scores is meaningless without careful normalisation. One parameter, no extra model calls.

**In this project:** Week 4 tried BM25 + dense with RRF: 8/12 hit-rate@3 against the
baseline's 9/12. It was rejected and is documented as a rejected experiment.

### Q6. What is reranking, and how do you choose between Cohere Rerank and BGE-Reranker?

A **second-stage** step: the first retriever returns 20–50 candidates fast; a cross-encoder
scores each (query, candidate) pair together and reorders them; keep the top few. Worth it
when the right chunk is usually *retrieved but not near the top*. Useless when it is never
in the candidate set.

- **Cohere Rerank:** hosted API. No infrastructure, strong quality, per-call cost and data
  leaves your system.
- **BGE-Reranker:** open weights you run yourself. No per-call fee and data stays in-house;
  you pay in compute and latency.

**In this project:** Week 4's cross-encoder over the top 25 improved hit-rate@1 (5/12 → 7/12)
and MRR (0.569 → 0.611) but **lowered hit-rate@3 (9/12 → 8/12)** — the specified metric — at
**4.5× the latency (270 → 1,213 ms)**. Not shipped.

### Q7. What is MMR, and when would you use it?

**Maximal Marginal Relevance** picks results one at a time, balancing relevance against
redundancy:

```
next = argmax over candidates [ λ · sim(query, d) − (1 − λ) · max sim(d, already picked) ]
```

λ = 1 is plain relevance; lower λ favours diversity. Use it when the top-k are near-duplicates
(overlapping chunks, the same clause in several editions) and you want the k slots to cover
different facts. It can push out a second, genuinely needed copy of a relevant passage, so
measure it.

### Q8. What are query rewriting and HyDE?

**Query rewriting** turns a messy user question into a better search query before
retrieval, often with a small LLM call:
- cleanup and expansion ("HO policy" → "homeowners policy");
- conversation-aware rewriting (resolve "what about that one?");
- **decomposition** into sub-queries;
- **multi-query** — several paraphrases, results fused.

**HyDE** (Hypothetical Document Embeddings): have the model write a *hypothetical answer
passage*, embed that, and search with it. A fake passage often looks more like the real
passage than a short question does.

Both add a call (latency, cost) and can drift from the user's intent — log the original and
rewritten query and measure the effect.

### Q9. Define hit-rate@k, recall@k and MRR, with an example.

- **hit-rate@k:** share of questions with at least one correct chunk in the top k.
- **recall@k:** for questions needing several chunks, the share of the needed chunks found in
  the top k (averaged).
- **MRR:** mean of 1 / (rank of the first correct chunk); 0 if none found. Rewards getting the
  right chunk to rank 1.

Example: three questions with the first correct chunk at ranks 1, 3 and "not found" →
hit-rate@3 = 2/3; MRR = (1 + 1/3 + 0) / 3 = 0.44.

**In this project:** Week 4 baseline on 12 golden questions: hit-rate@3 **9/12 = 0.750**,
hit-rate@1 5/12, MRR **0.569**, p50 270 ms.

### Q10. How do you prove a retrieval change actually helped?

1. **Freeze** the golden question set (and the expected chunk per question) before the
   change.
2. **Measure before** — retrieval only, per question, with latency.
3. Make **one** change.
4. **Measure after** on exactly the same questions.
5. Compare **per question** — which flipped and why — not just the average; 1 of 12 can be
   noise.
6. Report the **cost** (latency, compute) next to the gain, and decide against the metric
   you specified up front.

**In this project:** that procedure is why the Week 4 reranker was rejected even though two
of its metrics went up: the metric agreed in advance (hit-rate@3) went down.
