# The 10-minute demo — four parts, to the clock

Open beforehand: a terminal in `Week-12` with the venv active, `taxonomy.md`, `eval_report.md`,
`cost_10x.md`, `weaknesses.md`, `referrals/CLM-2024-30001.md`. Run `python gates.py` once before you
start (free, no model calls) so you know the gates hold.

**If Groq rate-limits the live run** (free tier: 200,000 tokens a day): do not wait. Say so, and show
the same claim from the eval run instead: `python app.py trace trc_2ab0cc106eb2` and
`referrals/CLM-2025-30004.md`. A limit hit live is itself Part 4's number.

---

## Part 1 — a real run (0:00–3:00)

```
python app.py triage CLM-2025-30004
```

Say: *"A storm on 14 March 2025, 66 mm of rain, water through a basement window."* While it runs:

1. **Coverage in force, checked against the loss date, as a tool call:** point at `coverage_in_force`
   in the trace (`python app.py trace <id>`). It is called with `2025-03-14`. The agent has no other way to
   learn the term, the forms or the limits.
2. **The exclusion cited by clause and endorsement version:** the referral cites *HO-0304 **ed. 01-25** —
   E-15 and its storm-ingress exception, resolved for loss date 2025-03-14*. Click the link: it opens the
   wording at that line.
3. **Three separate numbers:** deductible **750**, sub-limit **5,000** (Storm Ingress Allowance), policy
   limit **260,000**.
4. **Referred, not decided:** "Queued for: claims adjuster". Say: *"It cannot say covered. The
   referral tool refuses that word in code."* Show it: `python gates.py`, line *"'covered' in a referral is
   refused"*.

## Part 2 — the failures we found (3:00–6:00)

1. **The client's wound, in our own system.** When the 2025 HO-0304 edition joined the library, a 2024
   storm loss (CLM-2024-30001, 11 Aug 2024) came back with **3 of 4 passages from the 2025 wording**. The
   2024 E-15 row never reached the model, and it referred as "wording not on file". Trace
   `trc_5fed79106eff`. Seam 1 in `seams.md`.
2. **Its frequency** (`taxonomy.md`, mode 1): 2 of the 7 version cases before the fix (29%), 0 after.
3. **The modes integration created.** Mode 1 above could not exist before Week 12: no form had two
   editions. Mode 3: **our own judge** applied the 2025 Storm Ingress Allowance to an August 2024 loss and
   failed a correct referral (trace `trc_c66b247d566d`, seam 10). The grader had the client's wound too.
4. **The fix after the fix.** The first after-fix run found that a bare form number resolves to the
   edition in force on the date, not the edition the policy carried. CLM-2024-30032 holds HO-0415
   ed. 05-23, and the system cited ed. 01-24 (trace `trc_d41d68b1a7ad`, seam 11). It is closed by an edition
   check in `refer_to_adjuster`.
5. **The two other weaknesses, written down before review** (`weaknesses.md`): the same claim does not
   always get the same answer twice, so every number here is one draw. And claimant names and injuries are
   redacted from logs and from our server's returns, **but they still go to the model provider**.

## Part 3 — a number that moved (6:00–8:00)

From `eval_report.md`, on the same 7 version-boundary cases, before → after:

- **The two 2024 storm losses:** referred "wording not on file" **2/2 → E-15 ed. 03-24 cited, 2/2**.
- **Wrong-endorsement-version citations: 1/7 → 1/7 → 0/7. Pass: 3/7 → 4/7 → 5/7.** Say plainly that the
  date fix alone did not move the wrong-edition number. The edition gate (seam 11) did. In the re-run
  (trace `trc_40d52edd723e`) the model **made the same mistake again**: it cited HO-0415 ed. 01-24. The server
  refused it, and the model referred as WORDING_NOT_ON_FILE. That is the gate working live, not the model
  getting lucky.
- **n and the judge:** the full suite is **25 cases: 19/25 pass (76%), 20/25 (80%) with the gate re-run, and 0/25
  wrong-edition citations.** Judge agreement with the reference decisions is **21/25 = 84%: below the 85%
  target. Say so.** It is also 84% when the judge reads only the wording in force on each loss date. The misses
  are mode 3: the Week 6 judge was validated on COVERED / DENIED summaries and fails correct "policy not in force"
  and "wording not on file" referrals. The fix is to re-validate the judge prompt on referrals, which we ran
  out of time for.
- **Bonus:** hit-rate@3 on the Week 4 golden set: 9/12 in Week 4 → **8/12** when the 2025 edition joined →
  **9/12** with the date filter (`runs/hitrate.md`).
- **One sentence on what the suite does not measure:** *"Nothing here is a motor claim, a real claim file
  or a person's label. The 25 cases are authored, and run-to-run variation is not measured."*

## Part 4 — what's next (8:00–10:00)

1. **The case that now guards the failure:** `evals/cases.jsonl` holds the 5 straddle cases (including
   CLM-2024-30002, dated **31 Dec 2024, the day before the 2025 edition**) and CLM-2024-30032. `gates.py`
   replays the exact wrong-edition referral from trace `trc_d41d68b1a7ad` and expects a refusal. It runs in
   seconds with no model call. **Run it live: `python gates.py` → "GATES 9/9 hold".**
2. **Cost per claim triaged** (`cost_10x.md`): about **$0.002**. 92% of it is generation; retrieval and
   tools cost only the tokens they add.
3. **What breaks first in a hailstorm week (18,000 FNOLs):** **the daily token cap.** It needs 28.4 million
   tokens a day against 200,000, which is 142× over. It already breaks at normal volume (3.3× over). Cost
   does not break: about $39 for the whole week. The plan: a paid tier first, then fewer laps per claim,
   then a queue.

---

## Hostile questions — the short answers

- **"How many cases straddle a version boundary, and what do they score?"** 5 straddle cases: **3/5 before →
  4/5 after.** All 5 pass every assertion after. The fifth (CLM-2024-30001) fails only because the judge
  applied the 2025 wording, and it passes when the judge reads only the wording in force on the loss date.
  Be honest that 3 of the 5 were already green before: they are 2025 losses, and the 2025 wording was
  already winning the search. Only the two 2024 losses were red.
- **"Does it ever say covered?"** No. Show the assertion `no_covered` in `suite.py`, and the refusal in
  `policy_server.py` (`refer_to_adjuster`). That is the code that enforces it, not a prompt asking for it.
- **"Show the trace where it got the sub-limit right."** `trc_2ab0cc106eb2`: sub-limit 5,000 is a separate
  field from deductible 750 and limit 260,000. The `numbers` assertion would have failed it otherwise.
- **"Can you reproduce an answer in 18 months?"** The trace keeps the prompt version and sha, the model,
  the retrieved chunk ids (which name the edition) and the loss date. The wording files are in the repo.
  What we cannot promise is the same model output: run-to-run variation is weakness 1.
- **"What is in your logs, and what did your server hand another squad?"** Redacted traces in `logs/`, and
  the server's own spans in `logs/mcp_policy-docs.jsonl`. Policy records hold no claimant identity, and
  referral facts are redacted before they are stored or returned (`gates.py` checks a name and an injury).
  The gap: raw notes reach the model provider.
