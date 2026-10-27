# Architecture — claims triage & coverage assistant

```
 FNOL / claim number
        |
        v
 +----------------------------- app.py (one entry point) ------------------------------+
 |  tracer.Trace: one trace id per request, spans for every model call and tool call,  |
 |  redacted on write (names, addresses, phones, emails, policy ids, injuries)          |
 |                                                                                      |
 |  agent.py - hand-built loop (Week 7)                  llm.chat ---> Groq             |
 |    lap: model picks tools  <--------------------------  openai/gpt-oss-120b          |
 |    host routes each call over MCP, trace id in _meta    ** THE ONLY MODEL CALLS **   |
 |    ends ONLY when refer_to_adjuster accepts                ~93% of the cost          |
 +-----------+-------------------------------------------+------------------------------+
             | stdio JSON-RPC (tools discovered by tools/list, not hardcoded)
             v                                           v
 +--------------------------+          +------------------------------------------------+
 | claims-system (stand-in) |          | policy-docs  (OUR server - the one other        |
 |  get_claim_status        |          |  squads call)                                   |
 |  get_adjuster_notes      |          |  policy_lookup      policy_admin/policies.json  |
 |   -> raw notes WITH PII  |          |  coverage_in_force  terms, forms+editions,      |
 |   (the platform's data)  |          |                     deductibles, sub-limits     |
 |  span -> logs/mcp_claims |          |  search_policy  --> Chroma (MiniLM, local)       |
 +--------------------------+          |                     57 chunks, 7 wordings,      |
                                       |                     edition + in-force window   |
                                       |  refer_to_adjuster  refuses "covered" in code;  |
                                       |                     redacts; referrals/*.md     |
                                       |  span -> logs/mcp_policy-docs.jsonl             |
                                       |  no model call anywhere in this server          |
                                       +------------------------------------------------+

 evals: app.py eval -> suite.py: the same app.handle per case -> 8 assertions -> Week 6 judge
        (openai/gpt-oss-20b, a separate model and quota) -> runs/eval_<tag>.jsonl -> report.py
```

**Where the money goes:** every dollar is model tokens on `gpt-oss-120b`. Retrieval (local
embeddings, local Chroma) and the MCP tools cost $0 in API fees. What they cost is the tokens their
results add to every later model call: per request, the system prompt, the six tool definitions and
the growing history are re-sent on every lap. On the first end-to-end run (CLM-2024-30001, 6 laps)
that was generation $0.00229, retrieval-carried tokens $0.00027 and tool results $0.00013, out of
$0.00269.

**Where the model is not:** neither MCP server calls a model; the judge runs only in evals, never in
production.

**Trust boundary:** the claims system hands raw notes, with names, addresses and injuries, to the
host. They are redacted before any trace is written, and before anything leaves `policy-docs` (the
referral's facts and note). Policy records hold no claimant identity at all.
