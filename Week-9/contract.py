"""The output contract both systems must meet, and the pass rule applied to it.

The agent and the workflow are graded by the same function against the same
expected.json, so a pass means the same thing for both.
"""
import re
import json

POSITIONS = ("COVERED", "DENIED", "UNDETERMINED")
KEYS = ("claim_id", "coverage_position", "grounds", "payable_amount", "reasoning", "next_step")

CONTRACT_TEXT = """Return one JSON object and nothing else, with exactly these keys:
{
  "claim_id": "<the claim number>",
  "coverage_position": "COVERED" | "DENIED" | "UNDETERMINED",
  "grounds": ["<exclusion codes such as E-17 and form clauses such as HO-0820 Clause 2 the position rests on>"],
  "payable_amount": <integer dollars after the excess, 0 if DENIED, null if UNDETERMINED>,
  "reasoning": "<two to four sentences, each citing the chunk id it relies on in square brackets>",
  "next_step": "<one sentence for the adjuster>"
}"""


def parse(text):
    """Pull the JSON object out of a model reply. Returns (dict, error)."""
    if not text:
        return None, "empty reply"
    found = re.search(r"\{.*\}", text, re.S)
    if not found:
        return None, "no JSON object in reply"
    try:
        obj = json.loads(found.group(0))
    except json.JSONDecodeError as exc:
        return None, "invalid JSON: %s" % exc
    return validate(obj)


def validate(obj):
    missing = [k for k in KEYS if k not in obj]
    if missing:
        return None, "missing keys: %s" % ", ".join(missing)
    if obj["coverage_position"] not in POSITIONS:
        return None, "coverage_position %r not in %s" % (obj["coverage_position"], POSITIONS)
    if not isinstance(obj["grounds"], list):
        return None, "grounds is not a list"
    pay = obj["payable_amount"]
    if pay is not None and not isinstance(pay, (int, float)):
        return None, "payable_amount is not a number or null"
    return {k: obj[k] for k in KEYS}, None


def grade(output, expected):
    """Pass only if position, payable amount and every must_cite token are right.
    Returns (passed, list of reasons it failed)."""
    if output is None:
        return False, ["no valid output"]
    why = []
    if output["coverage_position"] != expected["coverage_position"]:
        why.append("position %s, expected %s" % (output["coverage_position"], expected["coverage_position"]))
    pay, want = output["payable_amount"], expected["payable_amount"]
    if (pay is None) != (want is None) or (pay is not None and round(pay) != want):
        why.append("payable %s, expected %s" % (pay, want))
    grounds = " ".join(str(g) for g in output["grounds"])
    for token in expected["must_cite"]:
        if token not in grounds:
            why.append("grounds missing %s" % token)
    return not why, why
