# Generation transcripts

## Grounding prompt (forced refusal)
```
You are a claims assistant. Answer ONLY from the retrieved
chunks supplied below. Rules (non-negotiable):
1. Every claim must carry a citation [chunk_id | form_number | clause].
2. If the chunks do not contain the answer you MUST reply exactly:
   "I cannot answer this from the indexed endorsements."
   and name the source that would be needed.
   Do NOT use outside knowledge. Do NOT use best judgement.
```

Gate: answer only if term-overlap >= 2 AND top score >= 0.45. Otherwise refuse.

---

## Q1: Does exclusion E-17 apply to water damage from a burst supply line when the discharge was sudden and accidental?

Gate: overlap=10, top_score=0.639 -> ANSWER

**Response:**
> No. The E-17 exception says it does NOT apply where the discharge was sudden and accidental as defined in Clause 1(a), so the loss remains covered up to policy limits.
>
> Citation: [struct:HO-0304:005 | HO-0304 ed. 03-24 | CLAUSE 3. EXCLUSIONS TABLE row E-17]

**Cited chunk, verbatim:**
```
FORM HO-0304 ed. 03-24
CLAUSE 3. EXCLUSIONS TABLE
The following exclusions apply to Section I - Property Coverages:
| Code | Exclusion Description | Applies To | Exception |
| E-17 | Water damage from a burst or ruptured supply line | Coverage A - Dwelling | Does NOT apply where the discharge was sudden and accidental as defined in Clause 1(a); such losses remain covered up to policy limits. |
```

---

## Q5: After this endorsement is attached, what percentage of the Coverage A limit applies to Ordinance or Law?

Gate: overlap=3, top_score=0.782 -> ANSWER

**Response:**
> 25 percent of the Coverage A limit, increased from the 10 percent stated in the base wording.
>
> Citation: [struct:HO-0612:002 | HO-0612 ed. 03-24 | CLAUSE 2. INCREASED LIMIT]

**Cited chunk, verbatim:**
```
FORM HO-0612 ed. 03-24
CLAUSE 2. INCREASED LIMIT
The Ordinance or Law coverage percentage stated in the base wording is increased from 10 percent to 25 percent of the Coverage A limit of liability shown in the Declarations. This increase applies only to losses occurring on or after the effective date shown above.
```

---

## Q7: A pipe burst in my rental house while it sat empty between tenants for 45 days. Is the damage covered?

Gate: overlap=5, top_score=0.548 -> ANSWER

**Response:**
> Excluded by E-61 because the dwelling was unoccupied more than 30 consecutive days, UNLESS the water supply was shut off at the main and the plumbing system drained during that period.
>
> Citation: [struct:DP-0703:003 | DP-0703 ed. 02-24 | CLAUSE 3. EXCLUSIONS TABLE row E-61]

**Cited chunk, verbatim:**
```
FORM DP-0703 ed. 02-24
CLAUSE 3. EXCLUSIONS TABLE
The following exclusions apply to Coverage A - Dwelling:
| Code | Exclusion Description | Applies To | Exception |
| E-61 | Water damage from a burst supply line occurring while the dwelling is unoccupied between tenancies for more than 30 consecutive days | Coverage A - Dwelling | Does NOT apply if the water supply was shut off at the main and the plumbing system drained during the unoccupied period. |
```

---

## R1: What is the reserve-setting threshold for claim CLM-2024-88431?

Gate: overlap=0, top_score=0.440 -> REFUSE

**Response:**
> I cannot answer this from the indexed endorsements.
> The 6 indexed endorsements contain policy wording only —
> no claim records, rating manuals, or declarations pages.
> Answering would require a source that was never indexed.

Top retrieved chunk (rejected as unsupporting): `struct:HO-0612:002` score=0.440

---

## R2: What premium charge applies for attaching endorsement HO-0820 to a policy?

Gate: overlap=1, top_score=0.595 -> REFUSE

**Response:**
> I cannot answer this from the indexed endorsements.
> The 6 indexed endorsements contain policy wording only —
> no claim records, rating manuals, or declarations pages.
> Answering would require a source that was never indexed.

Top retrieved chunk (rejected as unsupporting): `struct:HO-0820:002` score=0.595

---

## R3: What is the all-perils deductible shown on the declarations page of policy HO-778812?

Gate: overlap=0, top_score=0.638 -> REFUSE

**Response:**
> I cannot answer this from the indexed endorsements.
> The 6 indexed endorsements contain policy wording only —
> no claim records, rating manuals, or declarations pages.
> Answering would require a source that was never indexed.

Top retrieved chunk (rejected as unsupporting): `struct:HO-0509:006` score=0.638