# taxonomy.md - the Week 5 taxonomy re-scored on the integrated system

Built by `python app.py report after before` from the eval rows and their traces; a case can sit in more than one mode. Frequency is the share of the run's cases. Rebuilt whenever the run grows.

| # | mode | origin | severity | `before` n=7 | `after` n=7 | example trace |
|---|---|---|---|---|---|---|
| 1 | A second edition crowds the one in force out of the top 4, so wording that is on file is reported as WORDING_NOT_ON_FILE | **NEW - created by integration**: no form had two editions until the 2025 HO-0304 joined the library | High - the adjuster is told there is no wording and the exclusion is never put to them | 2 (29%) | 0 (0%) | `trc_5fed79106eff` |
| 2 | Cites an edition the policy did not carry on the loss date | Week 5 mode 3 (answers from whichever endorsement came back), now across editions | Critical - the brief's live wound: a loss assessed against wording that was not its contract | 1 (14%) | 1 (14%) | `trc_d41d68b1a7ad` |
| 3 | The judge applies a newer edition to an older loss and fails a correct referral | **NEW - created by integration**: the Week 6 judge reads the whole library, which held one edition per form until now | Medium - no claim is harmed, but the eval reports a correct system as broken | 1 (14%) | 2 (29%) | `trc_c66b247d566d` |
| 4 | The judge passes a referral the reference decision fails | Week 11 (the judge passed the planted wrong answer) | High - a wrong referral reaches the report as a pass | 1 (14%) | 0 (0%) | `trc_5fed79106eff` |
| 5 | Misreads the notes: wrong assessment with the right wording | Week 5 modes 2 and 4 | High - the wrong exclusion question is put to the adjuster | 0 (0%) | 0 (0%) | not seen |
| 6 | Deductible, sub-limit and policy limit confused | Week 7 | High - the number juniors mix up weekly, now in a referral | 0 (0%) | 0 (0%) | not seen |
| 7 | Ends without a valid referral, or never checks in-force against the loss date | Week 7 / Week 9 agent stops | Critical - nothing reaches the adjuster, or the term is assumed | 0 (0%) | 0 (0%) | not seen |

Clean in `after`: 4 of 7. Never seen in any run: the word "covered" in a referral - `refer_to_adjuster` refuses it in code, and `gates.py` replays that refusal.

## Traces read by hand

- `trc_c66b247d566d` (CLM-2024-30001, after): assertions all pass; the judge cited the 2025 Storm Ingress Allowance against an August 2024 loss. Mode 3 - seam 10.
- `trc_d41d68b1a7ad` (CLM-2024-30032, after): `search_policy` was called with the bare form `HO-0415`, the seam-1 fix resolved it to ed. 01-24 (in force on the date) though the policy carries ed. 05-23. Mode 2 - seam 11, gate added to `refer_to_adjuster`.
- The two `before` storm losses (CLM-2024-30001/30002): retrieval returned three 2025 chunks out of four, the 2024 E-15 row never reached the model, and it referred as WORDING_NOT_ON_FILE. Mode 1 - seam 1.
