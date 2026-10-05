"""Report the tools every server in an MCP config returns from tools/list.

    python list_tools.py mcp_config.json runs/tools_after.json

The count and names come from the servers' own tools/list replies, through the
same host the agent uses - not from anyone's notes. The full replies are saved.
"""
import sys
import json
import asyncio

from mcp_host import Host


async def main(config, out):
    async with Host(config, log=print) as host:
        report = {"config": config, "tool_count": len(host.tools),
                  "tools": [{"name": t["function"]["name"], "server": host.routes[t["function"]["name"]]}
                            for t in host.tools],
                  "servers": host.servers}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("%d tools: %s" % (report["tool_count"], ", ".join(t["name"] for t in report["tools"])))
    print("wrote", out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main(sys.argv[1], sys.argv[2]))
