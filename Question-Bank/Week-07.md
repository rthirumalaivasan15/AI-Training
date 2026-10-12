# Week 7 — Agent Loops, and When Not to Use Them

Module 4 · Agents · build week

Topics: the agent loop · ReAct · tool design · stop conditions and budgets · workflows vs
agents · agent vs workflow race · agent memory (short and long term) · summarisation and vector
memory · mem0 · LangChain / LangGraph

---

### Q1. What is an agent loop?

A loop in which the model decides the next step:

```
messages = [system, task]
repeat:
    reply = model(messages, tools)
    if reply has tool calls: run them, append the results, continue
    else: reply is the final answer -> stop
```

Plan → act → observe → repeat, until the model answers or a limit stops it. The defining feature
is that **the path depends on what each step finds** — the model chooses the next tool from the
last result. Everything else (memory, planning, sub-agents) is built on this loop. Writing it by
hand (about 50 lines) means it is never magic and you can debug any framework's version.

**In this project:** `agent.py` (Weeks 7–9) is this loop, logging every lap's tokens, cost, time
and tool calls.

### Q2. What is ReAct?

**Reason + Act** (Yao et al., 2022): the model interleaves a **Thought** (reasoning about what
to do), an **Action** (a tool call), and an **Observation** (the tool result), repeating until it
can answer. Reasoning lets it plan and adjust; acting lets it fetch facts instead of guessing.
Modern native tool calling is ReAct built into the API: the model's reasoning, then a structured
tool call, then your tool result as the observation.

### Q3. What makes good tool design for an agent?

- **One clear job per tool**, and no overlap — two tools that could both answer a question make
  the agent thrash between them.
- A description that says **what it returns and what it does not** ("returns claim facts only —
  never endorsement wording").
- A tight **argument schema**: enums, patterns, required fields, examples.
- **Errors the model can act on**: say what was wrong and how to fix it.
- **Deterministic work in code**: arithmetic, lookups and validation belong in tools, not in the
  model's head.
- **Least privilege**: read-only where possible.

**In this project:** Week 7's third tool, `compute_payout`, is arithmetic only, with a
`claim_status` enum of covered/denied/undetermined, and deliberately no overlap with
`get_claim` or `search_policy`.

### Q4. How do you stop an agent safely?

Check **budgets before every lap**, and push them into each call where possible:
- **max iterations** (laps);
- **max tokens**, summed over every lap;
- **max cost**;
- **max wall-clock time** — passed down as the request timeout.

When a budget fires, stop **cleanly**: log which budget fired and by how much, and return a
well-formed "could not decide — refer to a human" answer instead of crashing or returning
nothing. Without budgets, a confused agent loops until your bill stops it.

**In this project:** `runs/budget_termination.log` — on CLM-2024-10006 with a 3,000-token budget,
`max_tokens` fired at **4,138 used** and the agent returned a clean UNDETERMINED hand-off. The
overshoot is the last lap's prompt, which no completion cap can limit.

### Q5. Workflow or agent — how do you decide?

- **Workflow** (fixed sequence in code) when you know the steps in advance. It is faster, cheaper,
  easier to test and fails predictably.
- **Agent** when the path genuinely **depends on the input** — the next step can't be known
  until you see the last result.

Default to the workflow and make the agent earn its place with evidence. The test: does the agent's
path actually vary across inputs? If it always takes the same steps, you are paying for freedom it
never uses.

### Q6. How do you run a fair agent vs workflow race, and what did it show here?

Same cases, same model and settings, same tools, same output contract, same grader — only the
control flow differs. Report four numbers for both: **pass rate, latency (p50 at least), total
tokens, cost per task**. Count tokens over **every** lap, not the last call. Keep rate-limit waits
out of latency, since they measure your quota, not the system.

**In this project:** 10 claims, `gpt-oss-120b`: both **8/10**; workflow p50 **3.09 s vs 4.74 s**,
**23,319 vs 54,785** tokens, **$0.000753 vs $0.001209** per claim. The agent **never searched a
second time** on any claim — the path did not vary by input — so the workflow shipped.

### Q7. What are short-term and long-term memory for an agent?

- **Short-term (working) memory:** the conversation and tool results of the current task — the
  message list re-sent on each lap. Bounded by the context window and paid for on every call.
- **Long-term memory:** facts kept across tasks or sessions — user preferences, past decisions,
  earlier claims — stored outside the context and brought back only when relevant.

Short-term memory needs managing so it doesn't overflow or get too expensive; long-term memory
needs a store, a way to retrieve the right items, and rules for updating or forgetting stale facts.

### Q8. Summarisation memory vs vector memory?

- **Summarisation:** when the history gets long, replace older turns with a model-written summary.
  Keeps context bounded and preserves the storyline; loses detail, and summary errors persist.
- **Vector memory:** store past items (messages, facts) as embeddings; for each new step, retrieve
  the most relevant ones — RAG over the agent's own history. Scales to long histories and keeps
  exact text; can retrieve the wrong memories, and ignores order.

Systems often combine them: a running summary plus retrieval of specific facts.

### Q9. What is mem0?

An open-source **memory layer** for LLM applications. It uses an LLM to **extract** facts worth
remembering from conversations ("prefers email"), stores them (vector store, optionally a graph),
**updates or deletes** memories when new facts contradict old ones, and retrieves the relevant
memories per user or session before the next model call. It saves building the extraction, update
and retrieval logic yourself; the trade-offs are an extra LLM call per write, and memories that can
be wrong and need governance — especially with personal data.

### Q10. LangChain / LangGraph vs a hand-written loop?

- **LangChain:** a library of components and integrations — model clients, retrievers, vector
  stores, tool wrappers.
- **LangGraph:** models an agent as a **state graph** — nodes are steps, edges are transitions,
  including cycles — with built-in checkpointing, durable execution, streaming and
  human-in-the-loop pauses.

Frameworks speed up complex, long-running, multi-step systems. A hand-written loop is better for
learning, small systems and full control, because every token and decision is visible. Rule: build
it by hand once, then adopt a framework when you need what it adds — not to hide a loop you don't
understand.
