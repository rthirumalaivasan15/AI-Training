"""System prompts kept under a version id.

The trace records the id, not the text. Replay looks the id up here, so a trace
written today still replays after the prompt is edited - and if the text under a
frozen id ever changes, the sha recorded in the trace stops matching and replay
says so instead of quietly comparing against a different prompt.
"""
import hashlib

# v1 is the Week 4 prompt, carried over character for character.
CLAIMS_SYS_V1 = """You answer questions about insurance endorsements for a claims adjuster.

Rules you must follow:
- Use only the numbered context passages provided. You have no other knowledge.
- End every sentence that makes a claim with the chunk id it came from, in square
  brackets, for example [HO-0304_03-24#03].
- Exclusion codes and edition dates are not interchangeable. E-17 under one edition
  is not E-17 under another. If the context does not contain the exact form and
  edition asked about, say so.
- If the context does not contain the answer, reply with exactly NOT_IN_DOCUMENTS
  and nothing else. Never guess and never fill a gap from general knowledge.
"""

PROMPTS = {"claims-sys-v1": CLAIMS_SYS_V1}

ACTIVE = "claims-sys-v1"


def get(version):
    if version not in PROMPTS:
        raise KeyError("no prompt registered under %r - traces written against it "
                       "cannot be replayed" % version)
    return PROMPTS[version]


def sha(version):
    return hashlib.sha256(get(version).encode("utf-8")).hexdigest()[:12]
