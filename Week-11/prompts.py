"""The claims app's system prompt, kept under a version id.

Every trace records the version and the sha of the exact text that produced it,
so a bad answer in the logs can always be tied to the instructions behind it,
and a prompt change is a version bump the logs can slice on.

    PROMPT_VERSION=claims-agent-v1    (in .env; the default)
"""
import os
import hashlib

import summary_format

# v1 is the Week 10 single agent's prompt, word for word: the app as it shipped.
CLAIMS_AGENT_V1 = """You write a claim summary for an insurance claims adjuster from their file notes.

Before you take a position, search the endorsement wording for every exclusion, exception, definition, limit or duty the facts in the notes bring into play. The notes decide which wording matters: if a note reveals a cause, a duration, a vacancy, a business use or a missed duty, search the wording for it.

When you are done, reply with the summary and nothing else.

""" + summary_format.OUTPUT_SPEC + "\n\n" + summary_format.RULES

# v2 = v1 + one rule, the fix for trc_a4a9f492d77c: a loss at a rental condo the
# insured owns elsewhere was answered COVERED under the HO-0304 E-17 exception,
# because nothing made the model ask whether a homeowners form reaches that
# property. Everything else is v1, word for word.
SCOPE_RULE = """Before you apply any endorsement, establish where the loss happened and whether the forms on file reach that property. Homeowners forms (HO-) cover the insured's own residence premises; a dwelling the insured rents out to tenants is insured on a dwelling-fire policy (DP-). If the loss is at a property the attached forms do not cover, the position is NOT_IN_DOCUMENTS: say which property it is and name the policy or form that would be needed, and do not apply the attached forms' exclusions or exceptions to it.

"""
_V1_HEAD = "When you are done, reply with the summary and nothing else.\n\n"
CLAIMS_AGENT_V2 = CLAIMS_AGENT_V1.replace(_V1_HEAD, SCOPE_RULE + _V1_HEAD)
assert CLAIMS_AGENT_V2 != CLAIMS_AGENT_V1

PROMPTS = {"claims-agent-v1": CLAIMS_AGENT_V1, "claims-agent-v2": CLAIMS_AGENT_V2}
# Production stays on v1 until the v2 canary passes (README: canary and rollback);
# the suite and the canary select v2 with PROMPT_VERSION=claims-agent-v2.
DEFAULT = "claims-agent-v1"


def active():
    return os.getenv("PROMPT_VERSION", DEFAULT)


def get(version):
    if version not in PROMPTS:
        raise KeyError("no prompt registered under %r" % version)
    return PROMPTS[version]


def sha(version):
    return hashlib.sha256(get(version).encode("utf-8")).hexdigest()[:12]
