# Week 4 — Task Set D — Insurance claims

Failure separation and one retrieval change, measured on the 6 endorsements from Week 3.

**Result: the change did not buy back hit-rate@3, and I am not shipping it.**

| retriever | hit-rate@3 | hit-rate@1 | MRR | p50 latency |
|---|---|---|---|---|
| baseline — dense only | **9/12 = 0.750** | 5/12 | 0.569 | **270 ms** |
| + cross-encoder rerank over top 25 | **8/12 = 0.667** | 7/12 | 0.611 | **1213 ms** |

4.5x the latency to lose a question on the specified metric. Full reasoning, failure labels
and the rejected BM25 experiment: [results.md](results.md).

Failure tally: **2 retrieval, 0 generation, 1 not-in-corpus.** Generation was then tested
separately with 8 pinned-context probes and answered all 8 correctly — which is the evidence
that swapping the model would have fixed nothing.

## Setup

```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env        # then paste your Groq key into .env
```

## Run

```
.venv\Scripts\python ingest.py             # 6 endorsements -> 48 chunks
.venv\Scripts\python index.py              # build the vector index
.venv\Scripts\python evaluate.py baseline  # 9/12  @ 270 ms
.venv\Scripts\python evaluate.py rerank    # 8/12  @ 1213 ms
.venv\Scripts\python evaluate.py hybrid    # 8/12  - the rejected experiment
.venv\Scripts\python -m streamlit run app.py
```

Single queries:

```
.venv\Scripts\python search.py "does E-17 apply to a burst supply line"
.venv\Scripts\python rerank.py "does E-17 apply to a burst supply line"
.venv\Scripts\python answer.py "what is the water backup limit and deductible"
```

Only `answer.py` and `app.py` need an API key. Every measured number is produced without one.

## Files

| file | role |
|---|---|
| `data/` | the 6 endorsements, carried over from Week 3 |
| `ingest.py` | reads documents, extracts metadata, chunks at clause level |
| `index.py` | embeds the chunks into Chroma |
| `search.py` | dense search — the baseline retriever |
| `rerank.py` | cross-encoder rerank over the top 25 — **the one change** |
| `hybrid.py` | BM25 + RRF — tested and rejected, see results.md section 4 |
| `golden_set.jsonl` | 12 questions with their known-correct chunk ids |
| `evaluate.py` | hit-rate@3 and p50 latency for a given retriever |
| `answer.py` | grounded answers with citations and forced refusal |
| `app.py` | inspection view — question, chunks and answer side by side |
| `runs/` | saved measurement runs |

## Notes

Chunking moved from 700 to 250 characters (clause level) before the baseline was taken. At 700
each endorsement produced only 4 chunks, the whole exclusions table sat in one of them, and the
dense baseline scored 10/12 against a ceiling of 11/12 — no headroom to measure anything. Both
runs below use the same 250-character chunker; the chunk size is not the variable under test.
