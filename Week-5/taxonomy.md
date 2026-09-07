# Failure taxonomy — claims assistant, 20 traces read by hand

Sample: 20 of 117 desk traces, seeded random draw, **seed 20250907**. Read on
2026-09-07 with zero code changes applied. Working from `traces/traces.jsonl`.

**13 of 20 were clean. 7 of 20 (35%) failed.** Modes below account for all 7.

| # | Failure mode | Count | % of 20 | Severity | Example |
|---|---|---|---|---|---|
| 1 | **Says the endorsements are silent when the answering clause exists but was not among the 3 chunks fetched** | 2 | 10% | Wrongly denies — adjuster is told there is no wording, and closes on that | `trc_99613f4f2842` |
| 2 | **Attaches a consequence to a clause that states no consequence** | 2 | 10% | Wrongly denies — manufactures a coverage defence the form does not give | `trc_4ab44f82de51` |
| 3 | **Answers from whichever endorsement came back, without saying the form the question named is missing** | 1 | 5% | Wrongly denies — rental-form exclusions read onto a homeowners file | `trc_f308ef72eaf0` |
| 4 | **Applies an exclusion's exception without testing the definition the exception depends on** | 1 | 5% | Wrongly pays — the 14-day test that separates a burst from seepage is skipped | `trc_df4ab8c54cd4` |
| 5 | **Returns NOT_IN_DOCUMENTS without reading the chunks at all, on the retrieval score alone** | 1 | 5% | Wrongly denies — the answering clause was sitting at rank 1 | `trc_63bee0126a62` |

## Reading these counts honestly

**A one-trace swing moves any of these by 5 points.** Modes 3, 4 and 5 rest on a
single trace each. They are real — each has a trace you can open — but their
*ordering* against each other is not something 20 traces can settle.

**Mode 5 is the one number I checked against the whole file, and the sample
understates it.** Across all 117 desk traces the score floor refuses **19 times
(16%)**, not 5%. That is why it is the mode named in `PREDICTION.md` even though
it is joint-last here. Modes 1 to 4 were counted only in the 20 and I have not
extrapolated them.

**Every mode here is claim-affecting; none is merely annoying.** That is not a
flattering finding. The four wrong-denial modes all end with an adjuster being
told a claim is not covered when the wording says otherwise, which is the
bad-faith exposure the manager was gesturing at without evidence.

**The split between wrongly-denies and wrongly-pays is 6 traces to 1.** The one
wrongly-pays trace (mode 4) is the one I would put in front of the manager first
anyway, because paying a seepage loss as a burst pipe is the error nobody
appeals and nobody catches.

Per-trace observation sentences, the full sampled id list, replay evidence and
the demo-set comparison are in [notes.md](notes.md).
