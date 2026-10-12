# Week 9 — MCP: the Standard Way Agents Reach Tools & Data

Module 5 · MCP, Multi-agent & A2A · build week

Topics: what MCP is · host, client, server · where the AI runs · tools, resources, prompts ·
transports (stdio, HTTP) · JSON-RPC handshake · tool discovery · building a server (FastMCP) ·
recoverable errors · remote MCP and auth

---

### Q1. What is MCP, and what problem does it solve?

The **Model Context Protocol** is an open standard for connecting AI applications to tools and data
— a common "socket". Without it, every app hand-wires every integration: N apps × M tools = N × M
custom integrations. With it, each tool is wrapped once as an MCP server and any MCP-capable app can
use it: N + M.

Be honest about what it is: **plumbing**. It wins on reuse, swapping and discovery. It does **not**
make answers better — the same tools over MCP give the same quality as the same tools wired by hand.

### Q2. What are the host, the client and the server?

- **Host:** the AI application the user works with — it runs the model, holds the conversation and
  decides what to call. (Here: `agent.py`.)
- **Client:** a connector inside the host, **one per server**, that speaks the protocol to that
  server. (Here: one `ClientSession` per server in `mcp_host.py`.)
- **Server:** a program that exposes capabilities — tools, resources, prompts — over MCP. It has no
  idea which model is calling it. (Here: `policy_server.py` and the claims-system server.)

### Q3. Where does the model actually run in an MCP setup? How can you prove it?

**In the host.** The server never calls a model: it advertises tools and runs them when asked. The
host sends the tool list to the model, the model picks a call, and the host sends `tools/call` to
the server. A server that calls a model to "decide coverage" has the architecture backwards.

**In this project:** the captured wire (`Week-9/wire.json`) shows **0.786 s of silence** between the
`tools/list` reply and the first `tools/call` — that gap is the host's model call to Groq. Nothing
on the wire, and nothing in either server, calls a model.

### Q4. Tools, resources and prompts — what is the difference?

- **Tools** — **model-controlled**: functions the model chooses to call (search the wording, compute
  a payout). They can have side effects.
- **Resources** — **application-controlled**: read-only data the host decides to attach as context
  (a file, a schema, the exclusions schedule). The model doesn't "call" them.
- **Prompts** — **user-controlled**: reusable prompt templates the user picks (e.g. a slash command
  "triage this claim").

Choosing wrongly costs you: exposing the exclusions schedule as a **tool** makes the model spend a
call fetching context it should have been given as a **resource**.

**In this project:** both servers expose tools only — resources and prompts are not used yet.

### Q5. What transports does MCP support, and when do you use each?

- **stdio:** the host launches the server as a child process and exchanges newline-delimited JSON-RPC
  over stdin/stdout. Simple and local; the server runs with the host user's permissions; nothing may
  be printed to stdout except protocol messages.
- **Streamable HTTP:** the server is a remote service; the client POSTs JSON-RPC messages and can
  receive streamed responses (Server-Sent Events). Needed for shared or hosted servers, and brings
  authentication (Q10). It replaced the older HTTP+SSE transport.

**In this project:** stdio for both servers; HTTP transport and remote auth are not built.

### Q6. Walk through the JSON-RPC handshake and a tool call.

1. Host → `initialize` (protocol version, client capabilities, client info).
2. Server → result (agreed protocol version, server capabilities, server info).
3. Host → `notifications/initialized` — a **notification**: no `id`, no reply.
4. Host → `tools/list`; server → the tools with name, description and input schema.
5. *(The host's model picks a call — off the wire.)*
6. Host → `tools/call` with name and arguments; server → result with `content` and `isError`.

Every request has an `id` that its response repeats; a response carries `result` or `error`, never
both.

**In this project:** all of it captured raw by `wiretap.py` and annotated field by field in
`Week-9/wire.json`.

### Q7. What is tool discovery, and how do you prove an agent really discovers its tools?

The host asks each server `tools/list` at start-up and offers the model **exactly what comes back** —
no hard-coded tool list. Adding a server should then be a **config change only**.

Proof: add a second server by editing only the MCP config and show (a) a **git diff with zero changed
lines** in the agent code, (b) the tool count from `tools/list` before and after, and (c) a trace in
which the new server's tool is called.

**In this project:** `Week-9/agent_diff.txt` shows an empty diff for the agent module (identical blob
hashes); `tools/list` went **2 → 4** (`search_policy`, `compute_payout` + `get_claim_status`,
`get_adjuster_notes`); the next run called both new tools on `claims-system`.

### Q8. How do you build an MCP server in Python?

With the SDK's high-level server class (**FastMCP**; renamed **`MCPServer`** in `mcp` 2.x): create the
server, decorate plain functions with `@mcp.tool()`, run it with `mcp.run()` (stdio by default). The
SDK builds each tool's **input schema from the type hints** (Pydantic `Annotated[..., Field(...)]` for
descriptions and constraints) and takes the **description from the docstring** — so the docstring is a
prompt the model reads. It validates arguments before your function runs and turns raised errors into
tool errors.

**In this project:** `policy_server.py` (two tools) and `claims_system/server.py`, about 60–100 lines
each, with no model call in either.

### Q9. What is a recoverable error, and why does it matter for agents?

An error the model can **act on**: it says what was wrong and how to fix it — "claim CLM-2024-88120
not found: claim numbers look like CLM-YYYY-nnnnn" rather than "Error 3" or a silent empty result. In
MCP, a tool failure is returned as a normal result with **`isError: true`** (not a JSON-RPC protocol
error), so the model sees the message and can retry correctly.

The worst error is a **silent** one: an empty or partial result that looks like a real answer.

**In this project:** a form number written `HO 08 20` used to drop HO-0820 from the search filter
silently. After the rewrite it returns an error naming the bad form, the nearest match and the forms
held; with the same pinned failing call, the model repaired the call in one lap from the message
instead of by guesswork.

### Q10. How do authentication and trust work for remote MCP servers?

For HTTP servers the spec uses **OAuth 2.1**: the MCP server acts as a resource server, advertises
which authorisation server to use (protected-resource metadata), and accepts only access tokens
**issued for it** (audience-bound); it must not pass a client's token through to other services.

Trust is the bigger question. A third-party server runs inside your agent's trust boundary: its tool
descriptions go **verbatim into your model's prompt**, a stdio server runs with **your user's
rights**, and its token may reach far more data than one task needs. Before adding one, ask: who wrote
it, what can it reach, what does it log, what could a stolen token do — then pin a version, scope the
token, and review it.

**In this project:** `Week-9/risk_note.md` answers those for the claims-system server and says
**don't ship as-is** — unversioned build, one static unscoped token that reads every open claim's
notes, and a log that cannot tell the agent from an attacker using the same token.
