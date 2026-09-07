# Dated prediction — written 2026-09-07, before any fix

Committed before a single line of the answering pipeline was changed. Nothing in
`assistant.py`, `search.py`, `hybrid.py`, `index.py` or `ingest.py` has moved
since the 117 traces were written.

## The mode I will attack

**Mode 5 — "Returns NOT_IN_DOCUMENTS without ever reading the chunks, because the
retrieval score was below 0.35."**

Not the most frequent mode in the sample of 20, and I want to be straight about
that. It is 1 of 20 there (5%), while two other modes are 2 of 20 (10%). I am
attacking it first for three reasons that are on the record rather than on
instinct:

1. Across the full 117 desk traces it fires **19 times (16%)**, so the sample of
   20 caught one instance of something that is three times more common than a
   1-in-20 draw suggests.
2. Reading those 19, the endorsements plainly answer several of them — the
   ordinance-or-law question whose answering clause was retrieved at **rank 1**,
   the slow-drip question that E-18 covers, the washing-machine-hose question that
   E-17 covers. The assistant told the adjuster the wording is silent when it is not.
3. It is the only mode with a single-line lever, so the before/after is clean and
   one variable moves.

## The change

Delete the score-floor guard in `assistant.py`:

```python
best_dense = dense_search(question, 1)[0]["score"]
if best_dense < SCORE_FLOOR:          # SCORE_FLOOR = 0.35
    return ... REFUSAL ...
```

The model's own `NOT_IN_DOCUMENTS` rule, already in `claims-sys-v1`, becomes the
only refusal path. Retriever, k, chunker, corpus, prompt and model all stay put.

## What I expect, in numbers

Measured by re-running all 117 desk questions and re-drawing seed 20250907.

| measurement | now | after | falsified if |
|---|---|---|---|
| score-floor refusals | 19 / 117 (16%) | 0 / 117 | anything above 0 |
| of those 19, answers correctly citing a chunk that holds the answer | 0 | **at least 12** | 11 or fewer |
| of those 19, answers not supported by the retrieved chunks | 0 | **at most 3** | 4 or more |
| total NOT_IN_DOCUMENTS across 117 | 39 (33%) | **20 to 28** | outside that band |
| Mode 5 in a fresh seeded 20 | 1 / 20 (5%) | 0 / 20 | 1 or more |
| total failures in a fresh seeded 20 | 7 / 20 (35%) | **5 / 20 or fewer** | 6 or more |

"Correctly citing a chunk that holds the answer" means I open the cited chunk and
the text answers the question. I will judge those 19 by hand, the same way I read
the 20, and paste the result next to this table.

## The way this is most likely to be wrong

The floor is doing real work on the genuinely-out-of-corpus questions — the SIU
phone number, the Guidewire filing question, the auto claim. If the model starts
reaching for the nearest endorsement rather than refusing, unsupported answers go
past 3 and I will have traded a wrong denial for a wrong payment, which is the
worse of the two in a claims file. That is the number I am watching, and it is
why the ceiling is 3 and not "a few".
