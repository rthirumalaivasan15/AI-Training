# drill.md — finding the coverage answer that ignored the policy

**Time-to-find: not measured.** The timed drill — a squadmate plants a bad answer and times
the find — has not been run yet. Everything it needs is built (`plant.py`, `find.py`,
`drill/RUNBOOK.md`); this file will carry the mm:ss, the slice and the squadmate's name when it
is. No time is given here because none was measured.

## The bad answer that was found, and how

The day's logs (`logs/2026-10-26.jsonl`: 24 requests, 5 adjusters, one prompt version) held a
real one, with no planting: **`trc_a4a9f492d77c`** — adj-04, file note, `claims-agent-v1`,
14:32:45. A rental condo the insured owns in another city, written under the HO-3 on their own
home, was answered **COVERED under HO-0304's E-17 exception**. The right answer is
NOT_IN_DOCUMENTS: a homeowners form does not reach a tenant-occupied rental elsewhere (Week 6
labelled this same input, C13, NOT_IN_DOCUMENTS).

**Slice that found it: the output.**

| step | command | result |
|---|---|---|
| 1 | `find.py` | 24 requests: user, input type, prompt version all unremarkable; position COVERED=7 |
| 2 | `find.py --position COVERED` | 7 candidates — the complaint describes the output, so the output is the slice |
| 3 | Week-6 judge over those 7 | 6 PASS, 1 FAIL: `trc_a4a9f492d77c` |
| 4 | `find.py --show trc_a4a9f492d77c` | the trace: context ids explain it in one hop (below) |

Time, user, prompt version and input type could not have found it: one prompt version all day,
all 24 requests in one hour, and the user and input type of the bad answer are ordinary. Cost
could not either: at $0.00091 it sits at the day's lower quartile (median $0.00102), well inside
the outlier band `find.py --cost-outliers` uses ($0.00051–$0.00158).

## The one-hop diagnosis the context ids gave

One search (`HO-0304`, "vacant more than 30 days exclusion") returned `HO-0304_03-24#05` (the
exclusions table), `#04`, `#03`, `#00` — **not `#02`**, the definitions that tie a "supply line" to
the residence premises. The model then never asked whether the property is one the forms cover,
read "burst" as sudden and accidental, and answered COVERED. Without logged context ids this
would be a guess between "retrieval missed it" and "the model ignored it".

## The field whose absence costs the time

Step 3 — judging each COVERED answer — is the slow part, and it is the step a log field could
remove. **The missing field is a per-trace verdict written at log time**: an online check on
every COVERED answer (judge verdict, or at least "forms on file vs property the loss is at"), so
the find becomes one command: `find.py --position COVERED --verdict FAIL`. Indexing the output
position was what made step 2 possible at all — a log that only indexed the question would have
left 24 traces to read.

## Note on the drill set-up

The app answered 12 of 13 written trap claims correctly (clear single exclusions: vacancy, heat,
pollutants, cosmetic hail, seepage, sump maintenance). It fails on the property / wrong-form
question, and not every time: the same C13 notes came back COVERED, DENIED and UNDETERMINED on
three runs at temperature 0 — which is why `plant.py` retries until the app really says COVERED.
