# Week 6 — Task Set D — Insurance claims

Validate the claim-summary judge before trusting its number.

The app writes a claim summary from an adjuster's file notes. Its quality number
came from an LLM judge nobody had checked against a human. This week: move what a
regex can check out of the judge, hand-label 25 summaries blind, measure how often
the judge agrees, and move that number using the judge's own mistakes.

Numbers, the two disagreements and the scored prediction: [results.md](results.md).

## Setup

```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy ..\Week-4\.env.example .env      # then paste your Groq key into .env
.venv\Scripts\python index.py         # 48 chunks into Chroma
```

## The one command

```
.venv\Scripts\python eval.py
```

Summarises any case not yet summarised, runs the 4 assertions, runs every judge
version that is allowed to run, and prints pass rate **by mode** plus agreement
with the hand labels. Output is also saved to `runs/eval_output.txt`.

## The protocol, in the order git log shows it

| step | command | what it proves |
|---|---|---|
| 1 | commit the app and `judge_v0.txt` | the judge as first written: one 1-10 score over 6 criteria |
| 2 | commit `assertions.py`, `judge_v1.txt` | 4 criteria moved to regex and deleted from the judge; 1 left |
| 3 | `python summarise.py`, commit `summaries.jsonl` | the 25 summaries are frozen before anyone labels them |
| 4 | `python label.py`, commit `labels_25.json` | 25 blind labels exist **before** any judge call |
| 5 | `python judge.py v1`, commit `runs/judge_v1.jsonl` | the run file records the labels' commit hash and time next to its own start time |
| 6 | write and commit `prediction.txt` | one sentence on what the iteration will fix, before it exists |
| 7 | `python make_v2.py <id> <id>`, `python judge.py v2`, commit | v2 = v1 + two of v1's own disagreements as examples |

The ordering is enforced in code, not just promised:

- `label.py` refuses to start if any judge run exists.
- `judge.py` makes no call unless `labels_25.json` is complete, committed with no
  edits on top, and taken against the current `summaries.jsonl` (sha match).
- `judge.py v2` and `make_v2.py` refuse unless `prediction.txt` is committed.
- `make_v2.py` refuses any case that v1 did not actually get wrong.
- `agreement.py` flags it if the labels changed between the v1 and v2 runs.

## Assertions vs judged criteria

**4 deterministic assertions, 1 judged criterion.** `judge_v0.txt` had 6 criteria.

| was judge_v0 criterion | now |
|---|---|
| 1. claim number echoed in CLM-YYYY-NNNNN form | `assertions.claim_number` |
| 2. date of loss present and parseable | `assertions.date_of_loss` |
| 3. excess or deductible is a number | `assertions.excess_numeric` |
| 4. a denial cites its exclusion code | `assertions.grounds_on_denial` |
| 5. coverage position supported by the wording | **the judge's only criterion** — `criterion.txt` |
| 6. clear and concise | dropped — no claim decision turns on it |

```
git diff f1bf868 -- judge_v0.txt judge_v1.txt     # or: git diff --no-index judge_v0.txt judge_v1.txt
```

## Files

| file | role |
|---|---|
| `data/`, `chunks.jsonl`, `ingest.py`, `index.py`, `search.py`, `hybrid.py` | the Week 5 pipeline, carried over untouched |
| `summarise.py`, `prompts.py` | the app: notes in, fixed-line claim summary out |
| `cases.jsonl`, `cases.py` | 22 written cases + 3 regression cases read verbatim out of `../Week-5/traces/traces.jsonl` |
| `summaries.jsonl` | the frozen summaries every label and verdict refers to |
| `assertions.py` | the 4 checks that left the judge |
| `criterion.txt` | the one binary question — the labeller and the judge see the same words |
| `judge_v0.txt`, `judge_v1.txt`, `judge_v2.txt` | the judge prompt before the split, after it, and after the iteration |
| `label.py` → `labels_25.json` | blind hand labels |
| `judge.py` → `runs/judge_v*.jsonl` | judge runs, locked behind the labels |
| `prediction.txt` | written and committed before `judge_v2.txt` existed |
| `make_v2.py` | builds v2 from two v1 disagreements |
| `agreement.py` → `agreement.json` | agreement before -> after, and with the few-shot cases held out |
| `eval.py` | the one command |

## Models

Summariser `openai/gpt-oss-120b`, judge `qwen/qwen3.8-27b`, both on Groq at
temperature 0. They are from different model families on purpose, so the judge is
not grading its own model's writing.
