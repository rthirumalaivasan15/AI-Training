# error_before_after.md - the same failing call, old docstring/error vs new

**Tool:** `search_policy` on our own server (`policy_server.py`, server one).
**Claim:** CLM-2024-10004 - sewer backup, decided by the HO-0820 Clause 2 grant and its 10,000 per-event cap. Expected: COVERED, 9,000.
**The failing call, identical in both runs:** `search_policy(query="sewer or drain backup: exclusion, coverage grant and per-event limit", form_numbers=["HO-0304", "HO 08 20"])` - the sewer endorsement written the way ISO prints form numbers, not the way our library keys them.

How it was made the same call: `error_demo.py` lets the model run, and the first time it calls `search_policy` that one call is swapped for the pinned one. Every other turn in both runs is the model (`openai/gpt-oss-120b` on Groq, temperature 0). Before = commit `22a81d8`; after = commit `29d0bd4`, where the only change is `policy_server.py`.

## What changed

| | before | after |
|---|---|---|
| docstring | one sentence: what the tool searches, what it returns | a prompt: when to call it, one call per fact, what each argument looks like (`HO-0820`, copy from `forms_attached`), what comes back, what to cite, what the error means and what to do about it |
| `'HO 08 20'` in `form_numbers` | `'HO 08 20'.split()[0]` = `'HO'`, matches no form, **dropped silently** - the call still returns HO-0304 passages and looks like a normal result | **refused, nothing searched**: `form 'HO 08 20' is not in the endorsement library ... Form numbers look like HO-0820 ... Did you mean HO-0820? Forms held: DP-0703, HO-0304, HO-0415, HO-0509, HO-0612, HO-0820. Call search_policy again with corrected form_numbers, or omit form_numbers` |

## Same failing call, side by side

| | before | after |
|---|---|---|
| what the failing call returned | 4 passages, all HO-0304; no sign HO-0820 was dropped | error naming `'HO 08 20'`, nearest match `HO-0820`, the six forms held |
| model's next call | `search_policy(["HO-0820"], "sewer backup coverage HO-0820")` - re-searched by inference from the claim record; nothing told it why HO-0820 was missing | `search_policy(["HO-0304", "HO-0820"], "sewer backup")` - the exact correction the error asked for, other form kept |
| laps from the failing call to a valid HO-0820 search | 1 | 1 |
| outcome | **PASS** - COVERED 9,000 | **FAIL** - COVERED 13,200 |
| laps / tokens / cost / active time | 6 / 10,571 / $0.00235 / 7.9 s | 8 / 16,878 / $0.00342 / 12.9 s |

**Reading it.** The error path is fixed: after the rewrite the model is told what was wrong and repairs the call in place, instead of having to notice an absence. Before, it only recovered because the claim record happened to list HO-0820 and the model noticed no HO-0820 passage came back. With a single bad form the old code returns an empty list, which reads as "the wording says nothing".

**The outcome went the other way, for a reason outside the error path.** The corrected query `"sewer backup"` across two forms did not return `HO-0820_05-24#03`, the Clause 2 grant that states the 10,000 cap, and neither did the follow-up `"limit"` search. The Week 8 argument check refused the Coverage A limit (310,000), but it accepts an omitted limit, so the model paid 14,200 - 1,000 = 13,200. That is the Week 8 top mode (M3, limit not grounded in the wording) reached by a different door: the check tests a stated limit, never a missing one. One run each, so PASS -> FAIL is one observation, not a rate.

**Docstring-as-prompt, seen in the model's own call.** The search the model wrote itself (before the swap) was `["HO-0820"]` under the old docstring and `["HO-0820 ed. 05-24"]` under the new one - copied from `forms_attached`, as the new docstring tells it to. Both are valid; neither run would have hit this error unpinned.

## The code change

```diff
diff --git a/Week-9/policy_server.py b/Week-9/policy_server.py
index 5f911bd..4c978ed 100644
--- a/Week-9/policy_server.py
+++ b/Week-9/policy_server.py
@@ -13,7 +13,9 @@ from typing import Annotated, Literal, Optional
 
 from pydantic import Field
 from mcp.server.mcpserver import MCPServer
+from mcp.server.mcpserver.exceptions import ToolError
 
+from index import load_chunks
 from search import dense_search
 
 mcp = MCPServer("policy-docs", log_level="WARNING")
@@ -29,16 +31,46 @@ def _numbers_seen():
             for n in re.findall(r"\d[\d,]*", text)}
 
 
+FORMS = sorted({row["form_number"] for row in load_chunks()})
+
+
+def _form(raw):
+    """'HO-0304' or 'HO-0304 ed. 03-24' -> 'HO-0304'. Anything else is refused, with
+    the nearest form the library holds, so the model can correct it and call again.
+    (Week 9 fix: this used to be raw.split()[0], which turned 'HO 08 20' into 'HO',
+    matched nothing, and silently dropped that form from the search.)"""
+    head = re.sub(r"\s+ed\.?\s*[\d-]+$", "", raw.strip())
+    if head in FORMS:
+        return head
+    guess = "%s-%s" % (re.sub(r"[^A-Z]", "", head.upper()), re.sub(r"\D", "", head))
+    raise ToolError(
+        "form %r is not in the endorsement library, so nothing was searched. Form numbers look "
+        "like HO-0820: two letters, a hyphen, four digits (an edition suffix such as ' ed. 05-24' "
+        "is accepted).%s Forms held: %s. Call search_policy again with corrected form_numbers, "
+        "or omit form_numbers to search every form."
+        % (raw, " Did you mean %s?" % guess if guess in FORMS else "", ", ".join(FORMS)))
+
+
 @mcp.tool()
 def search_policy(
-    query: Annotated[str, Field(description="What to look for in the wording, e.g. 'sewer backup deductible'.")],
+    query: Annotated[str, Field(description="Plain words for the one fact you need, e.g. 'sewer backup per-event limit'.")],
     form_numbers: Annotated[Optional[list[str]], Field(
-        description="Form numbers to restrict to, e.g. ['HO-0820']. Omit to search all forms.")] = None,
+        description="The claim's endorsements as HO-0820 (two letters, hyphen, four digits), copied "
+                    "from forms_attached. Omit to search every form.")] = None,
 ) -> dict:
-    """Search the endorsement wording - definitions, exclusions table rows, exceptions, limits and duty clauses - with a free-text query, optionally restricted to specific form numbers. Returns wording passages with chunk ids only - it never returns claim facts."""
+    """Search the endorsement wording and return the passages a coverage decision rests on.
+
+    Call this whenever the decision depends on wording: a definition, an exclusions table row (codes like E-16), the exception in that row, a limit or sublimit, a deductible, or a duty such as maintenance or notice. One call per fact; a second, narrower query is normal when the first does not show the clause you need.
+
+    query: plain words for the fact, e.g. 'sewer backup per-event limit' or 'vacant more than 60 days'.
+    form_numbers: the endorsements attached to the claim, written HO-0820 - two letters, a hyphen, four digits. Copy them from the claim's forms_attached; 'HO-0820 ed. 05-24' is accepted. Omit to search every form.
+
+    Returns {"passages": [{chunk_id, form_number, text}]}, up to 4, best match first. Cite the chunk_id of every passage you rely on. Never returns claim facts - those come from the claims system.
+
+    If a form number is not in the library, nothing is searched and the error names the bad form, the closest form held and the full list: correct form_numbers and call again. Do not read that error as the wording being silent."""
     where = None
     if form_numbers:
-        forms = [f.split()[0] for f in form_numbers]   # "HO-0304 ed. 03-24" -> "HO-0304"
+        forms = [_form(f) for f in form_numbers]
         where = {"form_number": forms[0]} if len(forms) == 1 else {"form_number": {"$in": forms}}
     hits = dense_search(query, k=4, where=where)
     _evidence.extend(h["text"] for h in hits)
```

## Transcript - before (old docstring, silent drop) - runs/error_before.json

**Model's own first search, swapped for the pinned call:** `[{"form_numbers": ["HO-0820"], "query": "sewer backup"}]`

- lap 1 model -> `get_claim_status({"claim_number": "CLM-2024-10004"})`
  - tool returned `{"claim_id": "CLM-2024-10004", "status": "open", "policy_number": "HP-449215", "policy_line": "homeowners", "forms_attached": ["HO-0304 ed. 03-24", "HO-0820 ed.`
- lap 2 model -> `get_adjuster_notes({"claim_number": "CLM-2024-10004"})`
  - tool returned `{"claim_id": "CLM-2024-10004", "adjuster_notes": ["2024-06-12 Heavy rain overnight. Insured found dark water around the basement floor drain in the morning.", "`
- lap 3 model -> `search_policy({"query": "sewer or drain backup: exclusion, coverage grant and per-event limit", "form_numbers": ["HO-0304", "HO 08 20"]})`  **<- the pinned failing call**
  - tool returned 4 passages: `HO-0304_03-24#05` (| Code | Exclusion Description | Applies To | Ex), `HO-0304_03-24#06` (CLAUSE 4. DUTIES AFTER A WATER LOSS), `HO-0304_03-24#04` (CLAUSE 3. EXCLUSIONS TABLE), `HO-0304_03-24#00` (FORM NUMBER: HO-0304)
- lap 4 model -> `search_policy({"form_numbers": ["HO-0820"], "query": "sewer backup coverage HO-0820"})`
  - tool returned 4 passages: `HO-0820_05-24#00` (FORM NUMBER: HO-0820), `HO-0820_05-24#03` (CLAUSE 2. COVERAGE GRANT), `HO-0820_05-24#02` (CLAUSE 1. DEFINITIONS), `HO-0820_05-24#05` (| Code | Exclusion Description | Applies To | Ex)
- lap 5 model -> `compute_payout({"claim_status": "covered", "excess": 1000, "limit": 10000, "loss_amount": 14200})`
  - tool returned `{"payable_amount": 9000}`
- lap 6 model -> final answer:

```json
{
  "claim_id": "CLM-2024-10004",
  "coverage_position": "COVERED",
  "grounds": [
    "E-16",
    "HO-0820 Clause 2"
  ],
  "payable_amount": 9000,
  "reasoning": "The adjuster notes describe water backing up through the basement floor drain due to a municipal sewer surcharge, which triggers exclusion E-16 (water backs up through sewers or drains) [HO-0304_03-24#05]. The policy includes endorsement HO-0820, and its Clause 2 provides coverage for water backup up to $10,000 per loss, overriding E-16 [HO-0820_05-24#03]. The loss amount of $14,200 exceeds the endorsement limit, so the payable amount is limited to $10,000 minus the $1,000 deductible, resulting in $9,000 [computed payout].",
  "next_step": "Confirm the loss documentation and issue a payment of $9,000 to the insured."
}
```

Outcome **PASS** - 6 laps, 10571 tokens, $0.00235, 7.9 s active.

## Transcript - after (docstring as prompt, recoverable error) - runs/error_after.json

**Model's own first search, swapped for the pinned call:** `[{"form_numbers": ["HO-0820 ed. 05-24"], "query": "sewer backup"}]`

- lap 1 model -> `get_claim_status({"claim_number": "CLM-2024-10004"})`
  - tool returned `{"claim_id": "CLM-2024-10004", "status": "open", "policy_number": "HP-449215", "policy_line": "homeowners", "forms_attached": ["HO-0304 ed. 03-24", "HO-0820 ed.`
- lap 2 model -> `get_adjuster_notes({"claim_number": "CLM-2024-10004"})`
  - tool returned `{"claim_id": "CLM-2024-10004", "adjuster_notes": ["2024-06-12 Heavy rain overnight. Insured found dark water around the basement floor drain in the morning.", "`
- lap 3 model -> `search_policy({"query": "sewer or drain backup: exclusion, coverage grant and per-event limit", "form_numbers": ["HO-0304", "HO 08 20"]})`  **<- the pinned failing call**
  - tool returned **error**: `Error executing tool search_policy: form 'HO 08 20' is not in the endorsement library, so nothing was searched. Form numbers look like HO-0820: two letters, a hyphen, four digits (an edition suffix such as ' ed. 05-24' is accepted). Did you mean HO-0820? Forms held: DP-0703, HO-0304, HO-0415, HO-0509, HO-0612, HO-0820. Call search_policy again with corrected form_numbers, or omit form_numbers to search every form.`
- lap 4 model -> `search_policy({"form_numbers": ["HO-0304", "HO-0820"], "query": "sewer backup"})`
  - tool returned 4 passages: `HO-0820_05-24#02` (CLAUSE 1. DEFINITIONS), `HO-0304_03-24#06` (CLAUSE 4. DUTIES AFTER A WATER LOSS), `HO-0820_05-24#05` (| Code | Exclusion Description | Applies To | Ex), `HO-0304_03-24#05` (| Code | Exclusion Description | Applies To | Ex)
- lap 5 model -> `compute_payout({"claim_status": "covered", "excess": 1000, "limit": 310000, "loss_amount": 14200})`
  - tool returned **error**: `limit 310000 is not stated in any passage you have retrieved. Search the wording for the clause that states the per-event limit or sublimit and call again with that figure, or omit limit if the wording states none. A Coverage A limit from the claim record is not a per-event limit.`
- lap 6 model -> `search_policy({"form_numbers": ["HO-0820"], "query": "limit"})`
  - tool returned 4 passages: `HO-0820_05-24#04` (CLAUSE 3. EXCLUSIONS TABLE), `HO-0820_05-24#05` (| Code | Exclusion Description | Applies To | Ex), `HO-0820_05-24#07` (CLAUSE 5. OTHER TERMS), `HO-0820_05-24#06` (CLAUSE 4. MAINTENANCE DUTY)
- lap 7 model -> `compute_payout({"claim_status": "covered", "excess": 1000, "limit": null, "loss_amount": 14200})`
  - tool returned `{"payable_amount": 13200}`
- lap 8 model -> final answer:

```json
{
  "claim_id": "CLM-2024-10004",
  "coverage_position": "COVERED",
  "grounds": [
    "E-16 (coverage for water backup through sewers or drains requires HO-0820 endorsement)",
    "HO-0820 Clause 1 (definition of water backup)",
    "HO-0304 Clause 4 (duties after a water loss – no breach identified)"
  ],
  "payable_amount": 13200,
  "reasoning": "The adjuster notes describe water entering the basement via the floor drain after a municipal sewer surcharge, which matches the definition of \"water backup\" in HO-0820 Clause 1 [HO-0820_05-24#02]. Exclusion E-16 permits coverage for such backup only when the HO-0820 endorsement is attached, and it is attached to this policy [HO-0304_03-24#05]. No other exclusions (e.g., E-51 pump failure or E-52 vacancy) apply, and the insured has not breached the post‑loss duties in HO-0304 Clause 4, so coverage is affirmed.",
  "next_step": "Proceed with payment of the approved amount and issue the claim settlement to the insured."
}
```

Outcome **FAIL** (payable 13200, expected 9000) - 8 laps, 16878 tokens, $0.00342, 12.9 s active.
