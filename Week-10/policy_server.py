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
from mcp.server.mcpserver.exceptions import ToolError

from index import load_chunks
from search import dense_search

mcp = MCPServer("policy-docs", log_level="WARNING")

# Week 8 mitigation, carried over: compute_payout refuses a limit that no passage
# retrieved in this session states. One stdio session is one server process is
# one agent run, so the evidence is per run.
_evidence = []


def _numbers_seen():
    return {int(n.replace(",", "")) for text in _evidence
            for n in re.findall(r"\d[\d,]*", text)}


FORMS = sorted({row["form_number"] for row in load_chunks()})


def _form(raw):
    """'HO-0304' or 'HO-0304 ed. 03-24' -> 'HO-0304'. Anything else is refused, with
    the nearest form the library holds, so the model can correct it and call again.
    (Week 9 fix: this used to be raw.split()[0], which turned 'HO 08 20' into 'HO',
    matched nothing, and silently dropped that form from the search.)"""
    head = re.sub(r"\s+ed\.?\s*[\d-]+$", "", raw.strip())
    if head in FORMS:
        return head
    guess = "%s-%s" % (re.sub(r"[^A-Z]", "", head.upper()), re.sub(r"\D", "", head))
    raise ToolError(
        "form %r is not in the endorsement library, so nothing was searched. Form numbers look "
        "like HO-0820: two letters, a hyphen, four digits (an edition suffix such as ' ed. 05-24' "
        "is accepted).%s Forms held: %s. Call search_policy again with corrected form_numbers, "
        "or omit form_numbers to search every form."
        % (raw, " Did you mean %s?" % guess if guess in FORMS else "", ", ".join(FORMS)))


@mcp.tool()
def search_policy(
    query: Annotated[str, Field(description="Plain words for the one fact you need, e.g. 'sewer backup per-event limit'.")],
    form_numbers: Annotated[Optional[list[str]], Field(
        description="The claim's endorsements as HO-0820 (two letters, hyphen, four digits), copied "
                    "from forms_attached. Omit to search every form.")] = None,
) -> dict:
    """Search the endorsement wording and return the passages a coverage decision rests on.

    Call this whenever the decision depends on wording: a definition, an exclusions table row (codes like E-16), the exception in that row, a limit or sublimit, a deductible, or a duty such as maintenance or notice. One call per fact; a second, narrower query is normal when the first does not show the clause you need.

    query: plain words for the fact, e.g. 'sewer backup per-event limit' or 'vacant more than 60 days'.
    form_numbers: the endorsements attached to the claim, written HO-0820 - two letters, a hyphen, four digits. Copy them from the claim's forms_attached; 'HO-0820 ed. 05-24' is accepted. Omit to search every form.

    Returns {"passages": [{chunk_id, form_number, text}]}, up to 4, best match first. Cite the chunk_id of every passage you rely on. Never returns claim facts - those come from the claims system.

    If a form number is not in the library, nothing is searched and the error names the bad form, the closest form held and the full list: correct form_numbers and call again. Do not read that error as the wording being silent."""
    where = None
    if form_numbers:
        forms = [_form(f) for f in form_numbers]
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
