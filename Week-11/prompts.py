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

# v3 = v2 + one sentence. v2 fixed the position on the failing case (NOT_IN_DOCUMENTS,
# judge PASS) but then wrote EXCESS: NOT STATED although the notes give 1,000 - the
# scope rule read as "nothing applies, so report nothing". The claim facts are the
# notes' facts whatever the position. Suite runs: v1 8/11, v2 6/11 (runs/).
FACTS_RULE = """Whatever the position - including NOT_IN_DOCUMENTS - CLAIM NUMBER, DATE OF LOSS and EXCESS are facts from the notes: report them exactly as the notes give them.

"""
CLAIMS_AGENT_V3 = CLAIMS_AGENT_V2.replace(_V1_HEAD, FACTS_RULE + _V1_HEAD)
assert CLAIMS_AGENT_V3 != CLAIMS_AGENT_V2

PROMPTS = {"claims-agent-v1": CLAIMS_AGENT_V1, "claims-agent-v2": CLAIMS_AGENT_V2,
           "claims-agent-v3": CLAIMS_AGENT_V3}
# Production stays on v1 until the v2 canary passes (README: canary and rollback);
# the suite and the canary select the candidate with PROMPT_VERSION / CANARY_VERSION.
DEFAULT = "claims-agent-v1"


def active():
    return os.getenv("PROMPT_VERSION", DEFAULT)


def for_user(user):
    """Canary routing: users listed in CANARY_USERS get CANARY_VERSION, everyone else
    the active version. Rollback is emptying CANARY_USERS - no deploy."""
    canary = {u.strip() for u in os.getenv("CANARY_USERS", "").split(",") if u.strip()}
    if user in canary and os.getenv("CANARY_VERSION"):
        return os.environ["CANARY_VERSION"]
    return active()


def get(version):
    if version not in PROMPTS:
        raise KeyError("no prompt registered under %r" % version)
    return PROMPTS[version]


def sha(version):
    return hashlib.sha256(get(version).encode("utf-8")).hexdigest()[:12]
