# Week 11 — Production: Observability, Cost & the Failure→Test Loop

Module 6 · Production · build week

Topics: what to log per request · traces & spans · LangSmith / Phoenix / OpenTelemetry · the support
drill · cost per query · prompt caching · semantic caching · model routing (LiteLLM) · fallbacks &
rate limits · the data flywheel · the 10× plan · fine-tuning (last resort)

---

### Q1. What should you log for every request?

Enough to **find it and replay it** months later:

- **When and who:** timestamp, user, input type, and a **trace id**.
- **Which version:** prompt version **and its hash** (sha), model name and settings.
- **What went in and what came out:** the input and output, **redacted on write**, plus the
  answer's key fields (position, grounds) as their own fields so you can search on them.
- **What it looked at:** the retrieved context ids.
- **Every step:** one span per model call, retrieval and tool call, each with latency, tokens and cost.
- **The provider's limits:** quota headers and every rate-limit (429) response.

If it isn't logged, it didn't happen. "Wrong answer yesterday" can only be found if yesterday's answer
was stored with its position, context and version.

**In this project:** one JSON line per request in `logs/<date>.jsonl`, written by `tracer.py`, with all of
the above. Claimant names, phones, emails, addresses and policy numbers are redacted before the line is
written, and a trace is refused if anything survives.

### Q2. What are traces and spans?

- A **trace** is one request from start to finish, with one id.
- A **span** is one step inside it: a model call, a retrieval, a tool call, start-up. Each span has a
  start, a duration and its own tokens and cost.

Spans turn "this request was slow and expensive" into "**this step** was slow and expensive". A single
total cannot tell you whether to fix retrieval, cut laps, or shorten the prompt.

**In this project:** `trc_a4a9f492d77c` has a setup span (MCP start-up 1.29 s), generation spans and a
retrieval span, each with latency, tokens and cost (`cost_by_stage.md`).

### Q3. What are LangSmith, Phoenix and OpenTelemetry?

- **OpenTelemetry (OTel):** an open, vendor-neutral **standard** for traces, spans and metrics. Your code
  emits spans once and any compatible backend can store them. There are GenAI conventions for LLM spans
  (model, tokens, and so on).
- **LangSmith:** LangChain's hosted platform for tracing LLM apps, running datasets and evals, and
  monitoring.
- **Arize Phoenix:** an open-source LLM observability tool. It collects traces over OpenTelemetry,
  shows them, and runs evals on them.

They all do what a hand-written tracer does, with a UI, storage and search. The choice matters less than
logging the right fields.

**In this project:** a hand-built JSON-lines tracer, no platform. The fields match what these tools record
(trace id, spans, tokens, cost, prompt version).

### Q4. What is "the support drill"?

A practice run of a real support situation: a colleague **plants one bad answer** in the logs and
describes it only as vaguely as a customer would, for example "yesterday it said a flood claim was
covered". You find it **from the logs alone** against a stopwatch, and report the **time-to-find** and
**which slice found it** (time, user, version, position, context ids).

Then you "wire the drill shut": add the log field or index that would have made the find instant, and do
it again to beat your time.

**In this project:** the drill was attempted but **not measured**. One person planted and searched, with no
squadmate and no stopwatch, so there is no time to report. It still showed something useful: the judge
sweep **missed** the planted answer (it passed the app's own mistake). The log signal that found both bad
answers exactly was "E-17 cited **without** the definitions chunk `#02` in the context ids".

### Q5. How do you measure cost per query?

Cost = input tokens × input price + output tokens × output price, **per span**, summed per request.
Then split the cost **by stage** (generation, retrieval, tools) to see where the money actually goes.
Tokens that retrieval and tools add to later prompts count against them, not against "generation".

**In this project:** for `trc_a4a9f492d77c`, **$0.000910 per query: generation 93.3%, retrieval 6.7%,
tools 0%**, with `gpt-oss-120b` at $0.15 / $0.60 per million input / output tokens.

### Q6. What are prompt caching and semantic caching?

- **Prompt caching (provider-side):** when many requests start with the **same long prefix** (system
  prompt, tool definitions, a long document), the provider keeps the processed prefix and bills it
  cheaper and faster the next time. To benefit, put the stable parts **first** and the changing parts
  last.
- **Semantic caching (your side):** store question → answer. When a new question **means the same** as a
  stored one (embedding similarity above a threshold), return the stored answer without calling the
  model.

The risk with semantic caching: two questions can look alike but differ in a detail that changes the
answer, such as a different loss date or a different policy. For claims, a cache key must include those
facts, or the cache will serve a wrong answer very fast.

**In this project:** no cache was built. Every lap of the agent re-sends the system prompt and the tool
definitions, so prompt caching is the obvious first saving.

### Q7. What is model routing (LiteLLM), and what are fallbacks?

- **Model routing:** send each request to the **cheapest model that can handle it**: easy questions to a
  small model, hard ones to a large one. The router can be a rule ("classification → small model") or a
  small classifier.
- **LiteLLM:** an open-source library and proxy that puts **one OpenAI-style interface** in front of many
  providers. It handles routing, retries, **fallbacks** (if model A errors or is rate-limited, try model
  B), budgets and cost tracking.
- **Fallbacks** keep the app answering during an outage. The catch: the fallback model must have passed
  **the same eval** first, or the fallback quietly lowers quality.

**In this project:** one model, no router. Rate limits are handled by waiting for the provider's
`retry-after` (`llm.retry_after`), and every 429 is classified (TPM, TPD, RPD) and recorded in the trace.

### Q8. What are fallbacks and rate limits in practice, and what are TPM, RPD and TPD?

Providers cap usage per key:

- **TPM:** tokens per minute.
- **RPM / RPD:** requests per minute / per day.
- **TPD:** tokens per day.

When a cap is hit, the provider returns **HTTP 429** with a wait time. Production code should retry after
the wait, queue work rather than drop it, and **record every 429**, because a hidden limit shows up later
as unexplained latency.

**In this project:** on the free Groq key, TPM was 8,000 and RPD 1,000 (from the response headers). The
**daily token cap of 200,000 does not appear in the headers**, only in a TPD 429. It was hit for real:
"used 198,945, requested 3,080". Evals and production shared one key, and the evals used about 92,871 of
those tokens.

### Q9. What is the data flywheel, and the failure→test loop?

Every **real production failure** becomes a **permanent eval case**, so it can never quietly come back:

1. Find the bad answer in the logs.
2. **Add an eval case for it first**, and watch it fail (RED).
3. Fix the prompt, retrieval or code.
4. Re-run the **whole suite**, not just that case (GREEN), so the fix doesn't break something else.
5. Ship behind a **canary** (a few users first), with a one-step **rollback**.

Over time, real failures feed the eval set, the eval set guards every change, and the app improves from
its own traffic. That's the flywheel.

**In this project:** the bad answer `trc_a4a9f492d77c` (a rental condo in another city, answered COVERED)
became eval case `P-trc_a4a9f492d77c`. **RED 8/11** on v1 → the first fix v2 got the position right but
broke the deductible field (**6/11**, kept on record) → **v3 GREEN 9/11**. The canary was user `adj-04`
for one day, and rollback is one environment variable.

### Q10. What is a 10× plan, and when is fine-tuning the answer?

**10× plan:** take today's measured traffic, multiply by ten, and compare every number with its limit:
tokens per day, tokens per minute, requests per day, cost and latency. Name **what breaks first**, with
the number behind it. Then rank the fixes and cost them.

**Fine-tuning** (training the model further on your own examples) is the **last resort**. Try it only
after prompting, retrieval, evals and routing are exhausted, and only for a stable task with plenty of
good examples, such as a fixed output style or cheaper classification. It doesn't keep facts up to date
(RAG does that), it costs data, time and re-evaluation, and it must be re-done when the base model
changes.

**In this project:** **the daily token cap breaks first.** At 10×, the app needs **1,060,740 tokens a day
against 200,000 (5.3× over)**, and it already breaks at 1.9× today's volume. Cost would be only
**$0.27 a day**. Money is not the limit; the quota is.
