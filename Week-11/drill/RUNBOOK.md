# Week 11 drill — runbook

Two people: a **squadmate** who plants and times, and the **finder** who searches.
All commands run from `Week-11/` with `.venv\Scripts\python`.

## The short version

Open a terminal and go to the folder first: `cd C:\Projects\AI-Training\Week-11`

**Squadmate (finder looks away):**

```
.venv\Scripts\python plant.py --trap T13 --user adj-03 --tries 6 --by "Squadmate Name"
```

Any user `adj-01`..`adj-05` is fine. It may take several tries; wait for **PLANTED**. Then clear
the screen (`cls`), say *"an adjuster says it told a claimant something was covered when the
policy excludes it, sometime yesterday"*, and start a stopwatch.

**Finder:**

```
.venv\Scripts\python sweep.py
```

It lists every answer that said COVERED and marks with `!!` the ones the judge says are wrong.
`trc_a4a9f492d77c` is the old one, already fixed. The other `!!` line is the planted one —
check it with `.venv\Scripts\python find.py --show trc_...` and say "found trc_...".
The squadmate stops the clock and opens `drill\plant_key.json` to confirm the id.

The full version, with every search option, follows.

The finder must not open `drill/trap_pool.jsonl` or `drill/plant_key.json` before
the drill is over.

## 1. Squadmate: plant (finder out of the room)

```
.venv\Scripts\python plant.py --list
.venv\Scripts\python plant.py --trap T? --user adj-0? --tries 5 --by "Your Name"
```

- Choose any trap and any adjuster `adj-01`..`adj-05`. Add `--at HH:MM` to choose the
  time, or leave it out for a random time inside the day's traffic.
- Or write your own claim: `--notes "CLM-YYYY-NNNNN. DOL YYYY-MM-DD. ... Excess N."`
  (add `--exclusion E-xx` if one specific code should have applied).
- It runs the real app, up to `--tries` times. Only a run where the app really answers
  COVERED is planted; if none does, nothing is planted. Most traps fail to fool the app —
  it handles a clear single exclusion well — so expect to try more than one.
- When it prints **PLANTED**, close the terminal, call the finder in, and say only:

  > "An adjuster says it told a claimant something was covered when the policy
  > excludes it, sometime on <the day it printed>."

- Start a stopwatch.

## 2. Finder: find it from the logs alone

The tool is `find.py` (read-only, no model calls):

| command | what it gives |
|---|---|
| `find.py` | the day at a glance: counts by user, input type, prompt version, position, hour |
| `find.py --by user` (or `input_type`, `prompt_version`, `position`, `hour`) | one slice |
| `find.py --position COVERED` | filter on the output |
| `find.py --user adj-03`, `--input-type file_note`, `--version claims-agent-v1`, `--between 14:00 15:00` | filter on who / what / which prompt / when |
| `find.py --text vacant` | free text over the redacted input and output |
| `find.py --cost-outliers` | the cheapest and dearest requests |
| `find.py --show trc_...` | one full trace: every span, the context ids, the answer |

Filters combine. Say "found" when you can name the trace id **and** the exclusion it
ignored. The squadmate stops the clock.

## 3. Afterwards

- Squadmate opens `drill/plant_key.json` and confirms the trace id.
- Record: the time (mm:ss), the slice or filter that found it, the squadmate's name, and
  — if it took over 5 minutes — the log field whose absence cost the time.
- Then the loop: `make_eval.py <trace_id> --must-cite E-xx --why "..."`, `suite.py red`,
  fix, `suite.py green`.
