# race_table.md - single agent vs claims squad, same 10 Week-6 cases, same judge

Cases (from `../Week-6/cases.jsonl`, sha `400bb0047d97`): C01, C02, C05, C06, C09, C10, C14, C15, C18, C19 - the first two of each Week 5 failure mode.
Judge: Week 6 `judge_v2.txt` (sha `af8559b5e5e4`) on `openai/gpt-oss-20b` + the 4 Week 6 assertions; PASS = all four assertions and judge PASS. Both arms: `openai/gpt-oss-120b` on Groq, temperature 0.

| arm | pass rate | p50 latency | p99 latency | total tokens (10 cases) | cost per claim |
|---|---|---|---|---|---|
| single agent | **8/10** | 4.02 s | 6.20 s | 47,339 | $0.001234 |
| claims squad (orchestrator) | **4/10** | 8.06 s | 11.04 s | 78,382 | $0.002384 |

**Context re-send multiplier = 78382 / 47339 = 1.7x; largest share: orchestrator -> coverage worker, 57% of all multi tokens**

Model calls: single 24, squad 55. Prompt / completion tokens: single 35,689 / 11,650, squad 51,533 / 26,849. The notes went to two squad calls (plan + notes worker): 6,234 prompt tokens between them. Rate-limit waits, excluded from latency: single 195 s, squad 411 s. Judge tokens (gpt-oss-20b, not in either arm's bill): single 50,490, squad 56,718.

Latency is active seconds (model + tool calls + retry backoff, rate-limit waits excluded); the squad's is its critical path. Percentiles are nearest-rank over 10 cases, so p99 is the slowest claim. Cost uses the prices in `llm.py` ($0.15 / $0.60 per 1M input / output tokens).

## Per case

| case | mode | single: position / verdict / tok / s | multi: position / verdict / tok / s |
|---|---|---|---|
| C01 | 1 | PARTIAL / PASS / 6563 / 6.20 | PARTIAL / FAIL (judge FAIL) / 11311 / 11.04 |
| C02 | 1 | DENIED / PASS / 3749 / 3.44 | DENIED / PASS / 10660 / 9.55 |
| C05 | 2 | DENIED / PASS / 3872 / 3.99 | DENIED / PASS / 6072 / 9.96 |
| C06 | 2 | COVERED / PASS / 3459 / 3.26 | COVERED / FAIL (judge FAIL) / 6649 / 7.98 |
| C09 | 3 | COVERED / PASS / 3834 / 4.02 | UNDETERMINED / FAIL (judge FAIL) / 6787 / 7.01 |
| C10 | 3 | UNDETERMINED / FAIL (judge FAIL) / 8242 / 5.85 | UNDETERMINED / FAIL (judge FAIL) / 8834 / 8.72 |
| C14 | 4 | DENIED / FAIL (date_of_loss) / 6038 / 5.36 | DENIED / FAIL (date_of_loss) / 8694 / 8.04 |
| C15 | 4 | DENIED / PASS / 3510 / 3.39 | DENIED / PASS / 6177 / 7.81 |
| C18 | 5 | UNDETERMINED / PASS / 4273 / 5.58 | COVERED / PASS / 6513 / 8.06 |
| C19 | 5 | PARTIAL / PASS / 3799 / 5.15 | UNDETERMINED / FAIL (judge FAIL) / 6685 / 9.11 |
