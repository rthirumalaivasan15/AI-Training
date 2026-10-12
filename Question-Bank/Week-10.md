# Week 10 — Multi-Agent & A2A, With Evidence, Not Fashion

Module 5 · MCP, Multi-agent & A2A · build week

Topics: orchestrator–worker · specialist agents · when multi-agent helps · context re-send cost ·
single vs multi race · quality / latency / tokens / cost · A2A protocol · AgentCard and task
lifecycle · MCP vs A2A · CrewAI / AutoGen

---

### Q1. What is the orchestrator–worker pattern?

One **orchestrator** agent receives the task, **decomposes** it into sub-tasks, **delegates** each to
a specialist **worker** agent, and **synthesises** the workers' results into the final answer. Workers
run with their own prompts, tools and context; independent workers can run in parallel.

**In this project:** the claims squad — orchestrator plan + adjuster-note worker (in parallel), a
coverage/exclusions worker with one tool, then an orchestrator synthesis call.

### Q2. How do you design a specialist worker?

- **One narrow job** with a focused prompt.
- **Only the tools that job needs** — fewer tools means fewer wrong-tool errors. Giving a worker every
  tool the single agent had deletes the main reason a specialist could win.
- A **defined input** (a brief) and a **structured output** the orchestrator can check.
- Explicit fields for **uncertainty** — "subject to", "missing facts" — so conditions are not lost in
  hand-off.

**In this project:** the coverage worker got only `search_policy` and returned `position`, `grounds`,
`subject_to`, `reasoning`, `missing`.

### Q3. When does multi-agent genuinely help?

- Parts of the job are **truly independent** and can run **in parallel** (latency win).
- Parts need **clearly different instructions or tools** that interfere in one prompt.
- The context for one agent would be **too large**, and a worker can digest a slice and return a short
  result.
- Different parts need **different models** (a cheap model for extraction, a strong one for the
  decision).

It does not help when the steps are sequential and share the same facts: each hand-off then adds
cost, latency and a chance to drop information.

### Q4. What is the context re-send cost, and how do you measure it?

Every hand-off re-sends context: the worker's prompt plus whatever it is given; every lap of a worker's
own loop re-sends its whole history; the synthesis step re-reads the workers' outputs. Measure it with
a **hand-off log** — tokens billed per hand-off — and the **multiplier**:

```
multiplier = multi-agent total tokens / single-agent total tokens
```

Then attribute the largest share to a **named hand-off**. Don't blame "multi-agent" for a bad context
strategy, such as re-sending the full note history to every worker.

**In this project:** **78,382 / 47,339 = 1.7×**; the largest share was **orchestrator → coverage
worker, 57%** of squad tokens; 33% of all squad tokens were prompt tokens re-sent inside that worker's
search loop.

### Q5. How do you run a fair single vs multi race?

- The **same eval cases** — never a new set "because the old one doesn't suit the orchestrator"; that
  changes the ruler mid-measurement.
- The **same judge** and pass rule.
- The **same model and settings** for both arms; the same tools available to the system.
- Alternate arms case by case so both meet the same provider conditions.
- Commit the runs **before** judging, and never re-run a case to get a better result.

**In this project:** 10 Week-6 cases (the first two per failure mode, read from `Week-6/cases.jsonl`,
sha recorded), the Week-6 judge v2 + 4 assertions (prompt sha checked), `gpt-oss-120b` for both arms;
the raw runs were committed before any verdict existed.

### Q6. Which four numbers do you compare, and why is p99 not optional?

**Quality** (pass rate), **latency** (p50 *and* p99), **total tokens**, **cost per task**. Pass rate
alone can crown a team that costs 9× more; tokens alone can crown a cheap system that is wrong. p99 is
the slow claim the customer complains about, and multi-agent pipelines add latency in the tail.

**In this project:**

| arm | pass | p50 | p99 | tokens | cost/claim |
|---|---|---|---|---|---|
| single agent | 8/10 | 4.02 s | 6.20 s | 47,339 | $0.001234 |
| squad | 4/10 | 8.06 s | 11.04 s | 78,382 | $0.002384 |

Verdict: **kill the squad.** It won no case the single agent lost.

### Q7. A worker fails. What can the orchestrator do, and what happened here?

Three possibilities: **retry**; **degrade** to a partial answer that says what is missing; or **lie** —
e.g. declare a claim covered with no exclusions check. A good degrade names the failure: "exclusions
check did not run — re-run before deciding".

**In this project:** the coverage worker was made to return HTTP 500 on C02. The orchestrator
**retried once, then degraded**: no false "covered", but it shipped NOT_IN_DOCUMENTS and told the
adjuster to fetch policy forms that were already attached — the outage was invisible. It also looked
**cheaper** (2,974 vs 10,660 tokens) because it did less work.

### Q8. What is A2A?

**Agent-to-Agent** is an open protocol (started by Google, now under the Linux Foundation) for one agent
to delegate work to another agent, possibly built by another team on another framework. It runs over
HTTP(S) with **JSON-RPC**, supports streaming (Server-Sent Events) and push notifications for long tasks,
and treats the remote agent as **opaque** — you send it a task and messages, not its internals. Work is
exchanged as **messages** made of **parts** (text, files, data), and results come back as
**artifacts**.

### Q9. What is an AgentCard, and what is the A2A task lifecycle?

- **AgentCard:** a JSON document an agent publishes at a well-known URL that advertises **who it is and
  what it can do**: name, description, endpoint URL, version, **skills** (with examples), supported
  **input/output modes**, capabilities (streaming, push notifications) and the **authentication** it
  requires. Clients read it to discover and connect.
- **Task lifecycle:** a task moves through states — `submitted` → `working` → a final state:
  `completed`, `failed`, `canceled` or `rejected`. It can also pause in **`input-required`** (the agent
  needs more from the caller — e.g. an adjuster's confirmation) or `auth-required`, then resume.

Mapping matters: a claim whose exclusions check could not run should end `failed` or pause at
`input-required` — never `completed` with a guessed position.

### Q10. MCP vs A2A — and where do CrewAI and AutoGen fit?

- **MCP** connects an agent to **tools and data** — a server exposes capabilities; the host's model
  decides when to call them.
- **A2A** connects an agent to **other agents** — a peer that reasons for itself, runs long tasks,
  and returns results.

They complement each other: an agent can use tools over MCP and delegate to other agents over A2A.

**CrewAI** organises multi-agent work as a **crew** of role-based agents (role, goal, backstory) working
through tasks in a sequential or hierarchical process. **AutoGen** (Microsoft) builds multi-agent systems
as **conversations** between agents, with an event-driven runtime in newer versions. Both speed up
building a team; neither removes the need to race it against a single agent on the same eval.
