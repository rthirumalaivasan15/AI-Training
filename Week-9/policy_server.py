"""Server one: the policy-document search server (ours), over MCP stdio.

Exposes the endorsement wording and the payout arithmetic as two tools. No model
is called anywhere in this file: the server exposes a capability, the host runs
the model and decides what to call.

    python policy_server.py      # normally launched by the host from mcp_config.json

Nothing may be printed to stdout - stdout is the JSON-RPC channel.
"""
import re
from typing import Annotated, Literal, Optional

from pydantic import Field
from mcp.server.mcpserver import MCPServer

from search import dense_search

mcp = MCPServer("policy-docs", log_level="WARNING")

# Week 8 mitigation, carried over: compute_payout refuses a limit that no passage
# retrieved in this session states. One stdio session is one server process is
# one agent run, so the evidence is per run.
_evidence = []


def _numbers_seen():
    return {int(n.replace(",", "")) for text in _evidence
            for n in re.findall(r"\d[\d,]*", text)}


@mcp.tool()
def search_policy(
    query: Annotated[str, Field(description="What to look for in the wording, e.g. 'sewer backup deductible'.")],
    form_numbers: Annotated[Optional[list[str]], Field(
        description="Form numbers to restrict to, e.g. ['HO-0820']. Omit to search all forms.")] = None,
) -> dict:
    """Search the endorsement wording - definitions, exclusions table rows, exceptions, limits and duty clauses - with a free-text query, optionally restricted to specific form numbers. Returns wording passages with chunk ids only - it never returns claim facts."""
    where = None
    if form_numbers:
        forms = [f.split()[0] for f in form_numbers]   # "HO-0304 ed. 03-24" -> "HO-0304"
        where = {"form_number": forms[0]} if len(forms) == 1 else {"form_number": {"$in": forms}}
    hits = dense_search(query, k=4, where=where)
    _evidence.extend(h["text"] for h in hits)
    return {"passages": [{"chunk_id": h["chunk_id"], "form_number": h["meta"]["form_number"],
                          "text": h["text"]} for h in hits]}


@mcp.tool()
def compute_payout(
    claim_status: Annotated[Literal["covered", "denied", "undetermined"], Field(
        description="The coverage decision already reached.")],
    loss_amount: Annotated[int, Field(ge=0, description="Dollars of loss the decision applies to.")],
    excess: Annotated[int, Field(ge=0, description="Excess or deductible in dollars that applies to this loss.")],
    limit: Annotated[Optional[int], Field(
        ge=0, description="Per-event limit or sublimit in dollars that caps this loss. Omit if none applies.")] = None,
) -> dict:
    """Compute the payable amount for a coverage decision already made: min(loss_amount, limit) minus the excess, never below zero; 0 when denied, null when undetermined. Arithmetic only - it never reads the claim or the wording, so pass in the figures you have already found."""
    if claim_status == "denied":
        return {"payable_amount": 0}
    if claim_status == "undetermined":
        return {"payable_amount": None}
    if limit is not None and limit not in _numbers_seen():
        return {"error": "limit %s is not stated in any passage you have retrieved. Search the "
                         "wording for the clause that states the per-event limit or sublimit and "
                         "call again with that figure, or omit limit if the wording states none. "
                         "A Coverage A limit from the claim record is not a per-event limit."
                         % limit}
    capped = min(loss_amount, limit) if limit is not None else loss_amount
    return {"payable_amount": max(0, round(capped - excess))}


if __name__ == "__main__":
    mcp.run()   # stdio
