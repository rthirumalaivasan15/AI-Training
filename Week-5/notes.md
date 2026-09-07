# Week 5 — reading notes

Everything behind [taxonomy.md](taxonomy.md): how the sample was drawn, the 20
verbatim open-coding sentences, the replay evidence, the redaction confirmation,
the committed prediction, the benchmark note, and the demo-set comparison.

---

## 1. The population, and how the 20 were drawn

117 desk traces in `traces/traces.jsonl`, one JSON line per answered question,
written by `assistant.py` while it ran the 117 file-note questions in
`questions.py`. Zero errors. The questions were written before anything was run
and carry no expected answers, so nothing about the mix was steered toward
failures I already knew about.

**Seed: `20250907`.** Reproduce the exact 20 with:

```
python sample.py --seed 20250907 --n 20
```

`sample.py` sorts trace ids before sampling, so file order cannot affect the draw.
The 20 it returns:

| # | trace_id | question (as stored, redacted) |
|---|---|---|
| 1 | `trc_a0521a2a4b54` | Water came in under the patio door in heavy rain. Which code? |
| 2 | `trc_4ab44f82de51` | Insured already had the roof replaced before we got out there. Where does that leave us? |
| 3 | `trc_e96892e58854` | Does E-61 apply to a dwelling the owner lives in himself? |
| 4 | `trc_9e882d3e58fa` | Landlord says he shut the water off but did not drain the lines. Does the E-61 exception still apply? |
| 5 | `trc_df4ab8c54cd4` | Empty 22 days, pipe burst, heat was on. Do we pay? |
| 6 | `trc_a687786ef7a2` | Hail dented the metal roof but it still sheds water and there are no leaks. Does E-22 apply? |
| 7 | `trc_8e82dd5b0f49` | What is the per loss event limit on the water backup form? |
| 8 | `trc_e097c47d5b10` | Which policy line is DP-0703 written for? |
| 9 | `trc_553666e6bfb2` | Does any of our water wording cover mould that grew after the leak? |
| 10 | `trc_57e54da01664` | Does failing to inspect void the whole claim or just the exception? |
| 11 | `trc_879ba2de4572` | Loss is 14,000 dollars from a sewer backup, HO-0820 is attached. What do we pay? |
| 12 | `trc_f308ef72eaf0` | water damage exclusions please |
| 13 | `trc_e9abe000f215` | Homeowners policy, burst pipe in a rental unit the insured owns elsewhere. Which form applies? |
| 14 | `trc_0a9ec387b511` | What makes something a home business under HO-0509 - is there a dollar threshold? |
| 15 | `trc_97137ed2613e` | Two separate backups four days apart. One limit or two? |
| 16 | `trc_85ee791db7cf` | What is the sublimit for business property kept at the house? |
| 17 | `trc_d409efed88cc` | What is our subrogation deadline against the plumber? |
| 18 | `trc_d3acaa7cce0d` | Does E-32 have an exception for unpaid professional advice? |
| 19 | `trc_99613f4f2842` | Makes candles at home, cleared about 8,000 dollars last year. A customer tripped in the driveway. Are we on cover for the liability? |
| 20 | `trc_63bee0126a62` | Do we pay to upgrade beyond the minimum the code requires if the contractor recommends it? |

---

## 2. Open coding — one sentence per trace, what I saw

Written while reading, before any grouping existed. No fixes were applied at any
point during this pass; the answering pipeline is byte-identical to what wrote
the traces, and `git log` shows no commit touching it.

1. **`trc_a0521a2a4b54`** — Answered "E-15" for rain coming in under a patio door and cited the exclusions row, while the definitions chunk that says what surface water means was not one of the three chunks fetched.
2. **`trc_4ab44f82de51`** — Wrote four sentences ending in "the insurer can deny the claim", where the clause it cited says the insured must not authorise repairs before inspection but does not say what happens if they do.
3. **`trc_e96892e58854`** — Said E-61 does not reach an owner-occupied dwelling and pointed at the scope clause limiting the endorsement to tenant-occupied rentals.
4. **`trc_9e882d3e58fa`** — Said the E-61 exception fails because the lines were not drained, then added that the 7-day inspection duty "further confirm[s]" exclusion, although nothing in the question says whether an inspection happened.
5. **`trc_df4ab8c54cd4`** — Decided a 22-day-vacancy burst pipe is payable by putting the homeowners E-17 exception and the dwelling-fire E-61 threshold into one determination, and called the burst "sudden and accidental" without going near the 14-day definition.
6. **`trc_a687786ef7a2`** — Said E-22 applies to a dented metal roof that still sheds water, quoting "excluded absolutely" from the row it cited.
7. **`trc_8e82dd5b0f49`** — Gave 10,000 dollars per loss event and cited the coverage grant.
8. **`trc_e097c47d5b10`** — Answered dwelling-fire and cited the form header chunk.
9. **`trc_553666e6bfb2`** — Returned NOT_IN_DOCUMENTS in 555 ms with `refused_by` recorded as "score floor" and no model scratchpad, and I could not find mould wording anywhere in the six endorsements.
10. **`trc_57e54da01664`** — Answered that failing to inspect voids only the E-61 exception and not the whole claim, quoting the landlord duties clause.
11. **`trc_879ba2de4572`** — Took 14,000 dollars down to a 9,000 dollar payment over four sentences, each one ending in a chunk id.
12. **`trc_f308ef72eaf0`** — Asked for "water damage exclusions", it listed E-61 and E-62 from the rental dwelling-fire endorsement and never mentioned E-15 to E-18; its own scratchpad noted the HO-0304 Water Damage Exclusions header was in context "but no details given" and the answer did not pass that on.
13. **`trc_e9abe000f215`** — Said the homeowners form applies and the dwelling-fire endorsement does not, citing one chunk from each.
14. **`trc_0a9ec387b511`** — Gave the 5,000 dollar gross receipts threshold out of the definitions clause.
15. **`trc_97137ed2613e`** — Returned NOT_IN_DOCUMENTS on whether two backups four days apart draw one limit or two, and the chunk carrying "up to 10,000 dollars per loss event" was not among the three fetched.
16. **`trc_85ee791db7cf`** — Gave 2,500 dollars for business property at the house and cited the limits clause.
17. **`trc_d409efed88cc`** — Returned NOT_IN_DOCUMENTS for a subrogation deadline, and I could find no subrogation wording in the corpus.
18. **`trc_d3acaa7cce0d`** — Said E-32 has no exception and quoted the "None" entry from the row.
19. **`trc_99613f4f2842`** — Returned NOT_IN_DOCUMENTS on whether a home business liability claim is on cover, having fetched the definitions, the property sublimits and the form header, while the exclusions table holding E-31 was not fetched.
20. **`trc_63bee0126a62`** — Returned NOT_IN_DOCUMENTS in 1157 ms with `refused_by` recorded as "score floor" and no scratchpad, while the covered-costs clause saying the insurer pays the minimum the ordinance requires sat at rank 1.

### Where each sentence landed

| Mode | Traces |
|---|---|
| 1 — answering clause existed but was not fetched | 15, 19 |
| 2 — consequence attached to a clause that states none | 2, 4 |
| 3 — answered from whichever endorsement came back | 12 |
| 4 — exception applied without its definition | 5 |
| 5 — refused on the retrieval score, without reading | 20 |
| clean | 1, 3, 6, 7, 8, 9, 10, 11, 13, 14, 16, 17, 18 |

Trace 9 fired the same guard as trace 20 but the corpus really is silent on mould,
so the output was right. I did not count it as a failure, and I am flagging it
because counting it would have doubled mode 5 for free.

---

## 3. Replay evidence

Trace picked by a second seeded draw so it could not be chosen after the fact:

```
python sample.py --replay-pick        # seed 20250907 + 1 -> trc_5841988ca869
python replay.py trc_5841988ca869
```

`replay.py` reaches into nothing live. It takes the chunk ids off the trace and
looks them up in the pinned corpus, takes the prompt by its recorded version id,
and takes the model and params off the trace. It refuses to run at all if the
corpus fingerprint or the prompt sha has moved since the trace was written.

**Question:** Sump pump battery was never changed, pump died in the storm,
basement took water. Does E-51 apply?

| field | value from the trace |
|---|---|
| retriever / k | hybrid / 3 |
| chunks + scores | `HO-0820_05-24#05` 0.0325, `HO-0820_05-24#06` 0.0323, `HO-0304_03-24#05` 0.0312 |
| model | `openai/gpt-oss-120b` |
| params | `{"temperature": 0}` |
| prompt | `claims-sys-v1`, sha `cf9e36e42056` |
| corpus | sha matched, 48 chunks |

**ORIGINAL**
> Yes, E‑51 applies because the loss resulted from the insured's failure to keep the sump pump in working order – the battery was never replaced, which is a breach of the required maintenance duty [HO-0820_05-24#05] [HO-0820_05-24#06].

**REPLAYED**
> Yes, E‑51 applies because the water backup resulted from the insured's failure to keep the sump pump in working order, as defined in the exclusion table for this endorsement [HO-0820_05-24#05]. The policy also requires the insured to test the sump pump and retain proof of battery‑backup replacement within the 24 months before a loss, which was not done in this case [HO-0820_05-24#06].

### What reconstructed and what did not

Reconstructed exactly: the three chunk ids and their scores, the context block
built from them, the prompt, the model, the params, the decision (E-51 applies)
and both citations.

**Not reconstructed: the wording, byte for byte.** No field was missing — every
field the brief lists is in the trace — so I went looking for the cause rather
than assuming one. Replaying three more times gave three *different* answers, all
reaching E-51 and citing the same two chunks. Adding `seed: 7` to the params and
running three more times still gave three different answers. So this provider does
not return token-identical output at temperature 0 even with a seed pinned, and
byte-identical replay is not available here at all. What a trace can promise is
that the same inputs produce the same *determination and citations*, and that is
what it delivered.

---

## 4. Redaction

**Claimant names, claim numbers, policy numbers, phones, emails and addresses are
removed inside `trace.write()` before `json.dumps` is called, so an identifier
never exists in `traces.jsonl` at any point — this is not a cleanup pass over an
already-written file, and there is no function in `redact.py` that opens one.**

`selftest.py` checks this mechanically and passes 28 of 28, including that no raw
identifier is present in the bytes on disk. The writer raises rather than writing
if a structured identifier survives.

### The first run leaked, and I threw it away

The first 117 traces were written with a redactor that only matched two
capitalised words in a row. **Three of those 117 leaked a bare claimant first
name**, because the model echoes the claimant back mid-sentence — "which Rebecca
did by draining the system" — and one word does not match a two-word rule. The
same rule went wrong in the other direction and turned "Water Backup and Sump
Discharge Coverage" into "Water Backup and [NAME] Coverage".

I deleted that trace file, fixed both, and re-ran all 127 questions. The fix is
in `redact.py`: the writer now collects the name tokens it found anywhere in a
record and sweeps those single tokens through every field, and the stoplist that
protects policy vocabulary is derived from the corpus itself rather than
hand-written. Re-scanned after the re-run: **0 leaks in 117 desk traces and 0 in
10 demo traces.**

This cost a full re-run and a fresh draw, and it happened before open coding
started, not during it. I am recording it because a privacy control that is 97%
effective is not a privacy control, and because the alternative was writing a
confirmation line I could not stand behind.

---

## 5. The committed prediction

**Commit `3f4ab4d5206eaf541a2cc03652b5e82b33aa6372`** — "Week 5: dated
prediction, committed before any fix", 2026-09-07.

Full text in [PREDICTION.md](PREDICTION.md). In one line: remove the 0.35
dense-score floor from `assistant.py` and let the model's own NOT_IN_DOCUMENTS
rule be the only refusal path; expect score-floor refusals to go from 19/117 to
0/117, at least 12 of those 19 to come back citing a chunk that actually holds
the answer, at most 3 to come back unsupported, and total refusals to fall from
39/117 into a 20-28 band.

Committed with the answering pipeline untouched. `git log` shows no commit
touching `assistant.py`, `search.py`, `hybrid.py`, `index.py` or `ingest.py`
before it.

---

## 6. Why a public benchmark would have missed the top three modes

A public retrieval benchmark scores whether the right passage came back, and four
of my five modes happen *after* the right passage came back or *instead of*
reading it — mode 2 attaches a denial to a clause that states no consequence and
mode 4 skips a definition, both while holding correct context, and neither is
visible to a metric that stops at retrieval. The modes that do involve retrieval
are invisible for a different reason: mode 5 never reaches the retriever's output
at all because a hand-set 0.35 threshold short-circuits ahead of it, and no
benchmark ships with my threshold in it. And the thing that makes mode 3 a
failure — that E-15 through E-18 belong to the homeowners water form and E-61
through E-62 belong to the rental dwelling-fire form, so answering one from the
other is a wrong-form answer rather than a near-miss — is a fact about my six
endorsements that no general corpus encodes, which is why a benchmark would have
scored that answer as a clean hit on a relevant passage.

---

## 7. Bonus — the demo set, and what we have been telling ourselves

The 10 questions we bring to the monthly review, in `questions.DEMO_SET`, run
through the same pipeline into `traces/demo.jsonl` and open-coded the same way.

**Nine of ten were clean.** The one failure was `trc_2dbba8731e13`, "How much can
we pay for work laptops taken to a client office and stolen there?", refused by
the score floor at a dense score of 0.282 without a model call, while the clause
setting 500 dollars for business property away from the premises sits in the
corpus.

### The two numbers

| | random sample of 20 | demo set of 10 |
|---|---|---|
| **top mode** — answering clause existed but was not fetched | **2 of 20 = 10%** | **0 of 10 = 0%** |
| any failure at all | 7 of 20 = 35% | 1 of 10 = 10% |

### The paragraph

For a month we have been showing a set of questions whose answers each live in
one self-contained chunk — the 10,000 dollar limit, the 5,000 dollar threshold,
the "excluded absolutely" row — and every one of them retrieves that chunk at or
near rank 1. We picked them, without ever deciding to, for the property that
makes this assistant look good, and then we read the resulting 90% back to
ourselves as a hit rate. The random draw says the desk sees 35% failures, three
and a half times what the review sees, and the gap is not the model getting worse
on harder questions. It is that real file notes ask things whose answer is spread
across a definition and an exclusion, or that name a form whose clauses never come
back, and none of those are in the demo set. The uncomfortable part is that the
demo set is not even wrong about the app — it is an accurate picture of the app on
ten questions we chose — and that is exactly why nobody noticed. What we have been
telling ourselves is that we tested it. What we did was show it.

---

## 8. Caveats I would put in the ticket

1. **Twenty traces.** One trace moves any frequency by 5 points. Modes 3, 4 and 5
   are one trace each; they are real but their ordering against each other is not
   settled by this sample.
2. **Mode 5 is the only count I checked against the whole file**, where it is
   16% rather than 5%. Modes 1 to 4 are sample-only and not extrapolated.
3. **I judged correctness myself**, against the six endorsements, with no second
   reader. Trace 13 and trace 1 were the two closest calls and I put both in the
   clean column; moving either would take failures to 8 of 20.
4. **The traffic is my own writing.** It is not a real desk log, and if adjusters
   phrase things differently the mix of modes moves with it.
5. **The app traced is the shipped one**, which uses `hybrid_search` even though
   Week 4 measured dense as the better retriever on hit-rate@3. I did not change
   it, because a taxonomy is only about the app it was read from.
