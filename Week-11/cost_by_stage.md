# cost_by_stage.md - trc_a4a9f492d77c

Request: CLM-2024-20035, adj-04, file_note, prompt `claims-agent-v1` (sha `5783e86864c0`), model `openai/gpt-oss-120b`, at 2026-10-26T14:32:45.344+05:30.

| stage | prompt tokens | completion tokens | cost | share of cost | latency |
|---|---|---|---|---|---|
| retrieval | 407 | 0 | $0.000061 | 6.7% | 0.25 s |
| generation | 2,303 | 839 | $0.000849 | 93.3% | 2.56 s |
| tools | 0 | 0 | $0.000000 | 0.0% | 0.00 s |
| **total** | 2,710 | 839 | **$0.000910** | 100% | 4.25 s active (4.25 s wall, 0.0 s rate-limit wait, 1.29 s MCP start-up) |

Cost per query: **$0.000910**. Prices from `llm.py`: $0.15 / $0.60 per 1M input / output tokens.

## Where the stage numbers come from - every span

| span | kind | name | latency | prompt in | completion out | cost | carried in prompt (instructions / history / retrieval / tools) | context ids |
|---|---|---|---|---|---|---|---|---|
| 1 | setup | start MCP servers: policy-docs | 1292 ms | - | - | $0.000000 | - | - |
| 2 | generation | model call 1 | 667 ms | 1105 | 167 | $0.000266 | 1105 / 0 / 0 / 0 | - |
| 3 | retrieval | search_policy | 247 ms | - | - | $0.000000 | - | HO-0304_03-24#05, HO-0304_03-24#04, HO-0304_03-24#03, HO-0304_03-24#00 |
| 4 | generation | model call 2 | 1890 ms | 1605 | 672 | $0.000644 | 1123 / 75 / 407 / 0 | - |

## The same split over the whole day (24 requests), for comparison

| stage | mean cost per query | share |
|---|---|---|
| retrieval | $0.000111 | 9.8% |
| generation | $0.001019 | 90.2% |
| tools | $0.000000 | 0.0% |
| total | $0.001130 | 100% |

**Tool definitions ride inside the generation stage.** Every model call re-sends the tool list: `search_policy` 448 tokens, `compute_payout` 292 tokens. That is 740 tokens per call, 292 per call for `compute_payout` alone - which was called **0 times** in the day's 55 model calls (the Week 6 summary has no payout field). Its definition cost 16,060 input tokens over the day for nothing: the first saving to make, and only visible once cost is attributed.

Retrieval and tools are free to run here (local embeddings, local vector store, Python arithmetic); their cost is the tokens their results add to every later model call, which is why they are attributed from the prompt. Split method: o200k_base token counts per message, scaled to Groq's reported prompt_tokens for that call.
