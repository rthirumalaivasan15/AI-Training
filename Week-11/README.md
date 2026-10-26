# Week 11 — Task Set D — Insurance claims

Find the coverage answer that ignored the policy, then close the loop so it cannot ship again.

**The bad answer:** `trc_a4a9f492d77c` — a rental condo the insured owns in another city, written
under the HO-3 on their own home, answered **COVERED under HO-0304's E-17 exception**. Right answer:
NOT_IN_DOCUMENTS (a homeowners form does not reach a tenant-occupied rental elsewhere).

**The loop:** eval case added before any fix and seen **RED (suite 8/11)** on `claims-agent-v1`; first fix
`claims-agent-v2` fixed the position but dropped the excess (**6/11**, kept on record); `claims-agent-v3`
**GREEN: the case passes, suite 9/11** — the whole suite re-run each time.

**Cost per query** for that request: **$0.000910** — generation 93.3%, retrieval 6.7%, tools 0%.
**At 10x, the daily token cap breaks first:** 1,060,740 tokens a day against Groq's 200,000 TPD (5.3x
over), already hit for real today; cost at 10x would be $0.27 a day.

| deliverable | file |
|---|---|
| time-to-find + slice | [drill.md](drill.md) — **the timed squadmate drill has not been run**; how the real bad answer was found is documented |
| the found trace: per-span latency, tokens, cost, prompt version, context ids | [trace.json](trace.json) |
| the eval case | [evals/P-trc_a4a9f492d77c.json](evals/P-trc_a4a9f492d77c.json) |
| suite output RED, then GREEN, with pass counts | below, and `runs/suite_red.txt`, `runs/suite_v2_attempt.txt`, `runs/suite_green.txt` |
| cost per query by stage | [cost_by_stage.md](cost_by_stage.md) |
| what breaks first at 10x | [tenx.md](tenx.md) |

## The loop, case by case

| case | v1 — RED | v2 — first fix | v3 — GREEN |
|---|---|---|---|
| C01 | ✅ PARTIAL | ❌ PARTIAL | ✅ PARTIAL |
| C02 | ❌ DENIED | ✅ DENIED | ✅ DENIED |
| C05 | ✅ DENIED | ✅ DENIED | ✅ DENIED |
| C06 | ✅ COVERED | ✅ COVERED | ✅ COVERED |
| C09 | ✅ UNDETERMINED | ✅ COVERED | ✅ COVERED |
| C10 | ✅ NOT_IN_DOCUMENTS | ❌ UNDETERMINED | ❌ DENIED |
| C14 | ❌ DENIED | ❌ DENIED | ❌ DENIED |
| C15 | ✅ DENIED | ✅ DENIED | ✅ DENIED |
| C18 | ✅ UNDETERMINED | ✅ UNDETERMINED | ✅ UNDETERMINED |
| C19 | ✅ PARTIAL | ❌ PARTIAL | ✅ PARTIAL |
| P-trc_a4a9f492d77c | ❌ COVERED | ❌ NOT_IN_DOCUMENTS | ✅ NOT_IN_DOCUMENTS |

- **The target case** went COVERED → NOT_IN_DOCUMENTS (judge PASS). v2 got the position right but wrote
  `EXCESS: NOT STATED` though the notes give 1,000 — the fix broke the deductible field of its own case. v3
  adds one sentence: claim facts come from the notes whatever the position.
- **C14** fails the date-of-loss assertion in every run, as it did in Week 10 — unrelated to this fix.
- **C10** gave a different position in each run (NOT_IN_DOCUMENTS, UNDETERMINED, DENIED); in GREEN the judge
  passed it but the denial cited no code or clause. **C02** failed on the judge in RED and passed in v2 and
  v3. One run per case: a single flip is within the app's own run-to-run variation (the failing case itself
  came back COVERED, DENIED and UNDETERMINED on three v1 runs), so the move that counts is the target case
  and the net count, 8/11 → 9/11.

### Suite output — RED (before the fix)

```
SUITE RED - prompt claims-agent-v1 (sha 5783e86864c0) - Week-6 cases sha 400bb0047d97 - 2026-10-26T15:04:53+05:30

  C01                        PARTIAL          E-16, HO-0820 Clause 2   PASS
  C02                        DENIED           E-15, E-17               FAIL  judge FAIL
  C05                        DENIED           E-51                     PASS
  C06                        COVERED          NONE                     PASS
  C09                        UNDETERMINED     E-17, HO-0304 Clause 4   PASS
  C10                        NOT_IN_DOCUMENTS NONE                     PASS
  C14                        DENIED           E-17                     FAIL  date_of_loss
  C15                        DENIED           E-31                     PASS
  C18                        UNDETERMINED     E-17, HO-0304 Clause 4   PASS
  C19                        PARTIAL          HO-0509 Clause 2 (sublim PASS
  P-trc_a4a9f492d77c         COVERED          E-17                     FAIL  judge FAIL; expect: position COVERED, which this case forbids

SUITE RED: 8/11 pass
```

### Suite output — first fix (v2), not green

```
SUITE V2 ATTEMPT (first fix, not green) - prompt claims-agent-v2 (sha 611e1167c08b) - Week-6 cases sha 400bb0047d97 - 2026-10-26T15:11:01+05:30

  C01                        PARTIAL          E-16, HO-0820 Clause 2   FAIL  judge FAIL
  C02                        DENIED           E-15                     PASS
  C05                        DENIED           E-51, HO-0820 Clause 4   PASS
  C06                        COVERED          HO-0415 Clause 2, HO-041 PASS
  C09                        COVERED          E-17                     PASS
  C10                        UNDETERMINED     E-61, E-62               FAIL  judge FAIL
  C14                        DENIED           E-17                     FAIL  date_of_loss
  C15                        DENIED           E-31                     PASS
  C18                        UNDETERMINED     E-17, HO-0304 Clause 2,  PASS
  C19                        PARTIAL          HO-0509_06-24#02, HO-050 FAIL  grounds_on_denial
  P-trc_a4a9f492d77c         NOT_IN_DOCUMENTS NONE                     FAIL  excess_numeric

SUITE V2 ATTEMPT: 6/11 pass
```

### Suite output — GREEN (after the fix)

```
SUITE GREEN - prompt claims-agent-v3 (sha 38e4336a5604) - Week-6 cases sha 400bb0047d97 - 2026-10-26T21:31:52+05:30

  C01                        PARTIAL          E-16, HO-0820 Clause 2   PASS
  C02                        DENIED           E-15                     PASS
  C05                        DENIED           E-51                     PASS
  C06                        COVERED          NONE                     PASS
  C09                        COVERED          E-17, HO-0304 Clause 1(a PASS
  C10                        DENIED           NONE                     FAIL  grounds_on_denial
  C14                        DENIED           E-17                     FAIL  date_of_loss
  C15                        DENIED           E-31                     PASS
  C18                        UNDETERMINED     E-17, HO-0304_03-24#06   PASS
  C19                        PARTIAL          HO-0509 Clause 2 (sublim PASS
  P-trc_a4a9f492d77c         NOT_IN_DOCUMENTS NONE                     PASS

SUITE GREEN: 9/11 pass
```

## Prompt version bump, canary and rollback

`claims-agent-v1` (sha `5783e86864c0`) → `claims-agent-v2` (`611e1167c08b`, failed) → **`claims-agent-v3`
(`38e4336a5604`)**, in `prompts.py`; every trace records `prompt_version` and `prompt_sha`. Production stays
on v1 until the canary passes.

1. **Canary:** set `CANARY_USERS=adj-04 CANARY_VERSION=claims-agent-v3` for one working day (adj-04 sent 6 of
   24 requests today) and promote v3 to everyone only if the suite stays at 9/11 or better and none of
   adj-04's v3 traces (`find.py --version claims-agent-v3`) is COVERED on a property the forms do not reach or
   reports a claim fact NOT STATED that the notes give.
2. **Rollback:** empty `CANARY_USERS` (or set `PROMPT_VERSION=claims-agent-v1`) — one environment variable, no
   deploy — on the first such trace or any suite run below 9/11; the canary's answers stay pullable by
   `prompt_version` for re-review.

## What the logs carry, and the PII line

One JSON line per request in `logs/<date>.jsonl` (`tracer.py`): time, user, input type, prompt version and
sha, the redacted input **and** output, the output's position and grounds as their own fields, retrieved
context ids, and a span for every model call (generation), `search_policy` call (retrieval), other tool call
and MCP start-up — each with latency, tokens and cost — plus cost split by stage and Groq's quota headers
and 429s. Claimant names, phones, emails, addresses and policy numbers are redacted on write (the Week 5
redactor); a trace is refused if anything survives. Claim numbers are kept as the business key.

## Run

```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env                     # Groq key
.venv\Scripts\python index.py
.venv\Scripts\python traffic.py           # a day of traffic -> logs/
.venv\Scripts\python find.py              # search the logs (see drill/RUNBOOK.md)
.venv\Scripts\python make_eval.py <trace_id> --position-in ... --why "..." --how-found "..."
set PROMPT_VERSION=claims-agent-v1 & .venv\Scripts\python suite.py red
set PROMPT_VERSION=claims-agent-v3 & .venv\Scripts\python suite.py green
.venv\Scripts\python report.py cost <trace_id>     # cost_by_stage.md
.venv\Scripts\python report.py tenx                # tenx.md
```

The drill (`plant.py` for the squadmate, `find.py` for the finder) is in `drill/RUNBOOK.md`. Not done: the
timed drill itself, and the bonus (a log field that makes the find instant, then a second, faster drill).
