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

PROMPTS = {"claims-agent-v1": CLAIMS_AGENT_V1}
DEFAULT = "claims-agent-v1"


def active():
    return os.getenv("PROMPT_VERSION", DEFAULT)


def get(version):
    if version not in PROMPTS:
        raise KeyError("no prompt registered under %r" % version)
    return PROMPTS[version]


def sha(version):
    return hashlib.sha256(get(version).encode("utf-8")).hexdigest()[:12]
