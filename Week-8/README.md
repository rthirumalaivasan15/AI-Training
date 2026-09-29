# Week 8 — Task Set D — Insurance claims

Score the path the claims agent takes, not just the answer it reaches.

**Outcome pass 80%, trajectory pass 40%: a 40-point gap.** One claim reaches the
correct UNDETERMINED without opening a single endorsement. One mitigation —
argument validation on `compute_payout` — took the top mode from **5 → 2** and the
gap to **30 points**, for **+1,468 tokens, +$0.000215 and +1.05 s per claim**, and
created a new mode on the way (**M5: 0 → 1**).

| number | before | after |
|---|---|---|
| tool-choice accuracy | 90% | 90% |
| argument validity rate | 92.8% | 97.3% |
| step efficiency p50 (taken / needed) | 1.00 | 1.50 |
| cost per claim, p50 / max | $0.00130 / $0.00170 | $0.00152 / $0.00221 |
| outcome pass / trajectory pass | 80% / 40% | 80% / 50% |

Full write-up, the named right-answer-wrong-path trace, the mitigation diff and
the per-mode regression table: [results.md](results.md).

## Setup

```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env        # then paste your Groq key into .env
.venv\Scripts\python index.py
```

## Run

```
.venv\Scripts\python run_trace.py before        # 10 trajectories -> runs/traj_before.jsonl
.venv\Scripts\python run_trace.py after         # same, with the mitigation live
.venv\Scripts\python trajectory_eval.py before after    # score both + regression check
```

`run_trace.py` refuses to overwrite a finished run; delete the file to re-run.
`trajectory_eval.py` makes no model calls, so re-scoring a saved run is free.
`WEEK8_VALIDATE_ARGS=0` reproduces the pre-mitigation agent.

## Files

| file | role |
|---|---|
| `claims.json`, `expected.json`, `data/`, `chunks.jsonl`, `search.py`, `index.py`, `ingest.py` | the Week 7 claims and retrieval, carried over |
| `agent.py`, `tools.py`, `llm.py`, `contract.py`, `workflow.py` | the Week 7 agent; `tools.py` carries the one mitigation |
| `run_trace.py` | runs the 10 claims and saves each full trajectory |
| `trajectory_eval.py` | the accepted path sets, the decisive-wording check, the four numbers, the six modes |
| `trajectory_before.csv`, `trajectory_after.csv` | per claim |
| `trajectory_summary.csv` | the headline numbers for both runs |
| `runs/traj_*.jsonl` | every tool call, its arguments, what it returned, and the outcome grade |

## The six modes

| mode | meaning |
|---|---|
| M1_exclusions_never_opened | answered without calling `search_policy` at all |
| M2_decisive_clause_missed | searched, but never retrieved the wording the claim turns on |
| M3_ungrounded_limit | passed a limit to `compute_payout` that no retrieved passage states |
| M4_fabricated_reference | cited a claim id, form, chunk id or exclusion code that does not exist |
| M5_payout_skipped | stated a payable above zero with no accepted `compute_payout` call |
| M6_step_inefficiency | took more steps than the longest accepted path for the case |
