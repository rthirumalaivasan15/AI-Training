"""claims-system MCP server: claim status by claim number, and the adjuster note
history behind it. Read-only, stdio.

This is a local stand-in for the claims platform team's server, built to the
interface they describe, so the agent can be pointed at it with config alone.
It is not our code to change: the host only adds it to mcp_config.json.

Needs CLAIMS_API_TOKEN in its environment. Every call is appended to access.log
next to this file: time, token fingerprint, tool, claim number.
"""
import os
import re
import json
import hashlib
import datetime

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

HERE = os.path.dirname(os.path.abspath(__file__))
ACCESS_LOG = os.path.join(HERE, "access.log")
CLAIM_NUMBER = re.compile(r"^CLM-\d{4}-\d{5}$")

with open(os.path.join(HERE, "claims.json"), encoding="utf-8") as f:
    _claims = {c["claim_id"]: c for c in json.load(f)}

mcp = MCPServer("claims-system", log_level="WARNING")


def _audit(tool, claim_number):
    token = os.environ.get("CLAIMS_API_TOKEN", "")
    caller = hashlib.sha256(token.encode()).hexdigest()[:8] if token else "-"
    with open(ACCESS_LOG, "a", encoding="utf-8") as f:
        f.write("%s token=%s tool=%s claim=%s\n" % (
            datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            caller, tool, claim_number))
    if not token:
        raise ToolError("claims-system: no CLAIMS_API_TOKEN configured for this connection; "
                        "the claims system did not answer. This is not a statement about the claim.")


def _claim(claim_number):
    if not CLAIM_NUMBER.match(claim_number or ""):
        raise ToolError("claim number %r is malformed: claim numbers look like CLM-YYYY-nnnnn, "
                        "e.g. CLM-2024-10001" % claim_number)
    claim = _claims.get(claim_number)
    if claim is None:
        raise ToolError("claim %s not found: no claim with that number exists in the claims "
                        "system. Check the number with the adjuster." % claim_number)
    return claim


@mcp.tool()
def get_claim_status(claim_number: str) -> dict:
    """Current status and policy facts for one claim, by claim number (CLM-YYYY-nnnnn): status, policy number, policy line, endorsement forms attached, Coverage A limit, excess, date of loss, first notice of loss and claimed amount. Does not return the adjuster's notes - use get_adjuster_notes for those."""
    _audit("get_claim_status", claim_number)
    claim = _claim(claim_number)
    return {k: v for k, v in claim.items() if k != "adjuster_notes"}


@mcp.tool()
def get_adjuster_notes(claim_number: str) -> dict:
    """The adjuster's dated file notes for one claim, by claim number (CLM-YYYY-nnnnn), oldest first. An empty list means no notes have been written yet."""
    _audit("get_adjuster_notes", claim_number)
    claim = _claim(claim_number)
    return {"claim_id": claim_number, "adjuster_notes": claim.get("adjuster_notes", [])}


if __name__ == "__main__":
    mcp.run()   # stdio
