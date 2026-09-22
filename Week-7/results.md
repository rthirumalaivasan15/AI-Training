# Week 7 — Task Set D — Insurance claims

Race the claims agent against a fixed workflow.

**Pass rate tied at 8/10. The workflow is ahead on the other three numbers, and
the agent never once used the freedom that makes it an agent: it did not search
a second time on any claim.** Ship the workflow.

Model `openai/gpt-oss-120b` on Groq, temperature 0, for both systems. Same three
tools, same output contract (`contract.py`), same grader, same 10 claims.

---

## 1. The race — 8 numbers, same 10 claims

| system | pass rate | p50 latency | total tokens (10 claims) | cost per claim |
|---|---|---|---|---|
| fixed workflow | **8/10** | **3.09 s** | **23,319** | **$0.000753** |
| agent | **8/10** | 4.74 s | 54,785 | $0.001209 |

Source: [race.csv](race.csv), per claim in [race_claims.csv](race_claims.csv), every
lap and step in `runs/race_*.jsonl`.

- **Tokens are summed over every lap.** The agent re-sends the whole message list
  each lap, so its per-claim tokens grow 853 → ~1,150 → ~1,900 → ~2,100 across four
  laps. The last call alone would have reported about a third of the real total.
- **Latency is active time.** Groq's free-tier rate limit made both systems wait
  between calls. That backoff is recorded per claim (`rate_limit_wait_s`) and
  left out of latency and the wall-clock budget, because it measures the quota,
  not either system.
- **2 of the agent's 37 laps have estimated usage.** On CLM-2024-10007 and
  CLM-2024-10009 the model sent its final answer as a call to an undeclared tool
  `json`. Groq refuses such a call and reports no usage for it, so those two laps
  are counted at 4 characters per token (`llm.py`) instead of as free. Section 5.
- Cost uses Groq's list price of $0.15 / $0.60 per 1M input / output tokens,
  set in one place in `llm.py`.

### The claim mix

Written with expected outcomes and committed (`327f1e3`) before either system ran.

| class | claims | what makes it hard |
|---|---|---|
| notes trigger an exclusion lookup | 10002, 10003, 10004, 10005, 10006, 10009 | first notice points one way, a note changes which clause decides it: seepage duration, flood not backup, sewer backup + HO-0820 cap, power outage exception, vacancy + late inspection, business use sublimit |
| clean | 10001, 10007 | the first notice is enough |
| missing notes | 10008, 10010 | no notes, or notes that cannot establish the fact the exclusion turns on |

### Per claim

| claim | class | expected | workflow | agent |
|---|---|---|---|---|
| 10001 | clean | COVERED 7,400 | PASS | PASS |
| 10002 | notes trigger | DENIED E-18 | PASS | PASS |
| 10003 | notes trigger | DENIED E-15 | PASS | PASS |
| 10004 | notes trigger | COVERED 9,000 | PASS | **FAIL** — paid 13,200 |
| 10005 | notes trigger | COVERED 5,300 | **FAIL** — UNDETERMINED | PASS |
| 10006 | notes trigger | DENIED E-61 | PASS | PASS |
| 10007 | clean | DENIED E-22 | PASS | PASS |
| 10008 | missing notes | UNDETERMINED | PASS | PASS |
| 10009 | notes trigger | COVERED 2,000 | PASS | PASS |
| 10010 | missing notes | UNDETERMINED | **FAIL** — DENIED | **FAIL** — DENIED |

---

## 2. Why each failure happened

**Agent, CLM-2024-10004 — paid 13,200, should be 9,000.** Its only search was the
two words `sewer backup`, which returned the HO-0820 definition but not Clause 2,
the 10,000 per-event cap. It did not search again. It passed the 310,000
Coverage A limit to `compute_payout` as the cap. The workflow's query, written
from the notes (`"HO-0820" "sewer backup" ... municipal sewer surcharge coverage`),
returned Clause 2 on the first try. This is the one claim where searching again
would have paid off, and the agent had the freedom to do it and did not.

**Workflow, CLM-2024-10005 — UNDETERMINED, should be COVERED.** It found the E-51
power-outage exception and applied it correctly, then held the claim open
because the notes do not show the 90-day pump test in HO-0820 Clause 4. Clause 4
states a duty with no consequence attached. This is Week 5's failure mode 2,
attaching a consequence to a clause that states none, showing up again in a new
app.

**Both, CLM-2024-10010 — DENIED, should be UNDETERMINED.** The notes say the insured
does not know when the leak started. Both systems reasoned "sudden and accidental
is not established, so the E-17 exception does not apply, so deny." Both were
told the opposite in their prompts: when the notes cannot establish the fact an
exclusion turns on, the position is UNDETERMINED. A denial here would rest on a
fact nobody knows. The expected answer is arguable on burden of proof, but it
counts the same against both systems, so it cannot change the verdict.

---

## 3. Does the path vary by input? The agent's own tool trace

| claim | class | agent tool path |
|---|---|---|
| 10001 | clean | get_claim → search_policy → compute_payout |
| 10002 | notes trigger | get_claim → search_policy → compute_payout |
| 10003 | notes trigger | get_claim → search_policy |
| 10004 | notes trigger | get_claim → search_policy → compute_payout |
| 10005 | notes trigger | get_claim → search_policy → compute_payout |
| 10006 | notes trigger | get_claim → search_policy → compute_payout |
| 10007 | clean | get_claim → search_policy → compute_payout |
| 10008 | missing notes | get_claim |
| 10009 | notes trigger | get_claim → search_policy → compute_payout |
| 10010 | missing notes | get_claim → search_policy → compute_payout |

Eight of ten are the same three calls in the same order. The two that differ
only **drop** a step (a denial with no payout call; no notes, so nothing to
search). Not one claim took a path the workflow does not already take. On the six
claims where step 3 depends on step 2, the dependency is **data, not path**: the
notes change what is searched for, never whether a search happens or what comes
after it. The workflow handles that by having step 2 write the search query.

---

## 4. Verdict

Decision rule: does the path vary by input? On these 10 claims it does not. The
agent ran get_claim → one search_policy → compute_payout on eight claims and never
searched a second time, not even on the six notes-trigger-exclusion claims where
step 3 depends on step 2. That dependency is data, not path, and the workflow
covers it by writing the search query from the notes. Each system passed 5 of
those 6. With pass rate tied at 8/10, the workflow wins the other three numbers:
3.09 s vs 4.74 s p50, 23,319 vs 54,785 tokens, $0.00075 vs $0.00121 per claim.
None of the 10 claims forces an agent. The class that would is a claim whose
notes need a second endorsement lookup that the first search misses, like
CLM-2024-10004. The agent could have searched again there, and did not.

*(138 words)*

---

## 5. What the loop broke that the workflow cannot

The first race run crashed the agent on its first claim ([runs/agent_first_race_crash.txt](runs/agent_first_race_crash.txt),
commit `961ea29`). gpt-oss-120b sent a correct final answer as a call to a tool
named `json` that was never declared. Groq refused the whole call with a 400, and
the loop had no path for a refused call. The workflow cannot hit this because it
never sends tools to the model. Fixed in `b478fb8`: a refused call whose arguments
pass `contract.validate` is accepted as the answer; any other refused call gets a
"that tool does not exist" message and spends a lap. It happened again on 2 of 10
claims in the finished race, and both were accepted this way.

---

## 6. Budgets — all four enforced, one clean termination

`agent.py`, class `Budget`, checked **before every lap**:

| budget | default | also pushed into the call |
|---|---|---|
| `max_iters` | 8 laps | — |
| `max_tokens` | 60,000, summed over laps | `max_completion_tokens` = what is left, at most 4,096; a lap with under 512 left is not started |
| `max_cost` | $0.02, summed over laps | — |
| `max_wall` | 90 s active | request `timeout` = seconds left |

When one fires the loop stops, logs which budget fired and by how much, and
returns a valid UNDETERMINED answer referring the claim to an adjuster.
`python selftest.py` drives each budget against a stub model that asks for a tool
on every lap and never answers. Each of the four is the one that stops it (25
checks, no API calls).

**The live termination** — [runs/budget_termination.log](runs/budget_termination.log),
`python agent.py CLM-2024-10006 --max-tokens 3000 --log runs/budget_termination.log`:

```
09:46:48  START CLM-2024-10006  limits {"max_iters": 8, "max_tokens": 3000, "max_cost": 0.02, "max_wall": 90}
09:46:49  lap 1  +853 tok (810 in / 43 out)  total 853 tok  $0.00015  0.7s  finish=tool_calls
09:46:49        -> get_claim({"claim_id": "CLM-2024-10006"})
09:46:49  lap 2  +1198 tok (1104 in / 94 out)  total 2051 tok  $0.00037  1.3s  finish=tool_calls
09:46:50        -> search_policy({"form_numbers": ["DP-0703"], "query": "burst pipe"})
09:46:51  lap 3  +2087 tok (1561 in / 526 out)  total 4138 tok  $0.00092  3.1s  finish=tool_calls
09:46:51        -> compute_payout({"claim_status": "denied", "excess": 1500, "loss_amount": 17600})
09:46:51  STOP  budget=max_tokens fired  used=4138  limit=3000
09:46:51        used {"max_iters": 3, "max_tokens": 4138, "max_cost": 0.000919, "max_wall": 3.12}
09:46:51  OUTPUT {"claim_id": "CLM-2024-10006", "coverage_position": "UNDETERMINED", "grounds": [], "payable_amount": null, ...}
```

**It overshot: 4,138 against 3,000.** Lap 3 started with 949 tokens left, and its
completion was capped at 949 (it used 526). The 1,561 prompt tokens cannot be
capped, because the loop has to re-send the history. So the token budget holds to
within one lap, not exactly. Starting lap 3 at all would need an estimate of the
prompt size before sending it, which the loop does not make. The limit on 3,000
is lowered only for this demonstration; the race ran on the defaults, and no
race claim came near any budget (most laps: 4, most tokens: 6,540).

---

## 7. The third tool

`compute_payout`, added in `b7c91f1`. `git diff b6e8e89 b7c91f1 -- Week-7/tools.py`:

```diff
+CLAIM_STATUSES = ("covered", "denied", "undetermined")
+
+def compute_payout(claim_status, loss_amount, excess, limit=None):
+    if claim_status not in CLAIM_STATUSES:
+        return {"error": "claim_status must be one of %s" % ", ".join(CLAIM_STATUSES)}
+    if claim_status == "denied":
+        return {"payable_amount": 0}
+    if claim_status == "undetermined":
+        return {"payable_amount": None}
+    capped = min(loss_amount, limit) if limit is not None else loss_amount
+    return {"payable_amount": max(0, round(capped - excess))}
...
+    {
+        "type": "function",
+        "function": {
+            "name": "compute_payout",
+            "description": (
+                "Compute the payable amount for a coverage decision already made: "
+                "min(loss_amount, limit) minus the excess, never below zero; 0 when denied, "
+                "null when undetermined. Arithmetic only - it never reads the claim or the "
+                "wording, so pass in the figures you have already found."
+            ),
+            "parameters": {
+                "type": "object",
+                "properties": {
+                    "claim_status": {"type": "string", "enum": list(CLAIM_STATUSES), ...},
+                    "loss_amount": {"type": "integer", "minimum": 0, ...},
+                    "excess": {"type": "integer", "minimum": 0, ...},
+                    "limit": {"type": "integer", "minimum": 0, ...},
+                },
+                "required": ["claim_status", "loss_amount", "excess"],
+                "additionalProperties": False,
+            },
+        },
+    },
 ]
-IMPLS = {"get_claim": get_claim, "search_policy": search_policy}
+IMPLS = {"get_claim": get_claim, "search_policy": search_policy, "compute_payout": compute_payout}
```

- **One job.** Arithmetic on figures it is given. It reads nothing.
- **Enum.** `claim_status` accepts only `covered | denied | undetermined`. The
  schema says so, and the function refuses anything else (selftest checks both).
- **No overlap.** `get_claim` returns claim facts and "never returns endorsement
  wording". `search_policy` returns wording and "never returns claim facts".
  `compute_payout` "never reads the claim or the wording". Each description says
  what the tool does not do, so no two tools compete for the same call. In the
  race the agent never called a tool for the wrong job: every `get_claim` came
  first, and every `compute_payout` came after the search.

The 10004 failure is the one place the tool boundary showed a gap. The model
passed the Coverage A limit as `limit`, because the per-event cap was never
retrieved. `compute_payout` did exactly what its description says. The wrong
figure came from a search that was not repeated.

---

## 8. Not done

The bonus (sliding window plus summarisation for a 30-turn claim, and the excess
persisted across a restart) was not attempted.
