# eval_report.md - the integrated system, run `after`

One command: `python app.py eval after`. Every case runs through the same entry point, agent, MCP servers and tracing as production. PASS = all 8 assertions and the Week 6 judge.

**Cases run: 7 of 25 - the run is still going; this report is rebuilt from whatever has finished.** 7 ran before the edition gate in `refer_to_adjuster` (seam 11, 2026-10-27 18:19), 0 after it.

**Pass rate: 4/7 (57%).** Wrong-endorsement-version citation rate: **1/7 (14%)**. Judge agreement with the reference decisions: **5/7 = 71%**.

## Before -> after on the same 7 cases (`before` -> `after`)

| case | mode | before | after |
|---|---|---|---|
| CLM-2024-30001 | version-straddle | FAIL: assessment, cites | FAIL: judge |
| CLM-2024-30002 | version-straddle | FAIL: assessment, cites, judge | PASS |
| CLM-2025-30003 | version-straddle | PASS | PASS |
| CLM-2025-30004 | version-straddle | PASS | PASS |
| CLM-2025-30005 | version-straddle | PASS | PASS |
| CLM-2024-30032 | wording-not-on-file | FAIL: assessment, edition, judge | FAIL: assessment, edition, judge |
| CLM-2024-30033 | wording-not-on-file | FAIL: judge | FAIL: judge |

**Wrong-endorsement-version citation rate: 1/7 -> 1/7. Pass: 3/7 -> 4/7.**

## Pass rate per case mode

| mode | n | pass | rate |
|---|---|---|---|
| version-straddle | 5 | 4 | 80% |
| wording-not-on-file | 2 | 0 | 0% |

## Assertion failures (of 7 cases)

| assertion | failed |
|---|---|
| no_covered | 0 |
| referred | 0 |
| in_force_checked | 0 |
| assessment | 1 |
| cites | 0 |
| edition | 1 |
| loss_date | 0 |
| numbers | 0 |
| judge FAIL | 3 |

## Every case

| case | mode | assessment | assertions failed | judge | pass | trace |
|---|---|---|---|---|---|---|
| CLM-2024-30001 | version-straddle | EXCLUSION_APPEARS_TO_APPLY | - | FAIL | FAIL | `trc_c66b247d566d` |
| CLM-2024-30002 | version-straddle | EXCLUSION_APPEARS_TO_APPLY | - | PASS | PASS | `trc_8d7057567c5d` |
| CLM-2025-30003 | version-straddle | NO_EXCLUSION_TRIGGERED | - | PASS | PASS | `trc_a074d9ccf827` |
| CLM-2025-30004 | version-straddle | NO_EXCLUSION_TRIGGERED | - | PASS | PASS | `trc_2ab0cc106eb2` |
| CLM-2025-30005 | version-straddle | EXCLUSION_APPEARS_TO_APPLY | - | PASS | PASS | `trc_41db93dfc3e6` |
| CLM-2024-30032 | wording-not-on-file | EXCLUSION_APPEARS_TO_APPLY | assessment, edition | FAIL | FAIL | `trc_d41d68b1a7ad` |
| CLM-2024-30033 | wording-not-on-file | WORDING_NOT_ON_FILE | - | FAIL | FAIL | `trc_c10683925475` |

## Judge agreement

The Week 6 judge (prompt sha-checked, `gpt-oss-20b`), re-run on the integrated outputs with the integrated wording library. Its verdict is compared with a reference label per case: PASS when the referral's assessment, citation and edition match the reference decision in `evals/cases.jsonl`. Those decisions were written from the wording before any integrated run; they are not fresh hand labels taken on these outputs. Agreement **5/7 = 71%** (target 85%).

## What this suite does NOT cover

- **Motor claims**: there is no motor wording or motor case at all; everything here is household.
- **Real claim files**: 25 authored cases, not the brief's 500 anonymised files; no photo captions.
- **Parse quality**: the wordings are clean text, so a badly parsed PDF schedule is never tested.
- **Reproducibility over time**: one run per case at temperature 0; run-to-run variation is not measured here (it was 3 different positions in 3 runs on one Week 11 case).
- **Payable amounts**: the system never computes a payout, so no case checks one.
- **Adversarial input**: no prompt injection in the notes is tested.
- **Human labels**: judge agreement is against reference decisions, not a person grading these outputs.
