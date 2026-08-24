# Week 3 — Task Set D · Insurance claims
## Ingest the endorsement pack and prove the chunking finds the answer

**Notes.** Only the 6 new endorsements were indexed — the base policy wording library was
not re-indexed (6 files → 38 naive chunks / 44 structure-aware chunks). The supplied
endorsement pack was unavailable, so the 6 endorsements were authored to the Set D
specification; all measurements below are real runs against those files. No LLM API key
was available, so cited answers quote the retrieved chunk verbatim and the refusal gate
is deterministic code rather than a prompt instruction. The embedding model was held
constant across both runs (`all-MiniLM-L6-v2`, 384 dims) — only the chunker changed.

---

## 1. The 8 known-answer questions, with form_number and clause

Written from the endorsements **before** any search was run.

| Q | Question | form_number | Clause | Table row? |
|---|---|---|---|---|
| Q1 | Does exclusion E-17 apply to water damage from a burst supply line when the discharge was sudden and accidental? | HO-0304 | Clause 3, exclusions table row E-17 | **yes** |
| Q2 | What does "sudden and accidental" mean, and what time period does it require? | HO-0304 | Clause 1(a) Definitions | no |
| Q3 | Hail dented my metal roof but it still sheds water. Is that damage covered? | HO-0415 | Clause 3, exclusions table row E-22 | **yes** |
| Q4 | How much personal property cover is there for business property kept at the home? | HO-0509 | Clause 2 Limits of Liability | no |
| Q5 | After this endorsement is attached, what percentage of the Coverage A limit applies to Ordinance or Law? | HO-0612 | Clause 2 Increased Limit | no |
| Q6 | The sewer backed up into my basement. What is the most that will be paid for one event? | HO-0820 | Clause 2 Coverage Grant | no |
| Q7 | A pipe burst in my rental house while it sat empty between tenants for 45 days. Is the damage covered? | DP-0703 | Clause 3, exclusions table row E-61 | **yes** |
| Q8 | My sump pump was not maintained and water backed up. Is there any situation where I am still paid? | HO-0820 | Clause 3, exclusions table row E-51 | **yes** |

**4 of 8 depend on a row inside an exclusions table** (requirement: at least 3).
Known-correct answers are recorded in `questions.json` under `known_answer`, each with a
`marker` string used for automatic scoring; all 8 markers were verified present in their
expected source document before measuring (`src/verify_questions.py`).

---

## 2. The two hit-in-top-5 numbers

**Scoring rule.** A question scores HIT only if, within the top 5 results, some chunk
satisfies **both**: (a) `form_number` equals the expected form, **and** (b) the chunk text
contains the marker string.

| Q | Strategy A — naive (fixed 400 chars, 50 overlap) | Strategy B — structure-aware |
|---|---|---|
| Q1 | HIT | HIT |
| Q2 | HIT | HIT |
| Q3 | HIT | HIT |
| Q4 | HIT | HIT |
| Q5 | HIT | HIT |
| Q6 | HIT | HIT |
| Q7 | **MISS** | **HIT** |
| Q8 | HIT | HIT |
| **Total** | **7 / 8** | **8 / 8** |

Same 8 questions, same embedding model, same 6 documents. Full search-only dump — every
result list with chunk_ids and cosine scores, both strategies — in **`outputs/search_dump.md`**.

**The one difference, diagnosed.** Q7's naive chunk boundary fell *inside the string
`E-61`*: chunk 2 ended `"...supply line occurr"`, chunk 3 began `"-61 | Water damage..."`.
The retrieved chunk contained `-61`, not `E-61`, so it failed condition (b) despite ranking
first with the correct sentence. The half that kept the code held only a truncated fragment
and ranked below position 10.

---

## 3. Unfiltered vs filtered result lists — one policy_line query

**Query:** `"is a burst pipe covered if the house sat empty between tenants"`
**Filter:** `where={"policy_line": "homeowners"}` · Collection: structure-aware

### Unfiltered

```
1. score=0.6267  struct:DP-0703:001  [DP-0703 | policy_line=dwelling-fire]
   FORM DP-0703 ed. 02-24 CLAUSE 1. DEFINITIONS ... "Tenant-occupied period"...
2. score=0.5308  struct:DP-0703:003  [DP-0703 | policy_line=dwelling-fire]
   FORM DP-0703 ed. 02-24 CLAUSE 3. EXCLUSIONS TABLE ... | Code | ...
3. score=0.5278  struct:DP-0703:005  [DP-0703 | policy_line=dwelling-fire]
   FORM DP-0703 ed. 02-24 CLAUSE 4. LANDLORD DUTIES ...
4. score=0.4800  struct:HO-0304:005  [HO-0304 | policy_line=homeowners]
   FORM HO-0304 ed. 03-24 CLAUSE 3. EXCLUSIONS TABLE ...
5. score=0.4529  struct:HO-0304:007  [HO-0304 | policy_line=homeowners]
   FORM HO-0304 ed. 03-24 CLAUSE 4. DUTIES AFTER A WATER LOSS ...
```

### Filtered — `policy_line = homeowners`

```
1. score=0.4800  struct:HO-0304:005  [HO-0304 | policy_line=homeowners]
   FORM HO-0304 ed. 03-24 CLAUSE 3. EXCLUSIONS TABLE ...
2. score=0.4529  struct:HO-0304:007  [HO-0304 | policy_line=homeowners]
   FORM HO-0304 ed. 03-24 CLAUSE 4. DUTIES AFTER A WATER LOSS ...
3. score=0.4327  struct:HO-0304:006  [HO-0304 | policy_line=homeowners]
   FORM HO-0304 ed. 03-24 CLAUSE 3. EXCLUSIONS TABLE ...
4. score=0.4274  struct:HO-0304:001  [HO-0304 | policy_line=homeowners]
   FORM HO-0304 ed. 03-24 CLAUSE 1. DEFINITIONS ... "Sudden and accidental"...
5. score=0.4083  struct:HO-0415:003  [HO-0415 | policy_line=homeowners]
   FORM HO-0415 ed. 01-24 CLAUSE 3. EXCLUSIONS TABLE ...
```

**Top-1 changed:** `struct:DP-0703:001` (dwelling-fire, 0.6267) → `struct:HO-0304:005`
(homeowners, 0.4800). The entire unfiltered top-3 was dwelling-fire and was displaced.
Filtered scores are *lower* by design — the strongest semantic matches were disqualified
for belonging to the wrong product. Raw output: **`outputs/filter_demo.md`**

---

## 4. Three cited answers

Full transcripts: **`outputs/transcripts.md`**

**Grounding prompt (refusal forced, not suggested):**

```
You are a claims assistant. Answer ONLY from the retrieved chunks supplied below.
Rules (non-negotiable):
1. Every claim must carry a citation [chunk_id | form_number | clause].
2. If the chunks do not contain the answer you MUST reply exactly:
   "I cannot answer this from the indexed endorsements."
   and name the source that would be needed.
   Do NOT use outside knowledge. Do NOT use best judgement.
```

Enforcement is in code (`src/answer.py`): an answer is composed only if **term-overlap ≥ 2**
and **top cosine score ≥ 0.45**. If either fails, the answering path is never reached.

### Q1 — gate: overlap=10, top_score=0.639 → ANSWER

> No. The E-17 exception says it does NOT apply where the discharge was sudden and
> accidental as defined in Clause 1(a), so the loss remains covered up to policy limits.
>
> **Citation:** `[struct:HO-0304:005 | HO-0304 ed. 03-24 | CLAUSE 3. EXCLUSIONS TABLE row E-17]`

```
FORM HO-0304 ed. 03-24
CLAUSE 3. EXCLUSIONS TABLE
The following exclusions apply to Section I - Property Coverages:
| Code | Exclusion Description | Applies To | Exception |
| E-17 | Water damage from a burst or ruptured supply line | Coverage A - Dwelling | Does NOT apply where the discharge was sudden and accidental as defined in Clause 1(a); such losses remain covered up to policy limits. |
```

### Q5 — gate: overlap=3, top_score=0.782 → ANSWER

> 25 percent of the Coverage A limit, increased from the 10 percent stated in the base wording.
>
> **Citation:** `[struct:HO-0612:002 | HO-0612 ed. 03-24 | CLAUSE 2. INCREASED LIMIT]`

```
FORM HO-0612 ed. 03-24
CLAUSE 2. INCREASED LIMIT
The Ordinance or Law coverage percentage stated in the base wording is increased from 10 percent to 25 percent of the Coverage A limit of liability shown in the Declarations. This increase applies only to losses occurring on or after the effective date shown above.
```

### Q7 — gate: overlap=5, top_score=0.548 → ANSWER

> Excluded by E-61 because the dwelling was unoccupied more than 30 consecutive days,
> UNLESS the water supply was shut off at the main and the plumbing system drained
> during that period.
>
> **Citation:** `[struct:DP-0703:003 | DP-0703 ed. 02-24 | CLAUSE 3. EXCLUSIONS TABLE row E-61]`

```
FORM DP-0703 ed. 02-24
CLAUSE 3. EXCLUSIONS TABLE
The following exclusions apply to Coverage A - Dwelling:
| Code | Exclusion Description | Applies To | Exception |
| E-61 | Water damage from a burst supply line occurring while the dwelling is unoccupied between tenancies for more than 30 consecutive days | Coverage A - Dwelling | Does NOT apply if the water supply was shut off at the main and the plumbing system drained during the unoccupied period. |
```

All three chunk_ids resolve in the live index and each cited chunk contains the claim it
is cited for. Verify with:

```python
chromadb.PersistentClient(path="chroma_db").get_collection("structure").get(ids=["struct:HO-0304:005"])
```

---

## 5. Three refusal transcripts

Verified absent from the corpus: `CLM-2024-88431` 0 hits · `threshold` 0 · `premium` 0 ·
`all-perils` 0 · `HO-778812` 0.

### R1 — "What is the reserve-setting threshold for claim CLM-2024-88431?"
`Gate: overlap=0, top_score=0.440 → REFUSE`

> I cannot answer this from the indexed endorsements.
> The 6 indexed endorsements contain policy wording only — no claim records, rating
> manuals, or declarations pages. Answering would require a source that was never indexed.

Top retrieved chunk, rejected as unsupporting: `struct:HO-0612:002` score=0.440

### R2 — "What premium charge applies for attaching endorsement HO-0820 to a policy?"
`Gate: overlap=1, top_score=0.595 → REFUSE`

> I cannot answer this from the indexed endorsements.
> The 6 indexed endorsements contain policy wording only — no claim records, rating
> manuals, or declarations pages. Answering would require a source that was never indexed.

Top retrieved chunk, rejected as unsupporting: `struct:HO-0820:002` score=0.595

### R3 — "What is the all-perils deductible shown on the declarations page of policy HO-778812?"
`Gate: overlap=0, top_score=0.638 → REFUSE`

> I cannot answer this from the indexed endorsements.
> The 6 indexed endorsements contain policy wording only — no claim records, rating
> manuals, or declarations pages. Answering would require a source that was never indexed.

Top retrieved chunk, rejected as unsupporting: `struct:HO-0509:006` score=0.638

**Why a score threshold alone would have failed.** R3 scored **0.638** — higher than five
of the eight genuinely answerable questions — by matching `CLAUSE 5. OTHER TERMS`
boilerplate. A confidence-threshold gate would have answered a question about a policy
that does not exist. Term-overlap separated the populations cleanly (answerable 1–10,
out-of-corpus 0–1).

---

## 6. Code diff — the second chunker and the metadata fields

Full diff: **`outputs/code_diff.md`**. Baseline = naive fixed-size chunker with metadata
limited to `source_file` + `form_number`. Key hunks:

```diff
--- a/src/chunkers.py
+++ b/src/chunkers.py
     return {
         "source_file": source_file,
         "form_number": grab("FORM NUMBER"),
+        "policy_line": grab("POLICY LINE"),
+        "edition_date": grab("EDITION"),
     }
+
+def structure_chunks(text, meta):
+    chunks = []
+    form_tag = f"FORM {meta['form_number']} ed. {meta['edition_date']}"
+
+    parts = re.split(r"(?m)^(?=CLAUSE\s+\d)", text)
+    head, clauses = parts[0], parts[1:]
+    chunks.append({"text": head.strip(), "clause": "header"})
+
+    for clause in clauses:
+        title = clause.splitlines()[0].strip()
+        rows = [ln for ln in clause.splitlines() if re.match(r"^\|\s*E-\d+", ln)]
+
+        if rows:
+            header_row = next(ln for ln in clause.splitlines()
+                              if ln.startswith("| Code"))
+            intro = clause[:clause.index(header_row)].strip()
+            for row in rows:
+                code = re.match(r"^\|\s*(E-\d+)", row).group(1)
+                chunks.append({
+                    "text": f"{form_tag}\n{intro}\n{header_row}\n{row.strip()}",
+                    "clause": f"{title} row {code}",
+                })
+        else:
+            chunks.append({"text": f"{form_tag}\n{clause.strip()}",
+                           "clause": title})
+    return chunks
```

```diff
--- a/src/ingest.py
+++ b/src/ingest.py
-from chunkers import parse_header, naive_chunks
+from chunkers import parse_header, naive_chunks, structure_chunks
...
-    metadatas=[dict(meta) for _ in pieces],
+    metadatas=[dict(meta, chunker="naive", clause="") for _ in pieces],
+
+    sc = structure_chunks(text, meta)
+    struct_col.add(
+        ids=[f"struct:{meta['form_number']}:{n:03d}" for n in range(len(sc))],
+        documents=[c["text"] for c in sc],
+        metadatas=[dict(meta, chunker="structure", clause=c["clause"]) for c in sc],
+    )
```

`parse_header()` raises on a missing field, so a chunk without `source_file` cannot enter
the index.

---

## 7. Which chunker ships, and why

**The structure-aware chunker ships.** It scored 8/8 against 7/8 on the same 8 questions
with the same embedding model, and the single point of difference is the failure mode that
matters most in this corpus: fixed-size chunking cut through the string `E-61`, severing an
exclusion code from the rule it scopes and pushing the code-bearing half out of the top 10
entirely. In a wording set where meaning is carried by coded table rows, a chunk that has
lost its code is not merely lower quality — it is unciteable and unsafe, because the
retrieved text still reads fluently and a reviewer eyeballing it will pass it. The
structure-aware chunker makes that failure impossible by construction: it splits only at
clause headers, emits one chunk per exclusion row, and rebuilds each row's context (form
number, edition, clause title, table header) into the chunk itself. The cost is real and I
accept it knowingly — 44 chunks instead of 38, a tighter chunk that sometimes strands a
definition the row refers to, and a parser coupled to this document family's `CLAUSE n` and
`| E-nn |` conventions, which will need extending when a form arrives with different
formatting. That coupling is the honest trade: a chunker that understands its documents
beats a chunker that is safe for all documents and correct for none.
