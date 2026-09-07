# Week 5 — Task Set D — Insurance claims

Read 20 real traces by hand, no fixes, and hand back a ranked taxonomy.

**13 of 20 clean, 7 of 20 failed, 5 named modes, and every one of them is
claim-affecting.** The manager's "it sometimes gets coverage wrong" turns out to
be six wrong denials and one wrong payment, with a trace id against each.

| # | Failure mode | Count | % of 20 | Severity |
|---|---|---|---|---|
| 1 | Says the endorsements are silent when the clause exists but was not fetched | 2 | 10% | wrongly denies |
| 2 | Attaches a consequence to a clause that states no consequence | 2 | 10% | wrongly denies |
| 3 | Answers from whichever endorsement came back, not the one named | 1 | 5% | wrongly denies |
| 4 | Applies an exception without testing the definition it depends on | 1 | 5% | **wrongly pays** |
| 5 | Returns NOT_IN_DOCUMENTS without reading, on the retrieval score alone | 1 | 5% | wrongly denies |

Full taxonomy with example trace ids: [taxonomy.md](taxonomy.md). The 20
observation sentences, the seed, the replay evidence and the demo-set comparison:
[notes.md](notes.md).

**Prediction, committed before any fix** — `3f4ab4d`, 2026-09-07. Remove the 0.35
score floor; expect score-floor refusals 19/117 → 0/117, at least 12 of those 19
correctly cited, at most 3 unsupported. [PREDICTION.md](PREDICTION.md).

**Bonus** — the top mode runs at **10% in the random 20 and 0% in the demo 10**.
Overall failures: 35% random, 10% demo. The paragraph about what that means is in
notes.md section 7.

## Setup

```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy ..\Week-4\.env.example .env      # then paste your Groq key into .env
```

## Run

```
.venv\Scripts\python index.py                 # 48 chunks into Chroma
.venv\Scripts\python selftest.py              # 28 checks, no model calls
.venv\Scripts\python run_traffic.py           # 117 desk questions -> traces/traces.jsonl
.venv\Scripts\python run_traffic.py demo      # 10 review questions -> traces/demo.jsonl
.venv\Scripts\python sample.py                # the seeded 20
.venv\Scripts\python sample.py --replay-pick  # the trace to replay
.venv\Scripts\python replay.py <trace_id>     # original vs replayed
.venv\Scripts\python show.py --sample         # the 20, laid out for reading
```

`run_traffic.py` refuses to overwrite an existing trace file. Delete it to re-run.

## Files

| file | role |
|---|---|
| `data/`, `chunks.jsonl`, `ingest.py`, `index.py`, `search.py`, `hybrid.py` | the Week 4 pipeline, carried over untouched |
| `assistant.py` | the Week 4 answering logic with a trace written around it |
| `prompts.py` | system prompts under a version id, so a trace can be replayed after an edit |
| `redact.py` | strips claimant identifiers on the way **in** to the writer |
| `trace.py` | one JSON line per question; redacts, asserts, then appends |
| `questions.py` | 117 desk questions and the 10 demo questions, written before anything ran |
| `run_traffic.py` | fills the trace files |
| `sample.py` | the seeded random draw |
| `replay.py` | rebuilds one trace from the trace alone |
| `show.py` | lays traces out for reading, and computes nothing |
| `selftest.py` | 28 mechanical checks on the plumbing, model stubbed |
| `traces/` | 117 desk traces, 10 demo traces |

## Notes

Only `assistant.py`, `run_traffic.py` and `replay.py` need an API key.

The answering pipeline is unchanged from Week 4, including its use of
`hybrid_search`, which Week 4 measured as worse than dense on hit-rate@3. Fixing
that would have produced a taxonomy of an app nobody is running.

The first 117 traces were thrown away: the redactor leaked a bare claimant first
name in 3 of them. Both that leak and the over-redaction that turned an
endorsement title into `[NAME]` are fixed, and the re-run scans clean. Written up
in notes.md section 4.
