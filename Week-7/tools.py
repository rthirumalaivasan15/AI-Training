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
]

IMPLS = {"get_claim": get_claim, "search_policy": search_policy}


def run_tool(name, args):
    if name not in IMPLS:
        return {"error": "unknown tool %s" % name}
    try:
        return IMPLS[name](**args)
    except TypeError as exc:
        return {"error": "bad arguments for %s: %s" % (name, exc)}
