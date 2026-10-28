# cost_10x.md - cost per claim triaged, and what breaks first in a hailstorm week

From 25 integrated triages (run `after`), `gpt-oss-120b` on Groq at $0.15 / $0.60 per 1M input / output tokens.

| per claim triaged | mean | p50 | max |
|---|---|---|---|
| cost | $0.00223 | $0.00212 | $0.00412 |
| tokens | 11,063 | 10,407 | 18,999 |
| model calls (laps) | 5.2 | 5 | 7 |
| active latency | 13.0 s | 12.3 s | 32.9 s (p99 = max at n=25) |
| wall latency incl. rate-limit waits | 3490.1 s | 3886.5 s | 7590.7 s |

Cost by stage, mean per claim: generation $0.00204 (91%), retrieval-carried tokens $0.00009 (4%), tool results $0.00010 (4%).

## A hailstorm week: 18,000 FNOLs

| | normal (1,800 a month) | hailstorm week | limit on this key | breaks? |
|---|---|---|---|---|
| claims per day | 60 | 2,571 | - | - |
| tokens per day | 663,785 | 28,447,920 | 200,000 TPD | **yes, 142x over - already 3.3x over at normal volume** |
| model calls per day | 310 | 13,269 | 1,000 RPD | yes, 13x over |
| tokens per minute (10-hour day) | 1,106 | 47,413 | 8,000 TPM | yes, 6x over |
| cost | $0.13 a day | $5.74 a day, $40.2 a week | - | no |

**First to break: the daily token cap.** 28,447,920 tokens a day against 200,000 - and it breaks before any hailstorm: normal volume alone needs 3.3x the cap. Cost is not the problem ($40.2 for the whole hailstorm week).

During these 25 runs the key met 200 rate-limit responses (TPM x15, TPD x185). TPM and RPD are Groq's own response headers; the daily token cap is not in the headers and shows only in a TPD 429 (Week 11 measured it at 200,000 on this key).

## The plan, ranked and costed

1. **Move off the free tier** (the binding constraint at every volume): pay-as-you-go on the same model; at $0.00223 a claim a hailstorm week is about $40.2. Re-measure TPM/RPD from the new headers before trusting it.
2. **Cut laps per claim** (5.2 now): fetch the claim, notes and in-force term in the first lap - every lap re-sends the system prompt and six tool definitions, so one lap fewer saves about 19% of tokens.
3. **Queue and prioritise** at catastrophe volume: triage is not real-time for an adjuster's first 20 minutes; a queue that drains under the token cap turns 429s into latency the adjuster does not see.
