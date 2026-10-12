# Week 3 — Retrieval-Augmented Generation, From Parts

Module 2 · Retrieval & RAG · build week

Topics: why RAG · embeddings and dense retrieval · bi-encoder vs cross-encoder ·
embedding models (MTEB, BGE, E5) · chunking strategies · chunk size and overlap ·
vector databases (HNSW) · Qdrant / Chroma / pgvector · similarity search and top-K ·
metadata filtering · grounded generation and citations

---

### Q1. What is RAG, and why use it instead of the model's memory or fine-tuning?

Retrieval-Augmented Generation: **retrieve** the relevant passages from your own documents,
put them in the prompt, then **generate** the answer from them.

- **Private and current data** — the model never saw your policy wording, and it changes.
  RAG reads it at query time.
- **Citations** — every answer can point to the passage it came from.
- **Less guessing** — the model works from supplied text, with permission to say "not in
  the documents".
- **Cheap updates** — change a document, re-index, done.

Fine-tuning changes *behaviour* (format, style, a narrow task); it is a poor way to add
*facts*: slow to update, expensive, and it cannot cite. Use RAG for knowledge.

**In this project:** the claims assistant answers from six endorsement documents
(HO-0304, HO-0415, HO-0509, HO-0612, HO-0820, DP-0703); every answer cites chunk ids such
as `[HO-0820_05-24#03]`.

### Q2. How does dense retrieval work?

1. **Index time:** split documents into chunks, run each through an embedding model, store
   the vector with the chunk text and metadata.
2. **Query time:** embed the question with the **same** model, find the k stored vectors
   closest to it (cosine similarity or dot product), return those chunks.

Because embeddings encode meaning, "the pipe under the sink split" can match "sudden and
accidental discharge from a plumbing system" with few shared words. Weak spots: exact codes
and IDs (E-17 vs E-18), rare jargon, and questions phrased very differently from the
documents. Changing the embedding model means re-indexing everything.

### Q3. What is the difference between a bi-encoder and a cross-encoder?

- **Bi-encoder:** encodes the query and each document **separately** into vectors, then
  compares vectors. Document vectors are computed once and stored, so search over millions
  of chunks is fast. This is what a vector database uses.
- **Cross-encoder:** reads the query and one document **together** in a single pass and
  outputs a relevance score. Far more accurate — it can see how query words relate to
  passage words — but it must run once per (query, document) pair, so it is too slow to
  search a whole corpus.

Standard pattern: bi-encoder retrieves the top 20–50 candidates, cross-encoder reranks them
(Week 4).

### Q4. How do you choose an embedding model? What are MTEB, BGE and E5?

- **MTEB** (Massive Text Embedding Benchmark) is a public leaderboard scoring embedding
  models across task types; look at the **retrieval** columns, not the overall average.
- **BGE** (BAAI) and **E5** (Microsoft) are popular open embedding model families in
  several sizes. Both expect specific formatting: E5 wants `query: ` / `passage: `
  prefixes; BGE recommends an instruction prefix on queries. Skipping these quietly lowers
  quality.

Also weigh: vector dimension (storage, speed), maximum input length (must cover your chunk
size), language coverage, cost or hosting. Then **measure on your own questions** —
leaderboard rank does not transfer automatically to insurance wording.

**In this project:** `all-MiniLM-L6-v2` (384 dimensions), held constant across the Week 3
chunking comparison so only the chunker changed.

### Q5. What chunking strategies exist, and how do fixed-size and structure-aware compare?

- **Fixed-size:** split every N tokens/characters, usually with overlap. Simple, works on
  anything, but can cut a clause in half or separate a table row from its header.
- **Structure-aware:** split on the document's own structure — clauses, sections, table
  rows — and attach context (form number, clause heading) to each chunk. Each chunk is a
  coherent, citable unit; needs parsing logic per document type.
- Others: **recursive** splitting (paragraphs, then sentences), **semantic** chunking (split
  where similarity between sentences drops).

For structured documents (policies, contracts, manuals) structure-aware usually wins — but
prove it with a measurement.

**In this project:** Week 3 compared both on 8 known-answer questions, 4 of which depend on
a row inside an exclusions table: naive chunker **7/8**, structure-aware **8/8**
hit-in-top-5.

### Q6. What is "the chunking tension", and what does overlap do?

- **Small chunks** retrieve *precisely* (the vector is about one thing) but may lack the
  context to answer — a rule without its conditions, a row without its header.
- **Large chunks** carry full context but retrieve *imprecisely* (the vector averages many
  topics) and cost more prompt tokens.

**Overlap** (e.g. 10–15% of the chunk) repeats the end of one chunk at the start of the next,
so a sentence cut at a boundary survives whole in one of them. It costs extra storage and
can return near-duplicate chunks.

There is no universal best size: try two or three settings and measure hit-rate@k on a
fixed question set.

### Q7. How does an HNSW index work?

**Hierarchical Navigable Small World** is a graph-based approximate nearest-neighbour index.
Vectors are nodes linked to their near neighbours, arranged in layers: the top layers are
sparse with long-range links, the bottom layer holds every vector with short links. A search
starts at the top, greedily moves to the neighbour closest to the query, drops a layer, and
repeats — like zooming in on a map.

Key settings: **M** (links per node — memory vs recall), **ef_construction** (build quality),
**ef_search** (search breadth — recall vs latency). It is *approximate*: it can miss the
true nearest neighbour, which is why recall is tunable. Exact search is fine for a few
thousand chunks.

**In this project:** the Chroma collection is built with `{"hnsw:space": "cosine"}` — HNSW
with cosine distance.

### Q8. Chroma, Qdrant or pgvector — how do you choose?

- **Chroma:** embedded, runs in-process with a local folder, minimal setup. Ideal for
  prototypes and small corpora.
- **Qdrant:** a dedicated vector database server with strong metadata filtering, payload
  indexes, quantisation and horizontal scaling. For production vector search at scale.
- **pgvector:** a Postgres extension. Vectors live next to your relational data with SQL,
  transactions, joins and your existing backups and access control. Often the right
  choice when you already run Postgres and the corpus is moderate.

Decide on scale, filtering needs, operations you already have, and whether vectors must
join with other business data.

**In this project:** Chroma, persistent local folder, 48 chunks — rebuilt from
`chunks.jsonl` every time so the index cannot drift from the source.

### Q9. How do top-K and metadata filtering work, and what can go wrong with filters?

**Top-K** returns the K most similar chunks. Too small and the answer may be just below the
cut; too large and the prompt fills with noise and costs more.

**Metadata filtering** restricts search to chunks whose metadata match a condition —
`form_number = "HO-0820"`, `policy_line = "dwelling-fire"`, latest edition only. It stops
look-alike documents (another edition's E-17) from being retrieved. Filters can be applied
before the vector search (exact, can starve results) or after it (can return fewer than K).

The danger is a filter that matches **nothing** and fails silently — the caller sees "no
results" and concludes the wording is silent.

**In this project:** Week 9 found exactly that: the form number `HO 08 20` was split to
`HO`, matched no chunks, and was dropped from the filter without any error. The fix made it
a recoverable error naming the closest form held.

### Q10. How do you make a RAG answer grounded, cited and able to say "I don't know"?

1. Give every chunk a **stable ID** and send the ID with the text.
2. Instruct: answer only from the passages; end every sentence with the chunk id it relies
   on; if the passages do not answer, say so in a fixed, detectable way.
3. **Check in code:** every cited id must be in the retrieved set; a missing or invented
   citation makes the answer unsupported.
4. **Gate before generating:** if no chunk passes a relevance check, refuse without calling
   the model.
5. **Test it:** include out-of-corpus questions and score a correct refusal as a pass.

Track the opposite error too: refusing questions the documents do answer.

**In this project:** Week 3 included 3 out-of-corpus questions alongside the 8 known-answer
ones, and used a deterministic refusal gate.
