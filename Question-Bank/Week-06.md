# Week 6 — Evals: Measuring Whether a Change Actually Helped

Module 3 · Evals & Error Analysis · THE CORE · build week

Topics: eval sets · regression tests from failures · assertion checks · LLM-as-judge ·
G-Eval · binary vs 1–10 scoring · judge validation (human agreement) · RAGAS faithfulness ·
answer relevancy · context precision and recall · before/after deltas

---

### Q1. What makes a good eval set?

- **Real inputs** — phrased the way users phrase them, not tidy textbook questions.
- **Coverage of the failure taxonomy** — cases for each known failure mode, plus clean
  cases that must stay clean.
- **A way to score each case** — expected answer, assertions, or a validated judge.
- **Frozen** — fixed before you measure a change; a set you edit mid-experiment voids the
  comparison.
- **Versioned and fingerprinted**, so "the same set" is checkable.
- Kept **separate** from anything used as prompt examples.

Small is fine to start (20–50 cases) if each case earns its place.

**In this project:** Week 6 has 25 cases, 5 per Week 5 failure mode. Week 10 reused 10 of them,
read straight from `Week-6/cases.jsonl` with its sha recorded on every run.

### Q2. How do you turn real failures into regression tests?

Take each real failure from error analysis and make it a permanent case with the correct
expected behaviour. Best practice is to **replay it verbatim** — the original input and, for RAG,
the original retrieved passages — so the test exercises exactly what failed, not a cleaned-up
version. Once fixed, it stays in the set so the failure cannot quietly return.

**In this project:** R01–R03 are read out of the Week 5 trace file on every load — the question
byte for byte, the passages pinned to the trace's own chunk ids in rank order — and loading stops
if the corpus fingerprint has moved since the trace was written.

### Q3. Why run assertion checks before using an LLM judge?

Anything a rule can check, a rule should check: it is **free, instant, deterministic and says
exactly which field failed**. Examples: the claim number echoes the input in the right format;
the date parses; the excess is a plain number; a denial cites an exclusion code that actually
exists; a citation id is in the retrieved set. Save the judge for what genuinely needs judgement.
Every criterion moved out of the judge makes the judge's single question sharper and its verdicts
easier to validate.

**In this project:** the first judge prompt checked 6 criteria on a 1–10 scale; 4 of them became
regex assertions (`assertions.py`) and the judge was cut to **one** PASS/FAIL criterion.

### Q4. How do you design an LLM-as-judge?

- **One criterion per judge**, written as a PASS/FAIL definition with explicit failure
  conditions.
- Give the judge **what it needs to decide** — here, the source wording and the notes, not just
  the answer.
- Ask for a **verdict plus a short reason**, in a fixed format your code can parse.
- Temperature 0; a **different or smaller model** than the one being judged where possible.
- One retry on an unparseable reply, then record it as unparsed — never drop it.
- **Validate it against human labels before trusting it** (Q7).

**In this project:** `judge_v2.txt` checks only "coverage position supported" against all six
endorsements, on `gpt-oss-20b` (the app runs `gpt-oss-120b`).

### Q5. What is G-Eval?

A recipe for LLM-as-judge scoring:
1. Give the model the task and the evaluation criteria.
2. Have it **generate the evaluation steps** itself (chain-of-thought).
3. Score the output by following those steps, in a form-filling format.
4. Instead of taking the single score token, use the **probabilities of each score token** to
   compute a probability-weighted score, giving finer and more stable scores than a bare 1–5.

It improves agreement with humans on open-ended qualities (coherence, relevance). It needs token
log-probabilities from the API, and it is still a judge that must be validated.

### Q6. Binary or 1–10 scoring for a judge?

Prefer **binary PASS/FAIL per criterion**:
- it forces a precise definition of "good enough";
- humans and judges agree more on binary decisions;
- the result is actionable: a failure has a reason, and pass rate is easy to track;
- 1–10 scales drift (what is a 6 vs a 7?) and judges bunch on a few values.

If you need nuance, use several binary criteria rather than one scale.

**In this project:** judge v0 used one 1–10 score over six criteria; v1 and v2 use one binary
criterion.

### Q7. How do you validate a judge against human labels?

1. Humans label a set of outputs **blind** to the judge, and the labels are committed **before**
   the judge runs.
2. Run the judge on the same outputs.
3. Measure **agreement** (share of identical verdicts) and **Cohen's kappa** (agreement corrected
   for chance — important when most cases pass).
4. Look at the **direction** of disagreements: judge PASS where the human said FAIL is the
   dangerous one.
5. Measure **run-to-run noise** by re-running the identical judge — a change smaller than the noise
   is not a change.
6. Improve the judge (e.g. add its own past mistakes as worked examples), re-measure, and report
   agreement **without** the example cases too.

**In this project:** v1 72.0% (kappa 0.44) → v2 84.0% (kappa 0.68), 87.0% with the two few-shot
cases held out; judge-PASS/label-FAIL fell from 4 to 1. Caveat recorded in the repo: these labels
were written by an AI model, not a human (see the Week 6 disclosure), so this is label-vs-judge
agreement, not human-vs-judge. Changing the judge model moved agreement more than editing the
prompt: the same v1 prompt scored 88.0% on a qwen model.

### Q8. What do RAGAS faithfulness and answer relevancy measure?

- **Faithfulness:** split the answer into individual claims; check each claim against the
  retrieved context; score = supported claims ÷ total claims. Catches hallucination on top of
  retrieval. Needs no reference answer.
- **Answer relevancy:** have an LLM generate several questions that the answer would be answering,
  embed them, and take the mean cosine similarity to the original question. Penalises answers
  that are off-topic or padded. It does **not** check correctness.

Both are LLM-based and should be spot-checked against human judgement.

### Q9. What do RAGAS context precision and context recall measure?

- **Context precision:** are the relevant chunks ranked near the **top** of the retrieved list?
  Each retrieved chunk is judged relevant or not, and precision@k is averaged over the positions
  of relevant chunks — like MRR's concern with ranking.
- **Context recall:** does the retrieved context contain everything needed? Split the
  **reference (ground-truth) answer** into claims and check what share can be attributed to the
  retrieved context. Needs a reference answer.

Together they diagnose retrieval (Week 4's R side): low recall means the information was never
fetched; low precision means it was fetched but buried.

### Q10. How do you report a before/after delta honestly?

- Same frozen eval set, same judge, same settings — only the one change differs.
- Report **per failure mode**, not only overall: one overall number can hide a mode that
  regressed.
- Report **per case**: which flipped PASS → FAIL as well as FAIL → PASS.
- Compare the delta with the **noise** (judge flips, model variance on a re-run).
- Check against the **prediction** you committed before the change.
- Put the **cost** (tokens, latency) next to the quality change.

**In this project:** Week 6 scored its own prediction honestly — "nothing already right gets
broken" was marked **wrong**, because C09 flipped PASS → FAIL.
