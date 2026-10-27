# For Thursday's fresh-eyes reviewer (another squad)

You need nothing from us but this file and the repo. Note where you get stuck — that is the point.

## 1. Set up (Windows, Python 3.10+)

```
git clone <this repo>
cd AI-Training\Week-12
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env          # put a Groq API key in GROQ_API_KEY; any value for CLAIMS_API_TOKEN
.venv\Scripts\python ingest.py
.venv\Scripts\python index.py
```

## 2. Run our system end to end

```
.venv\Scripts\python app.py triage CLM-2025-30003
.venv\Scripts\python app.py trace <the trace id it prints>
```

## 3. Call OUR MCP server from YOUR agent

Our server is `policy_server.py` (stdio). Add it to your MCP host's config — run it from `Week-12`:

```json
{"mcpServers": {"policy-docs": {"command": "<path>\\Week-12\\.venv\\Scripts\\python.exe",
                                "args": ["policy_server.py"], "cwd": "<path>\\Week-12"}}}
```

Your agent should discover four tools by `tools/list`: `policy_lookup`, `coverage_in_force`,
`search_policy`, `refer_to_adjuster`. Try, for example: `coverage_in_force("HP-460113", "2025-01-03")`,
`search_policy("surface water through a door", "2024-08-11", ["HO-0304 ed. 03-24"])`, and a
`refer_to_adjuster` call that contains the word "covered".

Every call you make is logged in `Week-12/logs/mcp_policy-docs.jsonl` — send your trace id in the request
`_meta` as `{"trace_id": "..."}` and it is logged under your id.

## 4. Tell us

Your name and squad, which step you got stuck on and for how long, what our server returned that
surprised you, and **everything it returned to your agent** — we want to know what it handed you.
