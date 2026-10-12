# Week 10 — Task Set D — Insurance claims

Race the claims squad against the single agent, and report the bill alongside the pass rate.

**Kill the squad.** On the same 10 Week-6 cases with the same Week-6 judge, the single
agent passed **8/10** and the squad **4/10**, for **1.7x the tokens** and **1.9x the cost
per claim**, at twice the p50 latency. The squad won no case the single agent lost.

| arm | pass rate | p50 latency | p99 latency | total tokens | cost per claim |
|---|---|---|---|---|---|
| single agent | **8/10** | 4.02 s | 6.20 s | 47,339 | $0.001234 |
| claims squad | **4/10** | 8.06 s | 11.04 s | 78,382 | $0.002384 |

**Context re-send multiplier = 78,382 / 47,339 = 1.7x; largest share: orchestrator ->
coverage worker, 57% of all squad tokens** (25 calls; 33% of all squad tokens are prompt
tokens that worker re-sent on its second and later search laps).

**Injected failure (coverage worker 500 on C02):** retried once, then degraded — no false
"covered", but it shipped NOT_IN_DOCUMENTS and blamed missing documents instead of the dead
worker. [failure_case.md](failure_case.md)

| deliverable | file |
|---|---|
| 4 metrics x 2 arms, cases named, per-case table | [race_table.md](race_table.md) |
| every hand-off with its token count | [handoffs.log](handoffs.log) |
| multiplier line with the dominant hand-off | in race_table.md and the last line of handoffs.log |
| the injected 500 and what the orchestrator did | [failure_case.md](failure_case.md) |
| keep / kill, 9 lines | [verdict.md](verdict.md) |

## What was held the same

- **Cases:** C01, C02, C05, C06, C09, C10, C14, C15, C18, C19 — the first two of each Week 5
  failure mode, read from `../Week-6/cases.jsonl` on every run (sha `400bb0047d97` recorded in
  every row). No case was written or edited. The judge's two worked examples (C12, C22) are
  not in the set.
- **Judge:** `../Week-6/judge_v2.txt`, refused unless its sha is the Week 6 v2 sha
  `af8559b5e5e4`, on `openai/gpt-oss-20b` at temperature 0, plus the 4 Week 6 assertions.
  PASS = all four assertions and judge PASS — the Week 6 rule.
- **Arms:** both `openai/gpt-oss-120b` on Groq, temperature 0, the same policy-docs MCP server,
  the same Week 6 summary format (its output lines are cut out of `../Week-6/prompts.py`).

## The two arms

- **Single agent** (`single_agent.py`): the Week 9 loop — one model, every tool the server lists
  (`search_policy`, `compute_payout`), the adjuster notes in, the summary out.
- **Claims squad** (`orchestrator.py`): orchestrator plan + adjuster-note worker in parallel
  (the only two calls that see the notes), coverage/exclusions worker with `search_policy` only
  that sees just the orchestrator's brief, then a synthesis call that sees only the workers'
  results and must keep the coverage worker's position as given.

## Where the squad lost

- Synthesis did not lose anything: the final position equals the coverage worker's on 10/10,
  and stated conditions (C01, C05) were carried into REASONING.
- The brief did: working from a summary of the notes, the coverage worker stopped at
  UNDETERMINED on C09 and C19, where the single agent decided correctly. It searched no less —
  the same number of searches as the single agent on 8 of 10 cases.
- C01 and C06 failed with the same position as the single agent, on reasoning. With n = 10 and a
  judge that agreed with the labels 84% in Week 6, these two may be noise. The judge also
  passed both arms on C18 with opposite positions (UNDETERMINED and COVERED). Even counting
  C01 and C06 as noise, the squad is 6/10 against 8/10.
- C10 failed in both arms (judge), and C14 failed in both on the date-of-loss assertion.

## Setup and run

```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env          # Groq key
.venv\Scripts\python index.py
.venv\Scripts\python race.py                                  # both arms, 10 cases -> runs/race_*.jsonl
.venv\Scripts\python judge.py runs/race_single.jsonl runs/race_multi.jsonl
.venv\Scripts\python failure.py                               # coverage worker 500 on C02
.venv\Scripts\python judge.py runs/failure_C02.jsonl
.venv\Scripts\python report.py                                # race_table.md, handoffs.log; no model calls
```

Finished runs are never re-run: delete a run file to run it again. `runs/smoke/C05.txt` is
the one smoke test both arms got before the race; it is not part of any number.

The bonus (AgentCard and mapping the failed case onto the A2A task lifecycle) is not done.
