# Top 3 known weaknesses — written Tuesday 2026-10-27, before anyone asked

Written from the first integrated runs, before the after-fix suite finished and before any review.
Not edited afterwards.

## 1. The same claim does not get the same answer twice

CLM-2024-30001 (a 2024 storm loss) was referred as EXCLUSION_APPEARS_TO_APPLY under E-15 on its first
end-to-end run (`trc_9e374cb5cee5`) and as WORDING_NOT_ON_FILE on its eval run an hour later — same
code, same prompt, temperature 0. Week 11 saw one case come back three different ways in three runs.
The suite runs each case once, so a pass is one draw, not a rate. **Every number in the eval report
has run-to-run variation it does not measure.**

## 2. The judge is weakest exactly where the brief is hardest

On the 7 version-boundary cases before the fix, the Week 6 judge disagreed with the reference decision
twice: it passed a 2024 storm loss referred as "wording not on file" (wrong), and failed a pre-edition
loss referred as "wording not on file" (right). Its prompt was validated on Week 6 summaries without a
second edition of any form; its agreement here is measured against reference decisions written from the
wording, not fresh hand labels. **An LLM judge that shares the app's blind spot (Week 11: it passed the
planted wrong answer) cannot be the only check — which is why the edition, in-force and limit checks are
deterministic assertions.**

## 3. Claimant PII reaches the model provider unredacted

Names, addresses and injuries are redacted before anything is logged and before anything leaves our
`policy-docs` server — but the claims system hands the raw adjuster notes to the agent, and the agent
sends them to Groq as part of every model call. The PII line holds for logs and for other squads; **it
does not hold for the model provider.** Redacting notes before the first model call would close it, at
the risk of removing a fact the triage needs (an injury can be the fact a liability exclusion turns on).
