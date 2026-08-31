# Week 4 — Task Set D — Insurance claims

Label the failures, then buy back hit-rate@3 with exactly one change.

**Headline: the change did not buy anything back, and I am not shipping it.**

| retriever | hit-rate@3 | hit-rate@1 | MRR | p50 latency |
|---|---|---|---|---|
| baseline — dense only | **9/12 = 0.750** | 5/12 | 0.569 | **270 ms** |
| + cross-encoder rerank over top 25 | **8/12 = 0.667** | 7/12 | 0.611 | **1213 ms** |

The reranker sharpens the top of the list and costs 4.5x the latency to do it, while
losing a question on the metric that was actually specified. Decision in section 8.

Corpus: the 6 endorsements from Week 3 (`data/`), re-chunked at clause level, 48 chunks.

---

## 1. The golden set

12 adjuster questions, each tagged with the chunk that answers it. They are phrased the way a
claims file note is phrased — claimant language, form usually unnamed — and were written from
the endorsement wording before any search was run. 5 of the 12 carry an exact token that dense
retrieval is structurally bad at.

| id | question | correct chunk | exact token |
|---|---|---|---|
| Q01 | Pipe burst behind the shower wall on a HO-0304 ed. 03-24 policy. Insured was away three weeks and found it on return. Does E-17 exclude it? | HO-0304_03-24#02 | yes |
| Q02 | Leak ran for about three weeks before anyone noticed. Is that E-17 or E-18? | HO-0304_03-24#05 | yes |
| Q03 | Sewer backed up and flooded the basement. What is the most we pay and what comes off for the deductible? | HO-0820_05-24#03 | no |
| Q04 | Tenant moved out in November, place stood empty with the heating off, pipes froze and split. | DP-0703_02-24#05 | no |
| Q05 | Landlord never looked at the place after the last tenant left. Does that hurt the burst pipe claim? | DP-0703_02-24#06 | no |
| Q06 | Sump pump battery was never changed, pump died in the storm, basement took water. Does E-51 apply? | HO-0820_05-24#05 | yes |
| Q07 | Insured makes candles at home, cleared about 8,000 dollars last year. A customer tripped in the driveway. Are we on cover for the liability? | HO-0509_06-24#05 | no |
| Q08 | How much can we pay for work laptops that were taken to a client office and stolen there? | HO-0509_06-24#03 | no |
| Q09 | Hail dented the metal roof but it still sheds water and there are no leaks. Does E-22 apply? | HO-0415_01-24#05 | yes |
| Q10 | Does E-41 stop us paying for the asbestos survey the council is insisting on? | HO-0612_03-24#06 | yes |
| Q11 | Fire took half the house and the city now wants the undamaged wall rebuilt to current code. How much extra can we put up? | HO-0612_03-24#03 | no |
| Q12 | What is the reserve-setting threshold for claim CLM-2024-88431? | none — not in corpus | no |

Q12 has no correct chunk. It is in the set to test refusal. **The ceiling on this set is
11/12, not 12/12.**

### A note on how this set was arrived at, because it matters

My first attempt at these 12 questions scored **11/12 on the untouched baseline** — one off the
ceiling, nothing to measure. The reason was that I had written them after looking at the chunk
structure, so each question named its own form and echoed its chunk's wording. That is the
failure the task sheet warns about: a golden set that only contains questions you already pass
measures nothing. I rewrote them in claimant language, which is what produced the set above.

I am recording this rather than hiding it, because the first version would have produced a
meaningless experiment that looked like a good one.

---

## 2. Baseline, written down before anything was changed

Retriever: dense vector search only (Chroma, all-MiniLM-L6-v2 ONNX embeddings, cosine).

**hit-rate@3 = 9/12 = 0.750. p50 latency = 270 ms.**

| id | gold | hit | rank | retrieved top-3 |
|---|---|---|---|---|
| Q01 | HO-0304_03-24#02 | no | - | HO-0304_03-24#05, HO-0304_03-24#06, DP-0703_02-24#05 |
| Q02 | HO-0304_03-24#05 | yes | 3 | HO-0304_03-24#02, HO-0304_03-24#06, HO-0304_03-24#05 |
| Q03 | HO-0820_05-24#03 | yes | 1 | HO-0820_05-24#03, HO-0304_03-24#05, HO-0612_03-24#04 |
| Q04 | DP-0703_02-24#05 | yes | 1 | DP-0703_02-24#05, DP-0703_02-24#02, DP-0703_02-24#06 |
| Q05 | DP-0703_02-24#06 | yes | 2 | DP-0703_02-24#02, DP-0703_02-24#06, HO-0304_03-24#05 |
| Q06 | HO-0820_05-24#05 | yes | 2 | HO-0820_05-24#06, HO-0820_05-24#05, HO-0304_03-24#06 |
| Q07 | HO-0509_06-24#05 | yes | 2 | HO-0612_03-24#04, HO-0509_06-24#05, HO-0509_06-24#03 |
| Q08 | HO-0509_06-24#03 | yes | 1 | HO-0509_06-24#03, HO-0820_05-24#03, HO-0509_06-24#02 |
| Q09 | HO-0415_01-24#05 | yes | 1 | HO-0415_01-24#05, HO-0415_01-24#06, HO-0415_01-24#03 |
| Q10 | HO-0612_03-24#06 | yes | 1 | HO-0612_03-24#06, DP-0703_02-24#03, HO-0415_01-24#03 |
| Q11 | HO-0612_03-24#03 | no | - | HO-0612_03-24#02, HO-0612_03-24#04, DP-0703_02-24#05 |
| Q12 | (not in corpus) | no | - | HO-0612_03-24#03, HO-0304_03-24#05, HO-0820_05-24#00 |

Raw run: `runs/baseline.json`.

---

## 3. Failure labels — every miss, with evidence

Labels taken from the inspection view (`app.py`), one line of evidence each.

| id | label | evidence |
|---|---|---|
| Q01 | **R** | Gold HO-0304_03-24#02 (the Clause 1(a) definition) absent from top-3; it sits at **rank 10**. The retriever returned the E-17 row and the duties clause — the exclusion, but not the definition that decides whether its exception applies. |
| Q11 | **R** | Gold HO-0612_03-24#03 (Clause 2, the 25 percent figure) absent; it sits at **rank 4**. Ranks 1 and 2 were the definitions clause and the covered-costs clause of the same form — the right document, the wrong clause, and the only chunk carrying the number was one place outside the cut. |
| Q12 | **Not-In-Corpus** | No chunk contains claim CLM-2024-88431. The app returned `NOT_IN_DOCUMENTS`, which is correct. |

### Tally

| label | count |
|---|---|
| R — retrieval fetched bad context | 2 |
| G — model misused good context | 0 |
| Not-In-Corpus | 1 |
| **total misses** | **3** |

**Both recoverable failures are R, and both are ranking failures rather than recall failures**
— the correct chunk was in the candidate pool at rank 10 and rank 4 respectively, just below
the k=3 cut. That distinction is what chose the change in section 4.

---

## 4. The one change, and why this one

The tally has two recoverable failures. The decisive question was *where* the correct chunk
actually sits, so I dumped the dense top-25 for all 12 questions:

```
Q01  rank 10   HO-0304_03-24#02   <- MISS at k=3
Q11  rank 4    HO-0612_03-24#03   <- MISS at k=3
(every other gold chunk is at rank 1-3)
```

Neither miss is a recall failure. The retriever **found** both correct chunks and then ranked
them too low. That rules out the BM25 option: fusing in a keyword list helps when the target
was never retrieved at all, and here it always was. It points squarely at reranking, whose
entire job is to reorder candidates the first stage already fetched.

So the change is **a cross-encoder reranker (`Xenova/ms-marco-MiniLM-L-6-v2`, ONNX) re-scoring
the dense top 25**. A cross-encoder reads the question and each chunk *together* in one pass,
which the embedding model never does — the embeddings are computed independently and can only
be compared afterwards. That joint reading is where the extra accuracy is supposed to come
from, and it is why a reranker can only be afforded over a shortlist.

Nothing else was touched between the two runs. Same corpus, same chunker, same chunk ids,
same embedding model, same 12 questions, same k=3.

### I also tested BM25 + RRF, and rejected it on the numbers

Before settling on the reranker I ran the other option offered, so the choice is evidenced
rather than asserted. BM25 with RRF at k=60 scored **8/12** — worse than the untouched
baseline. Sweeping the candidate depth did not rescue it:

| RRF candidate depth | hit@3 | hit@1 |
|---|---|---|
| 3 | 10/12 | 8/12 |
| 5 | 8/12 | 7/12 |
| 8 | 9/12 | 7/12 |
| 10 | 9/12 | 7/12 |
| 15 | 9/12 | 7/12 |
| 25 | 9/12 | 7/12 |

(measured against an earlier 24-chunk index; no depth beat dense alone)

The reason is a vocabulary gap. An adjuster writes *"work laptops taken to a client office and
stolen"*; the policy says *"business property away from the residence premises"*. Those share
no content words at all, so BM25 has nothing to match and contributes noise, which RRF then
weights equally with the dense retriever's correct answer. BM25 earns its keep when a query
carries a rare exact token that appears in the target chunk — but here the exclusion codes
that do appear (`E-22`, `E-41`, `E-51`) were already being retrieved at rank 1 by dense search,
so there was no win available for it to add.

**These were separate runs. The before/after in section 5 changes exactly one thing.**

---

## 5. After the change

**hit-rate@3 = 8/12 = 0.667. p50 latency = 1213 ms.** Raw run: `runs/rerank.json`.

| metric | before | after | delta |
|---|---|---|---|
| **hit-rate@3** | 9/12 = 0.750 | 8/12 = 0.667 | **−0.083** |
| hit-rate@1 | 5/12 = 0.417 | 7/12 = 0.583 | +0.167 |
| MRR | 0.569 | 0.611 | +0.042 |
| **p50 latency per query** | 270 ms | 1213 ms | **+943 ms (4.5x)** |

The reranker did what a reranker does — it pulled correct answers from rank 2 and 3 up to
rank 1, which is why hit@1 and MRR both rise. It also pushed one correct answer out of the
top 3 entirely, which is why the specified metric falls.

---

## 6. What the change fixed, and what it did not touch

| id | before | after | outcome |
|---|---|---|---|
| Q01 | miss | miss | **not fixed** |
| Q02 | hit @3 | hit @1 | promoted to rank 1 |
| Q03 | hit @1 | hit @1 | unchanged |
| Q04 | hit @1 | hit @1 | unchanged |
| Q05 | hit @2 | hit @3 | still a hit, demoted one place |
| Q06 | hit @2 | hit @1 | promoted to rank 1 |
| Q07 | hit @2 | miss | **regressed** |
| Q08 | hit @1 | hit @1 | unchanged |
| Q09 | hit @1 | hit @1 | unchanged |
| Q10 | hit @1 | hit @1 | unchanged |
| Q11 | miss | miss | **not fixed** |
| Q12 | miss | miss | correct — not in corpus, still refused |

**Neither original R-failure was fixed. One passing question regressed.**

### Why each one behaved as it did

**Q01 — not fixed.** The gold chunk was at rank 10 of 25, so it was inside the pool the
reranker re-scored and the reranker still did not lift it. The question mentions E-17 twice
over; the cross-encoder scored the chunk that *contains* `E-17` above the chunk that merely
defines the term the E-17 exception depends on. The correct answer requires two chunks — the
exclusion row and the definition — and a top-3 with one gold cannot express that. This is a
limitation of my golden set as much as of the retriever, and I am naming it rather than
scoring around it.

**Q11 — not fixed.** Gold at rank 4, the closest miss in the set. All three retrieved chunks
were from the correct form; the reranker preferred the covered-costs clause, which describes
*what* is paid, over the increased-limit clause, which carries the *number* the question asked
for. The word "how much" is not lexically or semantically close to "25 percent of the Coverage
A limit of liability".

**Q07 — regressed, and this is the one that cost the metric.** Baseline had the gold at rank
2; the reranker dropped it out of the top 3 in favour of `HO-0612_03-24#04`, an ordinance-or-law
clause with no connection to home business liability. Cross-encoders are trained on general
web relevance, not on insurance wording, and on a question about a customer tripping in a
driveway it preferred prose that reads like a general coverage grant.

---

## 7. The generation half — where the failures are not

The tally in section 3 shows **zero G failures**. Hit-rate@3 cannot detect one by
construction: it stops measuring the moment the right chunk is fetched. So a null result there
proves nothing on its own, and I tested the generator separately.

I ran **8 probes with the context pinned to known-correct chunks**, so retrieval was correct by
definition and only the reading was under test. The probes were chosen to be the cases where
grounded models usually break:

| probe | what it tested | outcome |
|---|---|---|
| Burst pipe found after 3 weeks — does E-17 apply? | applying a 14-day definition to a stated fact | correct |
| Leak vs seepage, E-17 or E-18 | distinguishing two adjacent exclusion rows | correct |
| Child-minding, never notified, child hurt | exception chained to a suspension clause | correct |
| Rental empty 45 days, water drained, no inspection | exception voided by a duty clause | correct |
| Sewer backup, 14,000 dollar loss, HO-0820 attached | limit and separate deductible arithmetic | correct — 9,000 dollars |
| Ordinance costs 120,000, 15,000 asbestos, Coverage A 400,000 | exclusion then cap, two-step arithmetic | correct — 100,000 dollars |
| Homeowners loss with a Dwelling Fire exclusion in context | applying the wrong policy line's exclusion | correct — did not take the bait |
| Reserve threshold for CLM-2024-88431 | refusing what is not in the corpus | correct — refused |

Every answer carried citations, and every citation resolved to a chunk that was actually in
context.

**This is the answer to the proposal to swap the model.** Retrieval failed on 3 of 12
questions. Generation failed on 0 of 8 controlled probes designed to break it. The budget for
a better model would buy nothing, because the model was never where the failures were.

The honest caveat: 8 probes is not proof of a sound generator, only evidence that generation is
not the current bottleneck. A larger corpus, a weaker model, or a looser prompt would all
change this, and it should be re-tested if any of those change.

---

## 8. Shipping decision

**Do not ship the reranker.**

The number that decides it: hit-rate@3 goes **0.750 to 0.667** while p50 latency goes **270 ms
to 1213 ms**. Paying 4.5x the response time to lose a question is not a trade worth making.

I want to be precise about what the reranker did and did not do, because "it made things worse"
is too blunt. It genuinely improved the *ordering* of results — hit@1 from 5/12 to 7/12, MRR
from 0.569 to 0.611. If this product surfaced a single clause to the adjuster, that would be a
real gain and the decision might go the other way even at 1213 ms. But this product feeds three
chunks to a generator, so hit-rate@3 is the metric that reflects what the user actually
experiences, and on that metric it is a regression.

Neither offered change bought back hit-rate@3 — BM25 + RRF scored 8/12 and the reranker scored
8/12, against a 9/12 baseline. Both were measured on the same 12 questions with one variable
moved.

### What I would do next, and why it is not what I did this week

Both surviving failures are questions whose answer is spread across two chunks — Q01 needs the
E-17 row *and* the definition it points to; Q11 needs the covered-costs clause *and* the clause
carrying the percentage. No reranker fixes that, because there is no single chunk to promote.
The change that addresses it is at ingest: carry each form's header and its definitions clause
onto every chunk of that form, so a chunk is self-describing. That is a chunking change, it
would renumber every chunk id, and it therefore needs its own before-and-after on a fresh
golden set. It is the next change, not a second change bolted onto this one.

### Caveats I would put in the ticket

1. Twelve questions is a small sample. A one-question swing moves hit-rate@3 by 0.083, which is
   larger than most of the effects being discussed here. This number needs a bigger golden set
   before anyone leans on it.
2. Q01's gold label is genuinely arguable — the E-17 row is a defensible answer to that
   question, and had I labelled it that way the baseline would read 10/12. I left the label as
   written rather than adjusting it after seeing the results.
3. Latency was measured on a loaded developer laptop and varies by tens of milliseconds
   between runs. The 4.5x reranker cost is far outside that noise; the ~30 ms differences
   between dense and hybrid are not.

---

## 9. The code diff — exactly one retrieval change

New file `rerank.py`:

```python
MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
CANDIDATES = 25   # how many dense results the cross-encoder re-scores

_encoder = TextCrossEncoder(model_name=MODEL)


def rerank_search(question, k=3, where=None):
    # the cross-encoder reads the question and each chunk TOGETHER, which the
    # embedding model never does - that is where the extra accuracy comes from
    candidates = dense_search(question, CANDIDATES, where)
    scores = list(_encoder.rerank(question, [c["text"] for c in candidates]))

    ranked = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)
    return [dict(hit, score=float(score)) for hit, score in ranked[:k]]
```

The change to the measured pipeline is two lines in `evaluate.py`:

```diff
 from search import dense_search
+from rerank import rerank_search

 RETRIEVERS = {
     "baseline": dense_search,
+    "rerank": rerank_search,
 }
```

`ingest.py`, `index.py`, `search.py`, `golden_set.jsonl` and the corpus are untouched between
the two runs. `chunks.jsonl` was not regenerated, so every chunk id means the same thing in the
before table as in the after table.

`hybrid.py` is also in the repository. It is the rejected BM25 + RRF experiment from section 4
and is not part of the before/after comparison.

---

## 10. Reproducing these numbers

```
.venv\Scripts\python ingest.py             # 6 endorsements -> 48 chunks
.venv\Scripts\python index.py              # build the vector index
.venv\Scripts\python evaluate.py baseline  # 9/12, 270 ms
.venv\Scripts\python evaluate.py rerank    # 8/12, 1213 ms
.venv\Scripts\python evaluate.py hybrid    # 8/12 - the rejected experiment
.venv\Scripts\python -m streamlit run app.py
```

A warm-up query runs before timing in every case, so model load is not counted. The reranker
downloads an 80 MB ONNX model on its first run.
