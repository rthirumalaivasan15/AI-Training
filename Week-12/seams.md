# Seam list — written Tuesday 2026-10-27, while wiring Weeks 3–11 together

Unedited. Each seam is where two parts that worked alone did not fit; the **status** column is the
only thing updated after Tuesday (fixed / accepted / ran-out-of-time), with the date it changed.

| # | seam | found by | status |
|---|---|---|---|
| 1 | The Week 9–11 `search_policy` drops the edition from `"HO-0304 ed. 03-24"` and has no date, so with two HO-0304 editions in the library a 2024 surface-water query returned **3 of 4 passages from the 2025 edition** (`HO-0304_01-25#02, #07, #05`). Nothing before Week 12 had two editions of one form, so nothing caught it. | self-test search, Tuesday | open |
| 2 | Week 9's claims record carried forms and limits; in a real split the claims system holds claim facts and the policy admin system holds terms, forms, deductibles and limits. The agent now has to call `coverage_in_force` to get any of them — one more hop, and a hop it can skip. | data build | open |
| 3 | The Week 5 redactor has no rule for injuries; the capstone notes carry them ("cut his hand … 4 stitches", "treated in hospital for smoke inhalation"). Added a sentence-level HEALTH rule, run after the name rules. Cost: a quoted exclusion that says "bodily injury" is redacted in an output too. | redaction test | open |
| 4 | The first injury placeholder, `[INJURY]`, matched its own pattern, so the leak check refused clean text; and `Mr.` ended the "sentence" early, splitting a name across the redaction. | redaction test | open |
| 5 | The Week 11 tracer only knew the host side. The MCP servers had no idea which request a call belonged to, so "one trace id across every hop" was not true. The id now rides in each call's JSON-RPC `_meta` and both servers log their own span under it. | trace-id test | open |
| 6 | The Week 6 judge was validated on a claim summary with a COVERAGE POSITION line; the integrated output is a referral with an *assessment* and no coverage position at all. Its agreement has to be re-measured on integrated outputs, not assumed. | eval design | open |
| 7 | The Week 7 reference decisions are COVERED / DENIED / UNDETERMINED; compliance forbids the system from stating either of the first two. They were mapped to assessments (NO_EXCLUSION_TRIGGERED, EXCLUSION_APPEARS_TO_APPLY, FACTS_NEEDED) — a mapping, so a judgement. | data build | open |
| 8 | Six tools over two servers cost more tokens per claim than the Week 9 agent's four, against the same 200,000-token daily cap on the free Groq tier: a 25-case suite run is most of a day's budget. | budget check | open |
| 9 | `policy_line` lived on the Week 9 claim record and is now a policy fact; the `product` scope on `search_policy` depends on the agent passing it through from `coverage_in_force`. | data build | open |
