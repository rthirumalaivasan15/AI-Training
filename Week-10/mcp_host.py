"""The MCP host side of the agent: start every server named in an MCP config,
discover its tools with tools/list, and route each tool call to the server that
owns the tool.

Nothing here names a tool. The tool list the model sees is exactly what the
servers return from tools/list at start-up, so adding a server is a config change.

Config format (the common mcpServers shape):

    {"mcpServers": {"policy-docs": {"command": "python", "args": ["policy_server.py"],
                                    "env": {"SOME_TOKEN": "${SOME_TOKEN}"}}}}

"python" means the interpreter running the host. ${VAR} in env is filled from the
host's environment (.env included), so no secret is written into the config.
Servers start in the config file's directory.
"""
import os
import re
import sys
import json
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _expand(value):
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), value)


def load_config(path):
    with open(path, encoding="utf-8") as f:
        servers = json.load(f)["mcpServers"]
    base = os.path.dirname(os.path.abspath(path))
    params = {}
    for name, spec in servers.items():
        command = sys.executable if spec["command"] in ("python", "python3") else spec["command"]
        env = {k: _expand(v) for k, v in spec["env"].items()} if spec.get("env") else None
        params[name] = StdioServerParameters(command=command, args=spec.get("args", []),
                                             env=env, cwd=os.path.join(base, spec.get("cwd", ".")))
    return params


class Host:
    """async with Host("mcp_config.json") as host: host.tools, await host.call(name, args)"""

    def __init__(self, config_path, log=lambda line: None):
        self.config_path = config_path
        self.log = log
        self.tools = []      # OpenAI-format tool list, built from tools/list only
        self.routes = {}     # tool name -> server name
        self.sessions = {}   # server name -> ClientSession
        self.servers = {}    # server name -> what initialize and tools/list returned

    async def __aenter__(self):
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        for name, params in load_config(self.config_path).items():
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            init = await session.initialize()
            listed = await session.list_tools()
            for tool in listed.tools:
                if tool.name in self.routes:
                    raise ValueError("tool %s offered by both %s and %s"
                                     % (tool.name, self.routes[tool.name], name))
                self.routes[tool.name] = name
                self.tools.append({"type": "function", "function": {
                    "name": tool.name, "description": tool.description or "",
                    "parameters": tool.input_schema}})
            self.sessions[name] = session
            self.servers[name] = {
                "serverInfo": init.server_info.model_dump(mode="json", by_alias=True, exclude_none=True),
                "protocolVersion": init.protocol_version,
                "tools/list": listed.model_dump(mode="json", by_alias=True, exclude_none=True),
            }
            self.log("tools/list %s -> %d: %s" % (name, len(listed.tools),
                                                  ", ".join(t.name for t in listed.tools)))
        self.log("discovered %d tools from %d servers" % (len(self.tools), len(self.sessions)))
        return self

    async def __aexit__(self, *exc):
        return await self._stack.__aexit__(*exc)

    async def call(self, name, args):
        """Run one tool call on the server that owns it. Returns (result, server).
        A tool error comes back as {"error": text} so the model reads it as one."""
        server = self.routes.get(name)
        if server is None:
            return {"error": "unknown tool %s" % name}, None
        res = await self.sessions[server].call_tool(name, args)
        text = "\n".join(c.text for c in res.content if c.type == "text")
        if res.is_error:
            return {"error": text}, server
        try:
            return json.loads(text), server
        except json.JSONDecodeError:
            return text, server
