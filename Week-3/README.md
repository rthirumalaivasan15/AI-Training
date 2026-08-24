# Week 3 — Task Set D · Insurance claims RAG

Claims-assistant retrieval pipeline over 6 homeowners/dwelling-fire endorsements,
comparing two chunking strategies on 8 known-answer questions.

**Result: naive chunker 7/8, structure-aware chunker 8/8 hit-in-top-5.**

Full write-up: [results.md](results.md)

## Run it

```bash
pip install chromadb

python src/ingest.py            # index the 6 endorsements under both strategies
python src/verify_questions.py  # confirm every marker exists in its source document
python src/eval.py              # hit-in-top-5 for both strategies -> outputs/search_dump.md
python src/filter_demo.py       # policy_line filter demo      -> outputs/filter_demo.md
python src/answer.py            # cited answers + refusals     -> outputs/transcripts.md
```

`src/ingest.py` builds `chroma_db/` from scratch, so chunk_ids in the write-up are
reproducible.

## Layout

| Path | Contents |
|---|---|
| `data/endorsements/` | The 6 endorsement documents |
| `questions.json` | 8 known-answer questions + 3 out-of-corpus questions |
| `src/chunkers.py` | `parse_header`, `naive_chunks`, `structure_chunks` |
| `src/ingest.py` | Indexes both strategies with full metadata |
| `src/eval.py` | Hit-in-top-5 measurement |
| `src/filter_demo.py` | Metadata filter demonstration |
| `src/answer.py` | Grounding prompt, refusal gate, cited answers |
| `outputs/` | Search dump, filter demo, transcripts, code diff |
