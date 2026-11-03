# Week 12 — Capstone: Ship It and Defend It

Module 6 · Production · capstone week

Topics: integration · single entry point · fixing the seams · full eval suite · known weak spots ·
packaging (README, eval report) · fresh-eyes test · the four-part demo · defending your numbers

---

### Q1. What does "integration" mean in the capstone, and why is nothing new taught?

Joining the eleven weeks' parts into **one system**: documents and retrieval (RAG), the agent and its
tools, MCP servers, the eval suite, and logging. The skill being tested is making the parts work
**together**. Each part worked alone; the hard bugs live where they meet.

**In this project:** RAG over 7 wordings → a hand-built agent loop → 6 tools discovered over MCP from two
servers (a claims-system stand-in and our own `policy-docs`) → a referral to an adjuster, with one trace id
across every hop.

### Q2. Why one entry point and one command?

So a stranger, a reviewer or a scheduler can run the **whole** system the same way every time, with no
"first start this, then run that". One entry point also makes sure the eval suite tests **the same path
production uses**, not a side copy.

**In this project:** `python app.py triage CLM-2025-30004` runs one claim end to end, from claim in to
referral out. `app.py eval`, `app.py trace` and `app.py report` use the same `handle()` function the
triage uses.

### Q3. What is a "seam", and why keep a seam list?

A **seam** is where two parts that worked alone don't fit together: a field one part drops, an assumption
the other part relied on. A **seam list** is written **while integrating** (on Tuesday), left **unedited**,
and each seam is later marked **fixed**, **accepted** or **ran out of time**, with the date. It shows the
work honestly, including what was not finished.

**In this project:** 11 seams. The worst was **seam 1**: the Week 9 search dropped the edition and had no
date, so once a 2025 edition joined the library, a 2024 storm query returned **3 of 4 passages from the
2025 wording**. Fixed: `search_policy` now requires the loss date and returns only wording in force on it.

### Q4. How do you run the full eval suite on an integrated system?

- **25–40 cases** run through the **real entry point**, not a test-only path.
- **Assertions first** (cheap, exact, in code), **then the judge**.
- Report the pass rate **per failure mode with n**, not just one average.
- **Re-check the judge** on the integrated outputs. It was validated on the old output format, so its
  agreement must be measured again (target ≥ 85%).
- Show **before → after** on a named metric, with the sample size.

**In this project:** 25 cases, 8 assertions (never says "covered", referred, in-force checked against the
loss date, assessment, citation, **edition in force on the loss date**, loss date, three separate numbers),
then the Week 6 judge. **19/25 pass (76%), 20/25 with the pre-gate cases re-run.** Judge agreement **21/25 =
84%, under the 85% target**, and reported as such.

### Q5. What does re-scoring the error taxonomy show, and what is a mode "created by integration"?

Re-run the Week 5 taxonomy on the integrated system: **4–7 named failure modes**, each with frequency %,
severity and one trace id. At least one mode must be **new**: impossible in the separate parts, created
only by joining them.

**In this project:** 7 modes, 2 of them new:
- **Mode 1:** a second edition crowds the in-force one out of the top results, so wording that **is** on
  file is reported as "not on file": **2/7 (29%) before the fix, 0 after**. It could not exist before:
  no form had two editions.
- **Mode 3:** **the judge itself** applied the 2025 wording to a 2024 loss and failed a correct referral.
  The grader had the client's bug too.

### Q6. Why write down your known weak spots before anyone asks?

Because a reviewer will find them anyway. Naming them first, **dated before review**, shows you
understand your system's limits and aren't hiding them. It is part of the 30 marks for failure-finding.
A list written after the review is worth nothing.

**In this project** (`weaknesses.md`):
1. The same claim does not always get the same answer twice, so every pass rate is one draw.
2. The judge is weakest exactly on the version-boundary cases.
3. Claimant names and injuries are kept out of logs and out of our server's replies, but they still
   reach the model provider.

### Q7. What makes a project "packaged": README and eval report?

- **README:** a stranger can go from clone to a working answer **without asking you anything**. It has
  setup steps, the one command, what each command does, and where each deliverable is.
- **Eval report:** pass rate per mode with n, judge agreement, before → after, **and an explicit list of
  what the suite does NOT cover**. Leaving out what you didn't test reads as claiming you tested
  everything.

**In this project:** `README.md` (setup, one command, a commands table, a deliverables table) and
`eval_report.md`. The report states what is not covered: no motor claims, 25 authored cases rather than real
claim files, no parse-quality testing, no measurement of run-to-run variation, no prompt-injection test, and
judge agreement measured against reference decisions rather than fresh human labels.

### Q8. What is the fresh-eyes test?

Someone from **another squad**, who didn't build it, follows **only your README** to run the system, and
calls **your MCP server from their own agent**. You record who they were, where they got stuck and for
how long, what your server returned to them, and what you changed because of it. It proves the package
works for a stranger and that your server is a real capability someone else can use.

**In this project:** `REVIEWER.md` holds their steps. `fresh_eyes.md` is filled in only from what a real
reviewer reports. Until then it says "not yet run", rather than being made up.

### Q9. What are the four parts of the 10-minute demo, and why is a flawless demo a red flag?

1. **A real run:** a live claim in, coverage checked against the loss date as a visible tool call, the
   exclusion cited by clause **and edition**, deductible / sub-limit / limit as **three** numbers,
   referred to a human.
2. **The failures you found:** the trace, its frequency in the taxonomy, and the mode integration
   created.
3. **A number that moved:** before → after, with n and the judge's agreement, plus one sentence on what
   the suite does not measure.
4. **What's next:** the eval case that now guards the failure, cost per claim, and what breaks first at
   10× volume.

A demo where nothing fails means the failures are hidden. Marks go to **finding real failures**, not to
polish.

**In this project:** the run is `CLM-2025-30004`: HO-0304 **ed. 01-25**, deductible **750**, sub-limit
**5,000**, limit **260,000**. The failure is a 2024 loss getting 2025 wording. The number: **wrong-edition
citations 1/7 → 1/7 → 0/7**, pass 3/7 → 4/7 → 5/7. In the re-run (`trc_40d52edd723e`) the model made the
same wrong-edition mistake, **the server refused it**, and the model referred correctly.

### Q10. How do you defend your numbers under hostile questions?

- **Answer with the specific cases, not the average.** "How do the version-boundary cases score?" →
  "5 straddle cases: 3/5 before, 4/5 after."
- **Show the code that enforces a rule, not the prompt that asks for it.** "Does it ever say 'covered'?" →
  the `no_covered` assertion and the refusal in `refer_to_adjuster`.
- **Show the trace.** The id, the edition cited, the loss date, the numbers.
- **Say what you cannot prove.** Same model output in 18 months is not guaranteed (run-to-run variation),
  even though the trace keeps the prompt sha, model, chunk ids and loss date.
- **State a miss plainly.** "Judge agreement is 84%, under the 85% target. It fails correct
  'not in force' referrals because it was validated on covered / denied summaries."

**In this project:** cost **$0.0022 per claim** (91% generation). In a hailstorm week of 18,000 FNOLs,
**the daily token cap breaks first: 28.4 million tokens a day against 200,000 (142× over)**, and it is
already 3.3× over at normal volume. Cost is about $40 for the week, so money isn't the problem.
