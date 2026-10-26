"""The output both arms must write: the Week 6 claim summary, because that is what
the Week 6 judge and the four Week 6 assertions read.

OUTPUT_SPEC is cut out of ../Week-6/prompts.py at import, not retyped, so the two
arms are held to exactly the lines the judge was validated on.
"""
import os
import importlib.util

import assertions

_spec = importlib.util.spec_from_file_location("week6_prompts", os.path.join("..", "Week-6", "prompts.py"))
_week6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_week6)
_full = _week6.CLAIMS_SUMMARY_V1

OUTPUT_SPEC = _full[_full.index("Output exactly these lines"):_full.index("\n\nRules you must follow")]

# The Week 6 rules, with "the numbered context passages provided" now meaning
# whatever wording the arm actually retrieved.
RULES = """Rules you must follow:
- Use only endorsement passages that were actually retrieved. You have no other knowledge of the policy wording.
- Exclusion codes and edition dates are not interchangeable. E-17 under one edition is not E-17 under another. If the retrieved wording does not contain the exact form and edition the notes name, say so.
- If the wording you have does not let you take a coverage position, use UNDETERMINED or NOT_IN_DOCUMENTS and say what is missing. Never guess and never fill a gap from general knowledge."""


def position(summary):
    return assertions.fields(summary).get("COVERAGE POSITION")
