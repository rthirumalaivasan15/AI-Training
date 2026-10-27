# Week 12 — Capstone, Task Set D — Claims triage & coverage assistant

Triages a household claim, checks the policy was in force on the loss date, retrieves the wording **in
force on that date**, cites the exclusion by clause **and endorsement edition**, keeps deductible,
sub-limit and policy limit as three numbers — and refers to an adjuster. It never says "covered": the
referral tool refuses the word in code.

Weeks 3–11 behind one entry point: RAG over clause-level chunks (Weeks 3–4), the hand-built agent loop
(Week 7) with its tools discovered over MCP (Week 9) from two servers — a claims-system stand-in and our
own `policy-docs` — the Week 6 judge, and per-request tracing with one trace id across every hop (Week 11).

## Run it (Windows, Python 3.10+)

```
cd Week-12
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env              # a Groq API key in GROQ_API_KEY; any value for CLAIMS_API_TOKEN
.venv\Scripts\python ingest.py      # 7 wordings -> chunks.jsonl (57 chunks, edition + in-force window each)
.venv\Scripts\python index.py       # chunks -> local Chroma (MiniLM embeddings, no API cost)
```

**The one command:**

```
.venv\Scripts\python app.py triage CLM-2025-30004
```

FNOL in → referral out. It prints the referral (assessment, wording cited with edition and the loss
date it was resolved against, deductible / sub-limit / policy limit, facts for the adjuster) and a trace
id. Then:

| command | what it does | model calls |
|---|---|---|
| `app.py trace <trace_id>` | that request across every hop: host spans + both MCP servers' spans, cost and latency per span | none |
| `gates.py` | the rules the code enforces, replayed over real MCP: wrong edition refused, "covered" refused, PII redacted, trace id carried | none |
| `app.py eval <tag>` | the 25-case suite against the integrated system → `runs/eval_<tag>.jsonl`; resumes if stopped | ~11k tokens a case |
| `app.py report after before` | `eval_report.md`, `taxonomy.md`, `trajectory.md`, `cost_10x.md` from the runs | none |
| `rejudge.py <tag>` | the Week 6 judge re-run on a run's stored referrals with only the wording in force on each loss date | judge only |
| `hitrate.py` | hit-rate@3 on the Week 4 golden set, with and without the loss-date filter | none |

Try `CLM-2024-30001` (2024 storm loss: 2024 wording, excluded under E-15), `CLM-2025-30004` (same loss in
2025: the new Storm Ingress Allowance, sub-limit 5,000), `CLM-2024-30011` (policy cancelled before the loss),
`CLM-2024-30032` (the policy's edition is not on file). All 25 claims are in `claims_system/claims.json`.

**On the free Groq tier** the daily cap is 200,000 tokens: about 18 triages a day. A full suite run takes
two days on it; a paid key runs it in about 30 minutes for under $0.10.

## What is where

| deliverable | file |
|---|---|
| Tuesday's seam list, unedited, with statuses | [seams.md](seams.md) |
| one-page architecture: boxes, arrows, where the model calls are, where the money goes | [architecture.md](architecture.md) |
| eval report: pass rate per mode with n, judge agreement, before → after, what the suite does NOT cover | [eval_report.md](eval_report.md) |
| re-scored taxonomy, with the modes integration created | [taxonomy.md](taxonomy.md) |
| trajectory eval: tool-choice accuracy, outcome-vs-trajectory gap | [trajectory.md](trajectory.md) |
| cost per claim triaged + what breaks first in an 18,000-FNOL hailstorm week | [cost_10x.md](cost_10x.md) |
| top 3 known weaknesses, written before review | [weaknesses.md](weaknesses.md) |
| the 10-minute demo script | [demo.md](demo.md) |
| bonus: hit-rate@3 cost of the loss-date filter | [runs/hitrate.md](runs/hitrate.md) |
| for Thursday's reviewer from another squad, and what they found | [REVIEWER.md](REVIEWER.md), [fresh_eyes.md](fresh_eyes.md) |
| referrals the system wrote (redacted) | [referrals/](referrals/) |
| every trace (redacted) and both servers' spans | [logs/](logs/) |

## The failure this week turned on

The client's wound is a 2024 flood loss assessed against the 2025 wording. Adding a 2025 HO-0304 edition
to the library reproduced it in our own system: the Week 9–11 search ignored the edition and the date, so
a 2024 storm query came back with 3 of 4 passages from 2025 (seam 1). The fix is in code, not in the
prompt: `search_policy` requires the loss date and filters on each chunk's in-force window; an edition that
is not in the library, or not in force on the loss date, is refused with "refer as WORDING_NOT_ON_FILE"
instead of being swapped for another. The first after-fix run found the next hole — a bare form number
resolves to the edition in force on the date, not the one the policy carried (seam 11) — now closed by an
edition check in `refer_to_adjuster` and replayed in `gates.py`.

## Files

| file | role |
|---|---|
| `app.py` | the entry point: triage, trace, eval, report |
| `agent.py`, `prompts.py` | the hand-built loop and its prompt (versioned, sha in every trace) |
| `mcp_host.py`, `mcp_config.json` | starts both MCP servers, discovers tools by `tools/list`, carries the trace id in `_meta` |
| `policy_server.py` | **our MCP server** `policy-docs`: policy lookup, coverage in force, wording search by loss date, refer to adjuster |
| `claims_system/server.py` | the claims platform stand-in: claim status, adjuster notes (raw, with PII) |
| `ingest.py`, `index.py`, `search.py` | wordings → chunks with edition and in-force window → Chroma |
| `tracer.py`, `redact.py` | per-request trace, redacted on write (names, addresses, phones, emails, injuries) |
| `suite.py`, `judge.py`, `evals/cases.jsonl` | 25 cases, 8 assertions first, then the Week 6 judge |
| `build_data.py` | writes the claims, policies and eval cases |
| `data/` | 7 endorsement wordings (HO-0304 in two editions: 03-24 and 01-25) |
