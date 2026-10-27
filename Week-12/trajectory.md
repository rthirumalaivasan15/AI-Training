# trajectory.md - the integrated agent's paths, run `after`

**Tool-choice accuracy 37/37 = 100%. Outcome pass 4/7 (57%), trajectory pass 7/7 (100%): gap -43 points.**

Accepted path: the claim tools first; `coverage_in_force` with the claim's loss date before any search or referral; 1-3 searches when the policy is in force and wording is on file (0 when it is not in force, 0-3 when the wording is not on file); at least one retrieved chunk of an edition the policy term carries; end in `refer_to_adjuster`. Tool-choice accuracy counts every call that was acceptable at that point.

| case | outcome | trajectory | path | why the path fails |
|---|---|---|---|---|
| CLM-2024-30001 | FAIL | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > refer_to_adjuster | - |
| CLM-2024-30002 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > refer_to_adjuster | - |
| CLM-2025-30003 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > refer_to_adjuster | - |
| CLM-2025-30004 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > refer_to_adjuster > refer_to_adjuster | - |
| CLM-2025-30005 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > refer_to_adjuster | - |
| CLM-2024-30032 | FAIL | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > refer_to_adjuster | - |
| CLM-2024-30033 | FAIL | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > search_policy > refer_to_adjuster | - |
