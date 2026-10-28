# eval_report.md - the integrated system, run `after`

One command: `python app.py eval after`. Every case runs through the same entry point, agent, MCP servers and tracing as production. PASS = all 8 assertions and the Week 6 judge.

**Cases run: 25 of 25.** 8 ran before the edition gate in `refer_to_adjuster` (seam 11, 2026-10-27 18:19), 17 after it.

**Pass rate: 19/25 (76%).** Wrong-endorsement-version citation rate: **1/25 (4%)**. Judge agreement with the reference decisions: **21/25 = 84%**.

With the cases that ran before the edition gate re-run (`gate`): **pass 20/25 (80%), wrong-endorsement-version citation rate 0/25 (0%).**

## Before -> after on the same 7 cases (`before` -> `after` -> `gate`)

`gate` re-runs a case that ran before the seam-11 edition check in `refer_to_adjuster` existed; every other case in `after` already ran with it.

| case | mode | before | after | after, with the edition gate |
|---|---|---|---|---|
| CLM-2024-30001 | version-straddle | FAIL: assessment, cites | FAIL: judge | not re-run: no wrong edition cited, nothing for the gate to refuse |
| CLM-2024-30002 | version-straddle | FAIL: assessment, cites, judge | PASS | not re-run: no wrong edition cited, nothing for the gate to refuse |
| CLM-2025-30003 | version-straddle | PASS | PASS | not re-run: no wrong edition cited, nothing for the gate to refuse |
| CLM-2025-30004 | version-straddle | PASS | PASS | not re-run: no wrong edition cited, nothing for the gate to refuse |
| CLM-2025-30005 | version-straddle | PASS | PASS | not re-run: no wrong edition cited, nothing for the gate to refuse |
| CLM-2024-30032 | wording-not-on-file | FAIL: assessment, edition, judge | FAIL: assessment, edition, judge | PASS |
| CLM-2024-30033 | wording-not-on-file | FAIL: judge | FAIL: judge | FAIL: judge |

**Wrong-endorsement-version citation rate: 1/7 -> 1/7 -> 0/7. Pass: 3/7 -> 4/7 -> 5/7.**

## Judge agreement, re-measured on the integrated outputs (`rejudge.py after`)

The same Week 6 judge on the same stored referrals, two ways. **Reading every edition in the library: 21/25 = 84%. Reading only the wording in force on each loss date: 21/25 = 84%.** Target 85%.

| case | reference | judge, every edition | judge, wording in force on the loss date |
|---|---|---|---|
| CLM-2024-30001 | PASS | FAIL | PASS |
| CLM-2024-30002 | PASS | PASS | PASS |
| CLM-2025-30003 | PASS | PASS | PASS |
| CLM-2025-30004 | PASS | PASS | PASS |
| CLM-2025-30005 | PASS | PASS | PASS |
| CLM-2024-30032 | FAIL | FAIL | FAIL |
| CLM-2024-30033 | PASS | FAIL | FAIL |
| CLM-2024-10001 | PASS | PASS | PASS |
| CLM-2024-10002 | PASS | PASS | PASS |
| CLM-2024-10003 | PASS | PASS | PASS |
| CLM-2024-10004 | PASS | PASS | PASS |
| CLM-2024-10005 | PASS | PASS | PASS |
| CLM-2024-10006 | PASS | PASS | FAIL |
| CLM-2024-10007 | PASS | PASS | PASS |
| CLM-2024-10008 | PASS | PASS | PASS |
| CLM-2024-10009 | PASS | PASS | PASS |
| CLM-2024-10010 | PASS | PASS | PASS |
| CLM-2024-30011 | PASS | FAIL | FAIL |
| CLM-2024-30012 | PASS | PASS | PASS |
| CLM-2025-30013 | PASS | PASS | PASS |
| CLM-2024-30021 | PASS | PASS | PASS |
| CLM-2024-30022 | PASS | PASS | PASS |
| CLM-2024-30023 | PASS | PASS | PASS |
| CLM-2024-30031 | FAIL | PASS | PASS |
| CLM-2024-30034 | PASS | PASS | PASS |

## Pass rate per case mode

| mode | n | pass | rate |
|---|---|---|---|
| clean | 2 | 2 | 100% |
| limits | 3 | 3 | 100% |
| missing-notes | 2 | 1 | 50% |
| not-in-force | 3 | 2 | 67% |
| notes-trigger-exclusion | 7 | 7 | 100% |
| version-straddle | 5 | 4 | 80% |
| wording-not-on-file | 2 | 0 | 0% |
| wrong-property | 1 | 0 | 0% |

## Assertion failures (of 25 cases)

| assertion | failed |
|---|---|
| no_covered | 0 |
| referred | 0 |
| in_force_checked | 0 |
| assessment | 2 |
| cites | 0 |
| edition | 1 |
| loss_date | 0 |
| numbers | 1 |
| judge FAIL | 4 |

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
| CLM-2024-10001 | clean | NO_EXCLUSION_TRIGGERED | - | PASS | PASS | `trc_02ab5be2a6d5` |
| CLM-2024-10002 | notes-trigger-exclusion | EXCLUSION_APPEARS_TO_APPLY | - | PASS | PASS | `trc_d63ad4143756` |
| CLM-2024-10003 | notes-trigger-exclusion | EXCLUSION_APPEARS_TO_APPLY | - | PASS | PASS | `trc_3711a9d94330` |
| CLM-2024-10004 | notes-trigger-exclusion | NO_EXCLUSION_TRIGGERED | - | PASS | PASS | `trc_139c643780cd` |
| CLM-2024-10005 | notes-trigger-exclusion | NO_EXCLUSION_TRIGGERED | - | PASS | PASS | `trc_2163a8faa6ea` |
| CLM-2024-10006 | notes-trigger-exclusion | EXCLUSION_APPEARS_TO_APPLY | - | PASS | PASS | `trc_8fb78354312a` |
| CLM-2024-10007 | clean | EXCLUSION_APPEARS_TO_APPLY | - | PASS | PASS | `trc_d671e028cea0` |
| CLM-2024-10008 | missing-notes | FACTS_NEEDED | numbers | PASS | FAIL | `trc_351855794fb0` |
| CLM-2024-10009 | notes-trigger-exclusion | NO_EXCLUSION_TRIGGERED | - | PASS | PASS | `trc_d1a6eec29370` |
| CLM-2024-10010 | missing-notes | FACTS_NEEDED | - | PASS | PASS | `trc_b420a997fe00` |
| CLM-2024-30011 | not-in-force | POLICY_NOT_IN_FORCE | - | FAIL | FAIL | `trc_25e1c00926de` |
| CLM-2024-30012 | not-in-force | POLICY_NOT_IN_FORCE | - | PASS | PASS | `trc_0d803e0b4b6c` |
| CLM-2025-30013 | not-in-force | POLICY_NOT_IN_FORCE | - | PASS | PASS | `trc_a667053ec178` |
| CLM-2024-30021 | limits | NO_EXCLUSION_TRIGGERED | - | PASS | PASS | `trc_39a8828a4837` |
| CLM-2024-30022 | limits | NO_EXCLUSION_TRIGGERED | - | PASS | PASS | `trc_a0fb19a5ac92` |
| CLM-2024-30023 | limits | NO_EXCLUSION_TRIGGERED | - | PASS | PASS | `trc_7f2a4b068dd3` |
| CLM-2024-30031 | wrong-property | FACTS_NEEDED | assessment | PASS | FAIL | `trc_922508fec297` |
| CLM-2024-30034 | notes-trigger-exclusion | EXCLUSION_APPEARS_TO_APPLY | - | PASS | PASS | `trc_9b996fadb204` |

## Judge agreement

The Week 6 judge (prompt sha-checked, `gpt-oss-20b`), re-run on the integrated outputs with the integrated wording library. Its verdict is compared with a reference label per case: PASS when the referral's assessment, citation and edition match the reference decision in `evals/cases.jsonl`. Those decisions were written from the wording before any integrated run; they are not fresh hand labels taken on these outputs. Agreement **21/25 = 84%** (target 85%).

## What this suite does NOT cover

- **Motor claims**: there is no motor wording or motor case at all; everything here is household.
- **Real claim files**: 25 authored cases, not the brief's 500 anonymised files; no photo captions.
- **Parse quality**: the wordings are clean text, so a badly parsed PDF schedule is never tested.
- **Reproducibility over time**: one run per case at temperature 0; run-to-run variation is not measured here (it was 3 different positions in 3 runs on one Week 11 case).
- **Payable amounts**: the system never computes a payout, so no case checks one.
- **Adversarial input**: no prompt injection in the notes is tested.
- **Human labels**: judge agreement is against reference decisions, not a person grading these outputs.
