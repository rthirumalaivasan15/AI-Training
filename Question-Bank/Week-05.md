# Week 5 — Error Analysis: Reading Traces Like a Professional

Module 3 · Evals & Error Analysis · THE CORE · build week

Topics: complete traces · random vs curated sampling · open coding · error taxonomy ·
frequency × severity · choosing the fix target · benchmarks (MMLU, HumanEval) vs your app ·
writing a prediction first

---

### Q1. What is a "complete" trace?

A structured record of one request with enough detail to **understand and replay** the
answer later:
- request id and timestamp;
- the input (redacted);
- prompt version and a hash of the prompt text;
- retrieval details: query, chunk ids, ranks, scores, settings;
- tool calls with arguments, results and errors;
- model name and parameters;
- the **raw** model output, before parsing;
- tokens, cost and latency per step;
- errors and stop reasons — failures get a trace too.

"Replayable" means you can rebuild the exact model input from the trace and run it again —
for example to check a fix on the precise request that failed. A log of question + final
answer is not a trace.

**In this project:** every Week 5 trace records `prompt_version`, `prompt_sha`, `model`,
the retrieved chunk ids with ranks, and the `corpus_sha` of the indexed corpus — Week 6
refuses to replay a trace if the corpus has moved since it was written.

### Q2. How do you keep personal data out of traces?

**Redact on the way in, before anything reaches disk** — never "clean it up later", because
copies spread to backups, dashboards and vendors first.
- pattern-based redaction for structured identifiers (emails, phones, ID formats);
- known-value redaction for names you already hold in the record;
- stable pseudonyms (a keyed hash, e.g. HMAC with a secret) when you still need "same
  person" analysis;
- a verification pass that refuses to write a record that still matches a sensitive pattern.

Plus access control, retention limits and encryption on the trace store.

**In this project:** `Week-5/redact.py` runs before the trace writer. Two leaks were found on
a discarded first run: the model wrote a claimant back as a bare first name (fixed by sweeping
removed name tokens through every field), and a hand-written stoplist turned an endorsement
title into `[NAME]` (fixed by deriving the stoplist from the corpus).

### Q3. Why take a seeded random sample instead of looking at examples you noticed?

The failures you notice are **biased** — dramatic ones, complaints, things you already
suspected, the first page of the log. Fixing those leaves the common, quiet failures alone.

A fair sample is drawn **at random** from the whole population, with a **fixed seed chosen by
a rule before looking** (so you cannot re-roll until it looks right, and anyone can
reproduce it), records the population it came from, and is big enough for a first pass
(roughly 20–100).

**In this project:** 20 of 117 traces, seed `20250907` (the date, chosen before the file was
read); `sample.py` sorts trace ids before sampling so file order cannot change the draw. The
random 20 failed **35%**; the hand-picked demo 10 failed **10%** — the demo set would have
hidden most of the problem.

### Q4. What is open coding, and why write notes before choosing categories?

Read each sampled trace in full — retrieved chunks, tool calls, output — and write **one
honest sentence** on what went wrong (or that nothing did), in your own words, *before* you
have any categories. For example: "Says the endorsements are silent; the clause exists but
was never fetched."

Categories chosen first become boxes you force traces into, so you only find the failures you
expected. Notes first let the categories come out of the data, and keep them concrete.

### Q5. How do you turn notes into an error taxonomy?

1. Group similar notes.
2. Name each group with a specific behaviour ("attaches a consequence to a clause that states
   no consequence"), not a vague label ("hallucination").
3. Write a definition two people would apply the same way, with an example trace id.
4. Aim for roughly 4–7 categories.
5. Count each category in the sample.
6. Read more traces until new ones fit existing categories (saturation).

The taxonomy becomes the backbone of evaluation: each category gets test cases, and progress
is measured per category.

**In this project:** 5 named modes from 20 traces — e.g. "says the endorsements are silent
when the clause exists but was not fetched" (2/20) and "applies an exception without testing
the definition it depends on" (1/20) — each with a trace id.

### Q6. How do you rank failure modes?

**Frequency × severity.** Frequency is the count in the sample; severity is the harm when it
happens. For a claims assistant, "wrongly pays" outranks "wrongly denies", which outranks
"verbose answer". A rare catastrophic mode can outrank a frequent cosmetic one. Also weigh
the cost of the fix and whether one fix covers several modes. Write the ranking down with
its reasons.

**In this project:** 13 of 20 clean, 7 failed — and every failure was claim-affecting: six
wrong denials and one wrong payment. The manager's "it sometimes gets coverage wrong" became a
ranked table with a trace id against each mode.

### Q7. How do you choose which problem to fix next?

Pick the mode with the highest frequency × severity that has a **plausible single change**
behind it, and confirm the mechanism first: replay a failing trace and check that the cause
you believe in is really the cause. One change at a time — if you change three things and the
number moves, you cannot say which change moved it.

**In this project:** the Week 5 target was mode 5 — the 0.35 retrieval score floor refusing
answerable questions on the score alone. It was joint-last in the sample (1/20), but it was the
one mode checked against the whole file, where it fired on **19 of 117 traces (16%)**. A
one-trace swing moves any sample count by 5 points, so a full-population count beat a sample
estimate.

### Q8. Why write the prediction down before running the fix?

A dated, committed prediction — what will move, by how much, and what it will cost — keeps
you honest: you cannot reinterpret any outcome as success afterwards. It forces you to state
the mechanism, and comparing predictions with results calibrates how well you understand the
system. A wrong prediction is useful: it shows where your model of the system is wrong.

**In this project:** commit `3f4ab4d` (2026-09-07), before any fix: remove the 0.35 floor;
expect score-floor refusals **19/117 → 0/117**, at least 12 of those 19 correctly cited, at
most 3 unsupported.

### Q9. What do benchmarks like MMLU and HumanEval tell you about your app?

- **MMLU** — multiple-choice questions across 57 subjects: broad general knowledge.
- **HumanEval** — 164 Python programming problems scored by unit tests (pass@k).

They help shortlist **models**. They say nothing about **your application**: your documents,
your retrieval, your prompts, your failure modes. Scores can also be inflated by test data
leaking into training. A model that leads on MMLU can still deny claims because retrieval
missed the clause. Your own eval set, built from your own failures, is the number that
matters.

### Q10. How many traces should you read, and who should read them?

Enough for the categories to **stabilise** — when new traces mostly land in existing modes.
A first pass of 20–100 is common; repeat after every significant change, because new failure
modes appear.

The reader should be someone who knows what a correct answer looks like — a **domain
expert** (here, a claims adjuster) or an engineer working closely with one. One accountable
person keeps the categories consistent. This part cannot be automated: it is where you
discover the failure modes you never guessed.
