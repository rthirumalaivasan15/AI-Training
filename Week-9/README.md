# Week 9 — Task Set D — Insurance claims

Bolt on the claims-system server without touching the agent.

**Server two was added with config only: 0 lines changed in the agent module,
tools/list went from 2 to 4, and the first query after it called
`get_claim_status` and `get_adjuster_notes` on `claims-system` and passed
CLM-2024-10004 (COVERED, 9,000).** With server one alone the same claim came back
UNDETERMINED, because no tool could load the claim.

**Tool count, from tools/list: 2 before -> 4 after.**
- before (`runs/tools_before.json`): `search_policy`, `compute_payout` (policy-docs)
- after (`runs/tools_after.json`): `search_policy`, `compute_payout` (policy-docs), `get_claim_status`, `get_adjuster_notes` (claims-system)

**Where the model call happens:** only in the host — `agent.py` `run()` -> `llm.chat` ->
Groq — in the 0.786 s gap on the wire between the tools/list reply and the first
tools/call; never on the wire and never inside either server.

**Error path:** an ISO-style form number (`HO 08 20`) used to drop that form from
the search silently; it is now a recoverable error naming the form, the nearest
match and the forms held. Same pinned failing call: the model now repairs the call
from the error instead of by inference — and the run then failed downstream on a
retrieval miss the error fix does not touch (PASS 9,000 -> FAIL 13,200, one run
each). Full account in [error_before_after.md](error_before_after.md).

| deliverable | file |
|---|---|
| agent module, 0 changed lines | [agent_diff.txt](agent_diff.txt) — `git diff 1a9bff0 3d7186a`, empty; blob hashes identical |
| config diff adding server two | [config_diff.txt](config_diff.txt) |
| raw initialize -> tools/list -> tools/call, annotated | [wire.json](wire.json) (byte-exact lines: `runs/wire_raw.jsonl`) |
| tool count before -> after, with names | above, and `runs/tools_before.json`, `runs/tools_after.json` |
| trace showing the server-two tool called | `runs/trace_server1_plus_2.log` (server one only: `runs/trace_server1_only.log`) |
| same failing call, old docstring/error vs new | [error_before_after.md](error_before_after.md) |
| supply-chain risk note, 5 lines | [risk_note.md](risk_note.md) |

Same model as Weeks 7–8: `openai/gpt-oss-120b` on Groq, temperature 0.

## Commits that carry the proof

| commit | state |
|---|---|
| `d8f9ab1` | MCP host + server one; tools/list before |
| `1a9bff0` | server one only, one query run — **"before" side of agent_diff** |
| `3d7186a` | server two added to `mcp_config.json` — **"after" side of agent_diff** |
| `85a1ee5` | server two live: tools/list after, trace, wire capture |
| `22a81d8` | error demo before (old `search_policy`) |
| `29d0bd4` | `search_policy` docstring + error rewrite (only `policy_server.py` changes) |

## Layout

| path | what |
|---|---|
| `agent.py` | the loop and the model call; holds no tool list |
| `mcp_host.py` | starts every server in the config, tools/list, routes each call |
| `mcp_config.json` | the servers — the only file that changed to add server two |
| `policy_server.py` | server one (ours): `search_policy`, `compute_payout`; no model call |
| `claims_system/` | server two: `get_claim_status`, `get_adjuster_notes`; read-only, needs `CLAIMS_API_TOKEN`, writes `access.log`. A local stand-in for the platform team's server, built to the interface they describe |
| `wiretap.py` | stdio proxy that records every JSON-RPC line both ways; inserted by config (`mcp_config.wire.json`) |
| `list_tools.py` | prints and saves what tools/list returns per server |
| `error_demo.py` | the pinned-failing-call run, and its transcript renderer |

## Setup

```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env        # Groq key, and CLAIMS_API_TOKEN for the claims-system server
.venv\Scripts\python index.py
```

## Run

```
.venv\Scripts\python list_tools.py mcp_config.json runs/tools_after.json
.venv\Scripts\python agent.py CLM-2024-10004 --log runs/trace.log
.venv\Scripts\python agent.py CLM-2024-10004 --config mcp_config.wire.json    # also writes runs/wire_raw.jsonl
.venv\Scripts\python error_demo.py after                                       # refuses to overwrite a finished run
.venv\Scripts\python error_demo.py render after
```

The bonus (one gateway in front of both servers, audit line per tools/call, scoped
token denying the notes tool) is not done.
