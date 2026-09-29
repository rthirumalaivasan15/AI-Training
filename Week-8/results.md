# Week 8 — Task Set D — Insurance claims

Find the outcome-vs-trajectory gap in the claims agent, then close one mode.

**Outcome pass 80%. Trajectory pass 40%. The gap is 40 points** — four of the ten
claims reach the right answer down a path that would not survive an audit,
including one that never opens the exclusions at all.

One mitigation (argument validation on `compute_payout`) took the top mode from
**5 → 2**, the gap from **40 → 30 points**, and cost **+1,468 tokens, +$0.000215
and +1.05 s per claim**. It also created a new mode: **M5 rose 0 → 1**.

Same app as Week 7: `openai/gpt-oss-120b` on Groq, three tools, ten claims,
outcome graded by `contract.grade` against `expected.json`.

---

## 1. The accepted paths — asserted as sets, not single sequences

`trajectory_eval.py` enumerates the accepted tool sequences per case from three
rules, rather than pinning one sequence per claim:

1. `get_claim` runs first and once.
2. `search_policy` runs **1 to 3 times**. One search or three is a judgement
   call, not an error; what matters is whether the wording that decides the claim
   was opened (section 2).
3. `compute_payout` is **required only when the answer states a payable above
   zero**. On a denial (0) or UNDETERMINED (null) there is no arithmetic to do,
   and calling the tool to be told "0" is not a better path than not calling it.
   A **second** payout call is accepted when the first was refused — going back to
   the wording and retrying is the correction the refusal asks for.

| case | payout call | accepted sequences | why more than one path is right |
|---|---|---|---|
| 10001, 10004, 10005, 10009 | required (positive payable) | 3 (1–3 searches) + retry variants | the number of searches is the agent's call |
| 10002, 10003, 10006, 10007 | optional (DENIED, payable 0) | 6 (1–3 searches, with or without the payout call) | a denial needs no arithmetic |
| 10008, 10010 | optional (UNDETERMINED, null) | 6 | same |

`steps_needed` for the efficiency ratio is the shortest accepted sequence, which
is why a denial that also calls `compute_payout` scores 1.50 rather than 1.00. It
is not wrong, it is one step more than the case needs.

---

## 2. The decisive-wording check

A sequence can be correct while the run still decides the claim on wording it
never read. Every case therefore names the passages it turns on (`DECISIVE` in
`trajectory_eval.py`), and the run is checked against what `search_policy`
actually returned.

| claim | decisive passages | why |
|---|---|---|
| 10001 | `HO-0304#05`, `#02` | E-17 row, plus the 14-day definition its exception turns on |
| 10004 | `HO-0304#05`, `HO-0820#03` | E-16 row, plus the Clause 2 grant that overrides it and caps it at 10,000 |
| 10006 | `DP-0703#05`, `#06` | E-61 row with its exception, plus the Clause 4 duty that voids that exception |
| 10008 | `HO-0304#05` | UNDETERMINED is only a finding once the exclusions have been opened and none can be applied |

(Full table for all ten in the code.)

---

## 3. The four trajectory numbers

| number | before | after mitigation |
|---|---|---|
| tool-choice accuracy (sequence in the accepted set) | **90%** | **90%** |
| argument validity rate (arguments that landed) | **92.8%** | **97.3%** |
| step efficiency, p50 (steps taken / steps needed) | **1.00** | **1.50** |
| cost per claim — **p50** | **$0.00130** | **$0.00152** |
| cost per claim — **max** | **$0.00170** | **$0.00221** |
| *(context)* outcome pass | 80% | 80% |
| *(context)* trajectory pass | 40% | 50% |
| *(context)* tokens, 10 claims | 55,332 | 70,017 |
| *(context)* latency p50 | 5.35 s | 6.40 s |

Cost is reported p50 **and** max because the mean hides the claim that goes back
for a second look: the max claim costs **1.31×** the median before the mitigation
and **1.46×** after it. Per claim in `trajectory_before.csv` / `trajectory_after.csv`,
summary in `trajectory_summary.csv`.

**Argument validity** checks every argument that reached a tool: claim ids that
exist, form numbers that exist *and are attached to this policy*, `loss_amount`
within the claimed amount, an `excess` that is either the policy excess or a
figure stated in a passage the run opened, a `limit` stated in a passage the run
opened, and every chunk id and `E-NN` code cited in the answer. 0 fabricated
references in either run: the agent's ids are real. What it invents is not
identifiers but **authority** — see the top mode.

---

## 4. The gap: 80% − 40% = **40 points**

Four claims pass the outcome eval on a path that fails:

| claim | outcome | trajectory | what the path did wrong |
|---|---|---|---|
| **10008** | PASS | FAIL | **never opened the exclusions at all** |
| 10001 | PASS | FAIL | payout capped with a limit no passage states |
| 10005 | PASS | FAIL | never opened HO-0820 Clause 2; the limit was never verified |
| 10006 | PASS | FAIL | payout computed with the Coverage A limit as a per-event cap |

### The named right-answer-wrong-path case: CLM-2024-10008

```
lap 1  +853 tok   -> get_claim({"claim_id": "CLM-2024-10008"})
lap 2  +1214 tok  final answer
DONE
```

The whole trajectory is **one tool call**. Tool path: `get_claim`. No
`search_policy`, so not one word of the endorsements was read.

Its answer is graded **PASS** by the outcome eval, and it is word-for-word
defensible:

> `coverage_position: UNDETERMINED`, `payable_amount: null` — *"The adjuster notes
> are empty, providing no facts about cause, duration, vacancy, or business use
> that could trigger any endorsement exclusion, exception, limit, or duty."*

It is right for the wrong reason. The claim has no notes, so the agent concluded
nothing could be decided **without checking what the endorsements require**. The
policy carries HO-0304, whose E-15 to E-18 rows and Clause 4 duties are what
make a kitchen water loss undecidable. The agent asserted that from the empty
notes alone. On the very next claim where the notes are thin but an exclusion
applies absolutely, the same path returns the same UNDETERMINED and the outcome
eval scores it as a pass.

Step efficiency 0.50 — this is the one case that under-steps, and the efficiency
ratio catches it from the other side.

---

## 5. The mitigation: argument validation, one change

**Top mode before: `M3_ungrounded_limit`, 5 of 10 claims.** The agent passed a
`limit` to `compute_payout` that no passage it opened ever states — almost always
the Coverage A limit off the claim record (350,000 / 310,000 / 295,000 / 240,000)
standing in for a per-event cap. On 10004 that is the mechanism of the outcome
failure: the real cap is HO-0820's 10,000, so it paid **13,200 instead of 9,000**.

Chosen from the zoo: **argument validation**. Not a tighter description (the
description is already explicit), not a step limit (no run over-steps), not
replacing the agent with the workflow (that was Week 7's verdict and would test
nothing here).

```diff
+_evidence = None            # the wording this run has actually opened
+
+def begin_run():
+    global _evidence
+    _evidence = []
 def search_policy(query, form_numbers=None, k=4):
     hits = dense_search(query, k=k, where=where)
+    if _evidence is not None:
+        _evidence.extend(h["text"] for h in hits)

 def compute_payout(claim_status, loss_amount, excess, limit=None):
+    if limit is not None and _evidence is not None and limit not in _numbers_seen():
+        return {"error": "limit %s is not stated in any passage you have retrieved. Search the "
+                         "wording for the clause that states the per-event limit or sublimit and "
+                         "call again with that figure, or omit limit if the wording states none. "
+                         "A Coverage A limit from the claim record is not a per-event limit." % limit}
```

Validation is inert unless `begin_run()` turns it on, so `workflow.py` is
untouched and `WEEK8_VALIDATE_ARGS=0` reproduces the pre-mitigation agent.

### Before → after, with the price

| | before | after |
|---|---|---|
| **M3_ungrounded_limit (landed)** | **5** | **2** |
| M3 attempts (including refused) | 5 | 5 |
| trajectory pass | 40% | 50% |
| gap | 40 points | 30 points |
| **price: tokens per claim** | 5,533 | **7,002 (+1,468)** |
| **price: cost per claim (p50)** | $0.00130 | **$0.00152 (+$0.000215)** |
| **price: latency p50** | 5.35 s | **6.40 s (+1.05 s)** |

**The mitigation is not free and it is not a cure.** Three things the numbers say
that a "mode went down" headline would hide:

1. **Attempts did not move: 5 → 5.** The model still reaches for the Coverage A
   limit every time. The tool refuses it; the behaviour is unchanged. What the
   mitigation buys is that the bad argument no longer reaches the claim.
2. **Two ungrounded limits still land (10002, 10006).** Both are denials, and
   `compute_payout` returns 0 for `denied` *before* it validates the limit. The
   validation only guards the covered path. That is a real hole, it is one line to
   close, and it is left open here because the task allows exactly one mitigation
   and moving it now would confuse the measurement.
3. **10004's outcome is still wrong.** The refusal worked, the agent searched
   again — with the one-word query `"limit"` — retrieved the Clause 3 *header*
   instead of the Clause 2 grant, then dropped `limit` entirely and paid 13,200.
   Blocking a wrong argument does not supply the right one.

---

## 6. Regression check — every mode, before → after

| mode | before | after | verdict |
|---|---|---|---|
| M1_exclusions_never_opened | 1 | 1 | same |
| M2_decisive_clause_missed | 2 | 2 | same |
| **M3_ungrounded_limit** | **5** | **2** | **better — the target** |
| M4_fabricated_reference | 0 | 0 | same |
| **M5_payout_skipped** | **0** | **1** | **WORSE — created by the mitigation** |
| M6_step_inefficiency | 0 | 0 | same |

**M5 is new, and the mitigation caused it.** On CLM-2024-10005 the payout call was
refused for an ungrounded limit (295,000). The agent searched again, then wrote
`payable_amount: 5300` in its answer **without any accepted payout call** — it did
the arithmetic itself. The outcome is correct (6,300 − 1,000), which is exactly
why only the trajectory eval catches it. Refusing a tool call teaches some runs to
route around the tool.

A refused call is not a payout, so the detector counts accepted calls only. That
was a bug in the first version of the eval, fixed in `79b19a8`; the same corrected
eval scores both runs, and re-scoring the before-run costs nothing because
`trajectory_eval.py` never calls the model.

Step efficiency p50 also worsened, 1.00 → 1.50, which is the same +1 step the
price table charges: retries are steps.

---

## 7. Not done

The bonus (indirect prompt injection planted in an adjuster note, then sanitising
tool output, scoping the payment tool read-only and adding an output guardrail)
was not attempted.
