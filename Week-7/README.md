# Week 7 — Task Set D — Insurance claims

Race the claims agent against a fixed workflow, and settle whether it needs to be
an agent at all with four numbers instead of an opinion.

**Pass rate tied at 8/10; the workflow wins the other three numbers. The agent
never searched a second time on any claim, so the path does not vary by input.
Ship the workflow.**

| system | pass rate | p50 latency | total tokens | cost per claim |
|---|---|---|---|---|
| fixed workflow | 8/10 | 3.09 s | 23,319 | $0.000753 |
| agent | 8/10 | 4.74 s | 54,785 | $0.001209 |

Same 10 claims, same model (`openai/gpt-oss-120b` on Groq), same three tools,
same output contract, same grader. Full write-up, failure analysis, verdict,
budget log and tool diff: [results.md](results.md).

## Setup

```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env        # then paste your Groq key into .env
.venv\Scripts\python ingest.py
.venv\Scripts\python index.py
```

## Run

```
.venv\Scripts\python agent.py CLM-2024-10004       # the agent, one claim
.venv\Scripts\python workflow.py CLM-2024-10004    # the workflow, one claim
.venv\Scripts\python race.py                        # both over all 10 -> race.csv
.venv\Scripts\python selftest.py                    # 25 checks, no model calls
.venv\Scripts\python agent.py CLM-2024-10006 --max-tokens 3000 --log runs/budget_termination.log
```

`race.py` never re-rolls a finished run. It loads a complete
`runs/race_<system>.jsonl`, so delete that file to re-run that system.

## Files

| file | role |
|---|---|
| `data/`, `ingest.py`, `index.py`, `search.py`, `chunks.jsonl` | the Week 6 retrieval, carried over untouched |
| `claims.json` | the 10 claims: record, forms attached, excess, limits, adjuster notes |
| `expected.json` | the correct outcome per claim, committed before either system ran |
| `tools.py` | `get_claim`, `search_policy`, `compute_payout`, shared by both systems |
| `contract.py` | the output contract and the pass rule both systems are graded by |
| `llm.py` | one Groq client; per-call tokens, cost, active time and rate-limit wait |
| `agent.py` | the loop, with the four budgets in `Budget` |
| `workflow.py` | the same task as five hard-coded steps, no loop |
| `race.py` | runs both, writes `race.csv` and `race_claims.csv` |
| `selftest.py` | each budget stops a spinning stub model; workflow has no loop |
| `runs/` | race runs, the first-race crash, the budget termination log |

## Commit trail

```
git log --oneline week-7
```

The base agent → expected answers → third tool → budgets → workflow → race harness
→ first race (agent crash) → crash fix → race result → write-up. Each claim in
the results is checkable against the commit that produced it.
