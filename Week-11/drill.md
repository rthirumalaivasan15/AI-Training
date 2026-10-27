# drill.md — finding the coverage answer that ignored the policy

**Time-to-find: not measured.** One plant was made, on 2026-10-27, but the drill was not run as
the task sets it: the same person planted and searched, there was no squadmate and no stopwatch,
and the key records the planter as a placeholder (`"Real Name Here"`). So there is no mm:ss and
no squadmate's name to report. What the attempt did show is below, and it is the more useful
result: **the search built to make the find one command missed the planted answer.**

## The plant

`drill/plant_key.json`: trap T13, a real app run at 2026-10-27 14:53 on `claims-agent-v1` (the
prompt the logged day ran), answered **COVERED under E-17** on the first try, stamped into the
2026-10-26 traffic as **`trc_0d52f79cca97`**, adj-03, 14:34:49. The claim: a townhouse the insured
rents out in another town, under the HO-3 on their own home — the same failure family as the real
bad answer below. Right answer: NOT_IN_DOCUMENTS.

## The search, and what it missed

`sweep.py` takes the output slice the complaint points at — every answer that said COVERED (8 that
day) — and has the Week-6 judge check each one, storing the verdict beside the logs:

```
2026-10-26: 8 answers said COVERED
  !!  14:32:45  trc_a4a9f492d77c  adj-04 judge FAIL  CLM-2024-20035 ...
      14:34:49  trc_0d52f79cca97  adj-03 judge PASS  CLM-2024-20076 ...   <- the plant
1 the judge says are wrong: trc_a4a9f492d77c
```

**The judge passed the planted answer**, making the app's own mistake: it applied HO-0304's E-17
exception and never asked whether a homeowners form reaches a rental property. It had failed the
earlier answer of the same family only for a wrong reason ("45 days exceeds 14"). An LLM judge is not
a reliable index for a failure it shares with the app.

## The log field whose absence costs the time

**A deterministic "decisive context missing" field.** The traces already log retrieved context ids,
and both bad answers carry the same signature: COVERED, grounds **E-17**, context
`HO-0304_03-24#05, #04, #03, #00` — **without `#02`**, the definitions chunk that ties a supply line to
the residence premises and defines sudden and accidental. Checked over all 8 COVERED answers of the
day, "cites E-17 but `#02` was not retrieved" flags exactly the two bad ones and none of the six good
ones. Written at log time (as Week 8's decisive-wording check did for trajectories), it makes the find
one filter with no model call; without it, the finder reads eight covered answers by hand.

## The real bad answer that started the loop

`trc_a4a9f492d77c` — adj-04, 14:32:45, `claims-agent-v1`: a rental condo the insured owns in another
city, answered COVERED under E-17 (Week 6 labelled this same input, C13, NOT_IN_DOCUMENTS). Found on
2026-10-26 by the output slice (`find.py --position COVERED`: 7 of 24 requests) and the judge over
those 7. Time, user, prompt version, input type and cost could not have found it: one prompt version
all day, all requests in one hour, an ordinary user and input type, and a cost at the day's lower
quartile ($0.00091; median $0.00102). The context ids gave the diagnosis in one hop — retrieval never
returned `#02`, and the model never asked whether the forms cover the property.

## The fix covers the plant too

`claims-agent-v3` on the planted claim: **NOT_IN_DOCUMENTS**, excess 1000 kept, and this time retrieval
included `HO-0304_03-24#01`, where the residence-premises scope sits. The suite's eval case does not
depend on the judge for this failure: its `expect` block requires NOT_IN_DOCUMENTS or UNDETERMINED
deterministically.

## Note on the drill set-up

The app answered 12 of 13 written trap claims correctly (clear single exclusions: vacancy, heat,
pollutants, cosmetic hail, seepage, sump maintenance). It fails on the property / wrong-form question,
and not every time: the same C13 notes came back COVERED, DENIED and UNDETERMINED on three runs at
temperature 0 — which is why `plant.py` retries until the app really says COVERED. A proper timed run
needs a second person to plant: `drill/RUNBOOK.md`.
