# failure_case.md - the coverage/exclusions worker returns a 500 on C02

**What the orchestrator did: it retried once, then degraded to a partial answer - it did not declare the claim covered, but the answer blames missing policy documents instead of the failed exclusions check, so it sends the adjuster to fetch forms that are already attached.**

## The injection

- **Case:** C02 (`CLM-2024-20012`), chosen and committed in `failure.py` before the race ran. A cloudburst pooled water on the lawn and it ran in under the patio door; the insured asks whether E-17 covers it. The exclusions check decides this claim: with the worker up, the squad answered **DENIED, E-15** (surface water) and passed.
- **Fault:** `orchestrator.delegate` returns `{"status": 500, "body": "Internal Server Error"}` for `coverage_worker` on every attempt, without running the worker. Nothing else changes: the notes worker, the plan and synthesis run as in the race.
- **Policy under test:** the orchestrator's generic worker-error rule, written before any failure was injected: retry once after 1 s on a 5xx, then hand the error envelope to synthesis as that worker's result. Synthesis has no instruction about worker errors - only the Week 6 rule "if the wording you have does not let you take a coverage position, use UNDETERMINED or NOT_IN_DOCUMENTS and say what is missing."

## What actually happened (runs/failure_C02.json)

```
START multi C02  (injecting 500 from coverage_worker)
      orchestrator -> notes worker -> status 200 (attempt 1)
      orchestrator -> coverage worker -> status 500 (attempt 1)
      orchestrator -> coverage worker -> status 500 (attempt 2)
DONE  position NOT_IN_DOCUMENTS
```

What synthesis received as the coverage result: `{"status": 500, "body": "Internal Server Error", "attempts": 2}`

What it shipped:

```
POLICY FORMS: NONE
COVERAGE POSITION: NOT_IN_DOCUMENTS
GROUNDS: NONE
REASONING: No coverage forms or endorsement language were retrieved, so a coverage position cannot be determined [NO_DATA].
NEXT STEP: Obtain the relevant policy forms and endorsements to assess coverage.
```

| | worker up (race) | worker 500 (injected) |
|---|---|---|
| position | DENIED, E-15 | NOT_IN_DOCUMENTS, no grounds |
| judge + assertions | PASS | **FAIL** - "incorrectly claims no policy forms or endorsement language were retrieved, yet ... HO-0304 ed. 03-24 is attached" |
| model calls / tokens / cost | 7 / 10,660 / $0.00274 | 3 / 2,974 / $0.00120 |
| active latency | 9.55 s | 5.15 s (incl. the 1 s retry backoff) |

## Retry, degrade or lie?

- **Retried:** yes, once - the 500 was persistent, so the retry could not help.
- **Lied (declared covered with no exclusions check):** no. It did not say COVERED, and it did not pay.
- **Degraded:** yes, but to the wrong partial answer. NOT_IN_DOCUMENTS says the *wording* does not settle the claim; the truth is that the *check never ran*. The 500 is nowhere in the summary - the adjuster cannot tell a dead worker from a missing endorsement, and the next step points at the documents, not at re-running the check. It also cites a chunk id that does not exist (`[NO_DATA]`).
- **Cheaper and faster because it did less:** 2,974 tokens instead of 10,660. A failed hand-off looks like a saving on the bill.

What a correct degrade would say: UNDETERMINED, "the exclusions check did not run (coverage worker returned 500 twice); re-run before any decision". Not built - one change per week, and this is the finding, not the fix.
