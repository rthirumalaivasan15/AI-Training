"""The claims tools. The same Python functions serve the agent (which the model
calls through TOOLS) and the workflow (which calls them directly in a fixed order).

Each description names one job and says what the tool does not return, so the
model has no reason to call get_claim for policy wording or search_policy for
claim facts.
"""
import json
from search import dense_search

CLAIMS_FILE = "claims.json"

with open(CLAIMS_FILE, encoding="utf-8") as f:
    _claims = {c["claim_id"]: c for c in json.load(f)}


def get_claim(claim_id):
    claim = _claims.get(claim_id)
    if claim is None:
        return {"error": "no claim with id %s" % claim_id}
    return claim


def search_policy(query, form_numbers=None, k=4):
    where = None
    if form_numbers:
        forms = [f.split()[0] for f in form_numbers]   # "HO-0304 ed. 03-24" -> "HO-0304"
        where = {"form_number": forms[0]} if len(forms) == 1 else {"form_number": {"$in": forms}}
    hits = dense_search(query, k=k, where=where)
    return [{"chunk_id": h["chunk_id"], "form_number": h["meta"]["form_number"],
             "text": h["text"]} for h in hits]


CLAIM_STATUSES = ("covered", "denied", "undetermined")


def compute_payout(claim_status, loss_amount, excess, limit=None):
    if claim_status not in CLAIM_STATUSES:
        return {"error": "claim_status must be one of %s" % ", ".join(CLAIM_STATUSES)}
    if claim_status == "denied":
        return {"payable_amount": 0}
    if claim_status == "undetermined":
        return {"payable_amount": None}
    capped = min(loss_amount, limit) if limit is not None else loss_amount
    return {"payable_amount": max(0, round(capped - excess))}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_claim",
            "description": (
                "Fetch the record for one claim by its claim number: policy number, "
                "endorsement forms attached, excess, Coverage A limit, date of loss, "
                "claimed amount and the adjuster's dated file notes. Returns claim facts "
                "only - it never returns endorsement wording."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string", "pattern": "^CLM-\\d{4}-\\d{5}$",
                                 "description": "Claim number, e.g. CLM-2024-10001."},
                },
                "required": ["claim_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_policy",
            "description": (
                "Search the endorsement wording - definitions, exclusions table rows, "
                "exceptions, limits and duty clauses - with a free-text query, optionally "
                "restricted to specific form numbers. Returns wording passages with chunk "
                "ids only - it never returns claim facts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string",
                              "description": "What to look for in the wording, e.g. 'sewer backup deductible'."},
                    "form_numbers": {"type": "array", "items": {"type": "string"},
                                     "description": "Form numbers to restrict to, e.g. ['HO-0820']. Omit to search all forms."},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_payout",
            "description": (
                "Compute the payable amount for a coverage decision already made: "
                "min(loss_amount, limit) minus the excess, never below zero; 0 when denied, "
                "null when undetermined. Arithmetic only - it never reads the claim or the "
                "wording, so pass in the figures you have already found."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_status": {"type": "string", "enum": list(CLAIM_STATUSES),
                                     "description": "The coverage decision already reached."},
                    "loss_amount": {"type": "integer", "minimum": 0,
                                    "description": "Dollars of loss the decision applies to."},
                    "excess": {"type": "integer", "minimum": 0,
                               "description": "Excess or deductible in dollars that applies to this loss."},
                    "limit": {"type": "integer", "minimum": 0,
                              "description": "Per-event limit or sublimit in dollars that caps this loss. Omit if none applies."},
                },
                "required": ["claim_status", "loss_amount", "excess"],
                "additionalProperties": False,
            },
        },
    },
]

IMPLS = {"get_claim": get_claim, "search_policy": search_policy, "compute_payout": compute_payout}


def run_tool(name, args):
    if name not in IMPLS:
        return {"error": "unknown tool %s" % name}
    try:
        return IMPLS[name](**args)
    except TypeError as exc:
        return {"error": "bad arguments for %s: %s" % (name, exc)}
