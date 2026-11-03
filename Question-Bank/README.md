# Question Bank — Weeks 1 to 12

10 questions with answers for each of the twelve weeks of the AI Engineering League syllabus —
120 in all. Each week's questions follow that week's "topics covered" list. From Week 3 on, most
answers end with an **In this project** line giving the measured result from this repository, so an
answer can be backed with a real number.

| week | module | topic | file |
|---|---|---|---|
| 1 | Foundations | How a language model actually works | [Week-01.md](Week-01.md) |
| 2 | Foundations | Prompting, structured output and tool calling | [Week-02.md](Week-02.md) |
| 3 | Retrieval & RAG | Retrieval-augmented generation, from parts | [Week-03.md](Week-03.md) |
| 4 | Retrieval & RAG | Debugging retrieval: hybrid, reranking, failure separation | [Week-04.md](Week-04.md) |
| 5 | Evals & Error Analysis | Error analysis: reading traces | [Week-05.md](Week-05.md) |
| 6 | Evals & Error Analysis | Evals: measuring whether a change helped | [Week-06.md](Week-06.md) |
| 7 | Agents | Agent loops, and when not to use them | [Week-07.md](Week-07.md) |
| 8 | Agents | Agent failure modes and trajectory evals | [Week-08.md](Week-08.md) |
| 9 | MCP, Multi-agent & A2A | MCP: the standard way agents reach tools and data | [Week-09.md](Week-09.md) |
| 10 | MCP, Multi-agent & A2A | Multi-agent and A2A, with evidence | [Week-10.md](Week-10.md) |
| 11 | Production | Observability, cost and the failure→test loop | [Week-11.md](Week-11.md) |
| 12 | Production | Capstone: ship it and defend it | [Week-12.md](Week-12.md) |

## Key numbers from this repository

| week | result |
|---|---|
| 3 | chunking: naive 7/8 vs structure-aware 8/8 hit-in-top-5 |
| 4 | reranker: hit-rate@3 9/12 → 8/12 at 4.5× latency — not shipped |
| 5 | 20 seeded traces: 7 failed, 5 modes, all claim-affecting |
| 6 | judge agreement 72% → 84%, kappa 0.44 → 0.68 (labels AI-written, disclosed in Week 6) |
| 7 | agent vs workflow: 8/10 each; 54,785 vs 23,319 tokens — workflow shipped |
| 8 | outcome 80% vs trajectory 40%; one fix: top mode 5 → 2, gap 40 → 30 points |
| 9 | second MCP server by config only: 0 agent lines changed, tools 2 → 4 |
| 10 | single agent 8/10 vs squad 4/10 at 1.7× tokens — squad killed |
| 11 | failure→test loop: RED 8/11 → 6/11 (first fix) → GREEN 9/11; $0.000910 per query; at 10× the daily token cap breaks first (5.3× over) |
| 12 | 25-case suite 19/25 (20/25 with the gate re-run); wrong-edition citations 1/7 → 0/7; judge agreement 84%; $0.0022 per claim |

## Topics this repository has not built yet

Covered in the answers, but with no experiment behind them: query rewriting, HyDE and MMR (Week 4);
RAGAS and G-Eval (Week 6); agent memory and mem0 (Week 7); prompt injection, direct and indirect
(Week 8); MCP resources, prompts and remote HTTP auth (Week 9); A2A and AgentCard (Week 10); LangSmith,
Phoenix and OpenTelemetry, prompt and semantic caching, model routing with LiteLLM, and fine-tuning (Week 11).
