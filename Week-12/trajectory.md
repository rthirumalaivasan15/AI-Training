# trajectory.md - the integrated agent's paths, run `after`

**Tool-choice accuracy 127/127 = 100%. Outcome pass 19/25 (76%), trajectory pass 24/25 (96%): gap -20 points.**

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
| CLM-2024-10001 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > refer_to_adjuster | - |
| CLM-2024-10002 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > refer_to_adjuster | - |
| CLM-2024-10003 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > search_policy > refer_to_adjuster | - |
| CLM-2024-10004 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > refer_to_adjuster | - |
| CLM-2024-10005 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > refer_to_adjuster | - |
| CLM-2024-10006 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > refer_to_adjuster | - |
| CLM-2024-10007 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > refer_to_adjuster | - |
| CLM-2024-10008 | FAIL | FAIL | get_claim_status > get_adjuster_notes > coverage_in_force > refer_to_adjuster | 0 searches, accepted 1-3; never retrieved the edition in force |
| CLM-2024-10009 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > refer_to_adjuster | - |
| CLM-2024-10010 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > refer_to_adjuster | - |
| CLM-2024-30011 | FAIL | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > refer_to_adjuster | - |
| CLM-2024-30012 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > refer_to_adjuster | - |
| CLM-2025-30013 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > refer_to_adjuster | - |
| CLM-2024-30021 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > search_policy > refer_to_adjuster | - |
| CLM-2024-30022 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > search_policy > refer_to_adjuster | - |
| CLM-2024-30023 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > refer_to_adjuster | - |
| CLM-2024-30031 | FAIL | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > search_policy > refer_to_adjuster | - |
| CLM-2024-30034 | PASS | PASS | get_claim_status > get_adjuster_notes > coverage_in_force > search_policy > refer_to_adjuster | - |
