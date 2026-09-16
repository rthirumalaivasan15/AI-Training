# Week 6 — Task Set D — Insurance claims

Validate the claim-summary judge before trusting its number.

**agreement_before = 72.0% (18/25) → agreement_after = 84.0% (21/25).** On the 23
cases not used as examples: **87.0% (20/23)**. Kappa 0.44 → 0.68.

**4 deterministic assertions, 1 judged criterion.** The judge as first written had 6.

---

## 0. Disclosure — read this before the numbers

**The 25 labels were not written by a human.** The task asks for hand labels; the
human labelling step was not done. At the user's request an AI model wrote
`labels_25.json`, `prediction.txt`, and the who-was-right verdicts in section 5 of
this file. So every figure here is **AI label vs AI judge**, and none of it
validates the judge against a person.

What is still true, and checkable:

- The labels were committed (`1e14e43`, 2026-09-15 23:51:08 +05:30) **before any
  judge ran**. The first judge call was 2026-09-16 06:48:15 UTC, and every run
  file records the labels' commit hash and time beside its own start time.
- The labelling model had seen no judge output of any kind — none existed.
- The labelling model had written the 25 cases, so it knew which failure mode each
  case was built to exercise. A human labeller would not have that.
- `label.py` is the blind tool a human labeller would use. It was not used here.

---

## 1. The eval set

25 cases, 5 per Week-5 taxonomy mode, in `cases.jsonl` plus regressions built at
load time by `cases.py`.

| mode (from Week-5/taxonomy.md) | cases |
|---|---|
| 1 — answering clause exists but was not fetched | C01–C04, **R01** |
| 2 — consequence attached to a clause that states none | C05–C08, **R02** |
| 3 — answered from the wrong endorsement | C09–C13 |
| 4 — exception applied without its definition | C14–C17, **R03** |
| 5 — refused on the retrieval score alone | C18–C22 |

**3 regression cases replayed verbatim from real failed Week 5 traces.** They are
not copied into `cases.jsonl`: `cases.py` reads them out of
`../Week-5/traces/traces.jsonl` on every load, takes the question byte for byte and
pins the passages to the trace's own retrieved chunk ids in recorded rank order,
and refuses to load at all if the corpus fingerprint has moved.

| case | trace | the Week 5 failure |
|---|---|---|
| R01 | `trc_99613f4f2842` | said NOT_IN_DOCUMENTS on a home-business liability claim; E-31 was never fetched |
| R02 | `trc_4ab44f82de51` | invented a right to deny from a clause that states no consequence |
| R03 | `trc_df4ab8c54cd4` | paid a burst-pipe loss without testing the 14-day definition |

---

## 2. Assertions vs judged criteria

The judge as first written (`judge_v0.txt`) put six things in one 1-10 score. Four
never needed a model, and a fifth was not claim-affecting:

| judge_v0 criterion | now | why |
|---|---|---|
| 1. claim number echoed, CLM-YYYY-NNNNN | `assertions.claim_number` | a regex, and it never has an off day |
| 2. date of loss present and parseable | `assertions.date_of_loss` | same |
| 3. excess or deductible is a number | `assertions.excess_numeric` | same |
| 4. a denial cites its exclusion code | `assertions.grounds_on_denial` | same |
| 5. coverage position supported by the wording | **the judge's only criterion** | genuinely needs reading |
| 6. clear and concise | dropped | no claim decision turns on it |

**Count: 4 assertions, 1 judged criterion.** The four are deleted from the judge
prompt, and `judge_v1.txt` says so in as many words, so the judge is not quietly
still marking them. `judge.py` refuses to run a prompt that does not contain
`criterion.txt` word for word, so the judge and the labeller cannot drift apart.

The assertions caught things a model would have been paid to notice:

- **3 of 25 summaries carry no claim number, date or excess at all** (C03, C18,
  C19). All three are score-floor refusals: the 0.35 dense floor fires, the model
  is never called, and nothing from the notes reaches the summary.
- **C14 dropped the date of loss** — the notes say `DOL 2024-03-28 (date
  discovered)` and the summary returned NOT STATED.
- **grounds_on_denial passed 25/25.** Every denial cited an exclusion code or a
  named clause. Worth saying plainly: this assertion found nothing. It is cheap
  insurance, not a discovery.

A quieter one: the summariser writes exclusion codes with a non-breaking hyphen
(`E‑17`, U+2011). Codes are matched with that normalised, but `claim_number` stays
strict, because `CLM‑2024‑20011` with the wrong hyphen is not findable in a claims
system.

---

## 3. The one command

```
.venv\Scripts\python eval.py
```

```
WEEK 6 EVAL - 25 cases, 3 of them regression cases replayed from Week 5 traces
checks: 4 deterministic assertions (claim_number, date_of_loss, excess_numeric, grounds_on_denial) | 1 judged criterion
summaries.jsonl sha 0254f01250da

PASS RATE BY MODE   (PASS = all assertions + judge v2)
  mode                             n  assertions    judge v1      judge v2      human         PASS
  1 silent-but-not-fetched         5  4/5  80%      4/5  80%      3/5  60%      3/5  60%      3/5  60%
  2 invented-consequence           5  5/5 100%      3/5  60%      2/5  40%      2/5  40%      2/5  40%
  3 wrong-endorsement              5  5/5 100%      3/5  60%      2/5  40%      3/5  60%      2/5  40%
  4 exception-skips-definition     5  4/5  80%      2/5  40%      2/5  40%      2/5  40%      2/5  40%
  5 score-floor-refusal            5  3/5  60%      2/5  40%      2/5  40%      3/5  60%      2/5  40%
  ----------------------------------------------------------------------------------------------------
  ALL                             25  21/25  84%    14/25  56%    11/25  44%    13/25  52%    11/25  44%
```

**Why one overall number would have lied.** Assertions alone read 84%, and that is
the number an eval that only checked format would have printed. The labels say
**13 of 25 summaries take a coverage position the wording does not support** — the
app is at 52%, not 84%. And the modes do not move together: mode 2 (invented
consequence) and mode 4 (exception without its definition) sit at 40% on the
labels while the assertions score them 100% and 80%. Those two modes are exactly
where a regex cannot help, because the format is perfect and the reasoning is wrong.

---

## 4. Agreement, before and after

```
judge v1  18/25 =  72.0%   kappa 0.44   judge-PASS/human-FAIL 4   judge-FAIL/human-PASS 3
judge v2  21/25 =  84.0%   kappa 0.68   judge-PASS/human-FAIL 1   judge-FAIL/human-PASS 3
v2 held   20/23 =  87.0%   kappa 0.74   (without the few-shot cases C12, C22)
fixed by v2: C08, C10, C12, R01      broken by v2: C09
```

**agreement_before = 72.0 → agreement_after = 84.0.**

The iteration used two of v1's **own** disagreements as worked examples
(`make_v2.py C12 C22`), one in each direction:

- **C12** — v1 said PASS on a summary that denied under E-22 of ed. 01-24 when the
  dec page named ed. 05-23, an edition not in the documents.
- **C22** — v1 said FAIL on a summary whose UNDETERMINED position the label called
  correct.

`make_v2.py` refuses any case v1 did not actually get wrong, and refuses to run at
all until `prediction.txt` is committed. The v1 → v2 diff is exactly those two
examples and nothing else (`git diff judge_v1.txt judge_v2.txt`).

**The held-out number is the honest one.** C12 and C22 sit in v2's prompt with
their answers, so counting them flatters v2. Excluding them: 20/23 = 87.0%.

**The dangerous direction improved most.** Judge-PASS-where-the-label-said-FAIL —
a wrong coverage position waved through — went from **4 to 1**. The other
direction (judge fails a summary the label passed) did not move: 3 to 3. For a
router that sends "PASS" summaries onward unread, that is the trade worth having.

### The judge model changed mid-task, and that is the biggest number here

v1 was first run twice on `qwen/qwen3.8-27b`, which scored **88.0% (22/25), kappa
0.76** against the same labels, then ran out of free-tier tokens part way through
v2. Rather than compare v1 on one model with v2 on another, both versions were
re-run on `openai/gpt-oss-20b`, and those runs are the 72 → 84 figures above. The
qwen runs are kept (`runs/judge_v1_qwen.jsonl`, `runs/judge_v1_qwen_repeat.jsonl`).

So on the identical prompt and the identical 25 summaries:

| judge model | agreement with the labels |
|---|---|
| qwen/qwen3.8-27b (v1 prompt) | **88.0%** |
| openai/gpt-oss-20b (v1 prompt) | **72.0%** |
| openai/gpt-oss-20b (v2 prompt) | **84.0%** |

**Changing the judge model moved agreement by 16 points. Iterating the prompt moved
it by 12, and did not recover the model choice.** Anyone about to spend a week on
judge prompt wording should read that line first.

### Run-to-run noise

`judge.py v1 repeat` re-runs the identical prompt into its own file, because Week 5
found this provider does not return token-identical output at temperature 0. On
qwen: **0 of 25 verdicts flipped** across two identical runs, 22/25 both times. So
that judge's verdicts were stable and a 12-point move is not noise. **The same
check on gpt-oss-20b did not finish** — the token budget ran out — so the noise
floor for the model the headline numbers come from is measured at zero on one
model and unmeasured on the other. That is a real hole, and it is cheap to close
by re-running `judge.py v1 repeat` tomorrow.

---

## 5. Two disagreements, read, with a verdict on who was right

Verdicts written by the AI model that wrote the labels (see section 0).

### C09 — the judge was right and the label was wrong

Notes: loss **19 February 2024**, homeowners policy with **HO-0304 ed. 03-24**,
burst supply line about 3 days before discovery. The summary said COVERED via the
E-17 sudden-and-accidental exception. The label said PASS. **v2 said FAIL**:

> The endorsement HO-0304 ed. 03-24 is not effective until 2024-03-01, but the loss
> occurred 2024-02-19.

HO-0304 Clause 2 says the endorsement controls "for losses occurring on or after
the effective date shown above", and the header gives `EFFECTIVE DATE: 2024-03-01`.
A 19 February loss is before it. **The judge caught a date the labeller missed**,
in a case written to test something else entirely. This is the one v2 "broke", and
it is the clearest evidence in the whole exercise that the judge is worth having:
scored against the label it counts as a regression, and it is actually a catch.

### C22 — the judge was right, the label was too generous

Notes: a leak behind a shower wall that ran about 10 days, with mould in the wall
cavity, and the insured wanting mould remediation paid. The summary returned
UNDETERMINED, saying the endorsement text "does not include the specific exclusion
or coverage language needed". The label said PASS, on the ground that no
endorsement mentions mould. **v2 said FAIL**, because HO-0304 is in front of it and
a 10-day leak is inside the 14-day definition, so the water-damage half is
answerable. Both are right about their half, but the summary's stated reason — that
the wording was not available — is false, and the criterion fails a summary that
says the wording is silent when it is not. **The label should have been FAIL.**

### C16 — the label was right and the judge is wrong (and v2 did not fix it)

Gross receipts of 4,200 are under the 5,000 threshold in HO-0509 Clause 1(a), so it
is not a home business and E-31 does not apply. The summary said UNDETERMINED
because the liability grant itself lives in the base HO-3 wording, which is not in
the corpus. That is right: the endorsements settle the exclusion, not the coverage.
Both v1 and v2 fail it. **This is a judge error that survived the iteration.**

### C15 — neither, and the case is at fault

The summary denies under E-31 because the day care charges a fee. Both judges say
PASS; the label says FAIL because the home-business definition was never tested.
Reading the notes again: the day care was notified in July 2024 and the loss was
16 September, so 3 children at 150 a week is roughly 4,500–5,850 depending on a
start date the notes never give. **The case is under-specified**, which is a defect
in the eval set rather than in the summary or the judge, and it is mine.

---

## 6. The prediction, scored honestly

`prediction.txt`, committed `e444fb3` before `judge_v2.txt` existed. In one line:
adding C12 and C22 as worked examples would fix the two mistakes they stand for —
accepting a wrong-edition summary, and failing a correct UNDETERMINED — and lift
agreement from 88% to about 96% with nothing already right getting broken.

| claim | outcome |
|---|---|
| C12 (edition) fixed | **right** — v1 PASS → v2 FAIL, matching the label |
| C22 (correct UNDETERMINED) fixed | **wrong** — v2 still fails C22 |
| starting point 88% | **wrong** — the judge model had to change; the real baseline was 72% |
| ~96% after | **wrong** — 84%, or 87% held out |
| nothing already right gets broken | **wrong** — C09 flipped PASS → FAIL |
| named risk: it becomes readier to fail summaries generally, C10/C13/C16/C20 at risk | **half right** — C10 moved the other way (fixed), C13 and C20 held, C16 stayed wrong; but the prompt did make the judge stricter, and C09 is exactly that spillover — an effective-date objection nobody asked for |

**Four of six claims wrong.** The one that stings is "nothing already right gets
broken": the case it broke, C09, is the case where the judge turned out to be
right and my label wrong. So the prediction was wrong about the direction of the
error, and the scoring of it was wrong too until the disagreement was actually
read. The lesson is the one the task sheet is pointing at — the number moved for
reasons other than the one predicted, and only reading the disagreements showed it.

---

## 7. Blind protocol: the ordering, and how it is enforced

Not promised in prose — the code refuses.

- `label.py` will not start if any judge run exists.
- `judge.py` makes no model call unless `labels_25.json` is complete, committed,
  clean, and taken against the current `summaries.jsonl` (sha `0254f01250da`).
- `judge.py v2` and `make_v2.py` refuse until `prediction.txt` is committed.
- `make_v2.py` refuses a case v1 did not get wrong.
- `agreement.py` flags it if the labels commit differs between two runs, so
  relabelling after seeing a verdict cannot pass unnoticed.

```
1e14e43  2026-09-15 23:51:08 +0530  25 labels, committed before any judge run
6208ccc  2026-09-16 11:19:48 +0530  judge v1 run (qwen)
e444fb3  2026-09-16 11:20:46 +0530  prediction, before judge_v2.txt existed
857bf04  2026-09-16 11:21:33 +0530  judge_v2 built from C12 and C22
4be32fc  2026-09-16 11:33:31 +0530  judge v1 run a second time (qwen), for the noise check
923f3c1  2026-09-16 12:18:12 +0530  qwen runs kept under their own names, judge model changed
839a4c6  2026-09-16 13:19:51 +0530  judge v1 and v2 runs on gpt-oss-20b
```

Every run file also carries `labels_commit` and `labels_committed_at` next to its
own `started_at`, so the ordering survives outside git as well.

---

## 8. What went wrong while doing this

1. **A run lost 22 paid-for verdicts.** The first v2 attempt wrote its file only at
   the end, hit the rate limit on case 23 of 25, and threw everything away. Runs now
   append each verdict as it arrives and resume where they stopped (`0f3acec`).
2. **Two runs at once exhausted the quota.** v2 was started alongside the repeat
   run to save wall-clock time, and between them they burned the qwen budget — which
   is what forced the judge model change in section 4.
3. **An open `label.py` session overwrote the committed labels** with a single
   entry whose reason was the letter `q`. Restored from git. The lock stopped the
   judge from running against the damaged file, which is the lock doing its job.
4. **One qwen reply arrived with no readable verdict** (R02) and was counted as a
   disagreement rather than guessed at from its prose. Under gpt-oss-20b there were
   no unparsed replies.

---

## 9. Caveats

1. **The labels are not human.** Section 0. This is the caveat that swallows the
   others: the headline is an agreement between two models.
2. **25 cases.** One case moves agreement by 4 points. The 72 → 84 move is three
   cases.
3. **The labeller wrote the cases**, so it knew what each was built to test.
4. **The noise floor is measured on the wrong model** — 0/25 flips on qwen,
   unmeasured on gpt-oss-20b.
5. **C15 is under-specified** and should be rewritten or dropped before the set is
   used again.
6. **The summariser is the shipped Week 5 pipeline**, floor and all, so 3 of 25
   summaries are score-floor refusals that never reached the model.
