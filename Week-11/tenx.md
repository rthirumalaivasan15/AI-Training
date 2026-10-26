# tenx.md - what breaks first at 10x

**Rate limit breaks first - the daily token cap: 10x today's traffic needs 1,060,740 tokens a day against Groq's 200,000 tokens-per-day cap on openai/gpt-oss-120b (5.3x over; it breaks at 1.9x today's volume), while cost would be only $0.27 a day.**

| | today (2026-10-26) | at 10x | limit | breaks? |
|---|---|---|---|---|
| requests | 24 in 9 min | 240 | - | - |
| tokens per day | 106,074 | 1,060,740 | 200,000 TPD | **yes, 5.3x over - first, at 1.9x** |
| tokens per minute (at today's arrival rate) | 12,179 | 121,785 | 8,000 TPM | yes, 15.2x over - if it arrives as fast as today |
| model calls per day | 55 | 550 | 1,000 RPD | no (55% of cap) |
| cost per day | $0.0271 | $0.2712 | - | no |
| latency p50 / p99 (wall) | 18.1 s / 83.7 s | grows with the TPM queue | - | follows the rate limit |

Today already hit the TPM cap: **49 rate-limit responses (TPM x49), 409 s of waiting** across 24 requests; active time p50 / p99 was 5.2 s / 12.7 s, wall time 18.1 s / 83.7 s - the gap is the queue.
At 4,420 tokens per request, the 8,000 TPM cap sustains 1.8 requests a minute; 10x today's rate is 27.6 a minute.
The daily cap binds however the traffic arrives: spread evenly over an 8-hour shift, 10x would be only 2,210 tokens/min (under TPM), but the day's total is the same 1,060,740 tokens. It was hit for real on 2026-10-26T18:03: 429 TPD: limit 200,000, used 198,945, requested 3,080 - after the day's traffic plus trap pre-tests and eval-suite runs on the same key; the remaining suite cases then waited ~876 s each for the budget to refill (`runs/quota_probe.json`). Evals and production share one key: tests and suite runs used about 92,871 of those 198,945 tokens, so the cap was reached at only ~1x production traffic.
The GREEN suite run that followed met **29 TPD 429s and 3.9 hours of waiting** over the 6 cases it logged (`runs/suite_green.jsonl`) - 11 eval cases took most of an evening at ~1x.
TPM and RPD come from Groq's own response headers (`x-ratelimit-limit-tokens`, `x-ratelimit-limit-requests`) recorded in every trace; the daily token cap is not in the headers and appears only in a TPD 429; every 429 is classified by `llm.rate_limit_hit`.
