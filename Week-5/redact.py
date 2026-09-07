"""Strip claimant identifiers out of text.

This runs on the way IN to the trace writer, before any line reaches disk, so a
raw claimant name never exists in traces.jsonl at any point. It is not a cleanup
pass over an existing file - there is deliberately no function here that opens a
trace file.

Two things here were learned the hard way, on a first run that was thrown away:

1. A two-capitalised-words rule alone leaks. The model writes the claimant back
   as a bare first name - "which Rebecca did by draining the system" - and one
   word does not match a two-word pattern. So the writer collects the name tokens
   it removed from every field of a record and then sweeps those single tokens
   through all the other fields. See `name_tokens` and the `also` argument.

2. A hand-written stoplist leaks the other way. It let "Water Backup and Sump
   Discharge Coverage" become "Water Backup and [NAME] Coverage", which is an
   endorsement title, not a person. The stoplist is now derived from the corpus:
   a capitalised word that appears in the endorsements is policy vocabulary and
   is never a claimant.
"""
import os
import re
import json

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chunks.jsonl")

# grammar and role words that are not in the endorsements but are not names either
BASE_STOP = {
    "the", "his", "her", "their", "our", "does", "did", "is", "was", "were",
    "do", "not", "no", "yes", "she", "he", "they", "we", "it", "this", "that",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "adjuster", "claimant", "policyholder", "please", "under", "per", "yes",
}


def _corpus_stop(path=CORPUS):
    """Every word in the endorsements. If it is in the policy wording it is not
    a claimant name, and this is far more reliable than guessing the vocabulary."""
    try:
        with open(path, encoding="utf-8") as f:
            text = " ".join(json.loads(line)["text"] for line in f if line.strip())
    except (OSError, ValueError):
        return set()
    return {w.lower() for w in re.findall(r"[A-Za-z]{2,}", text)}


STOP = BASE_STOP | _corpus_stop()

RULES = [
    # structured identifiers first - these are unambiguous
    ("CLAIM_ID", re.compile(r"\bCLM[-\s]?\d{4}[-\s]?\d{4,6}\b", re.I)),
    ("POLICY_ID", re.compile(r"\b(?:POL|HO|DP)[-\s]?\d{2,4}[-\s]?\d{5,8}\b")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")),
    # no leading \b - it would refuse to match the "(" of "(555) 271-0043"
    ("PHONE", re.compile(r"(?:\+?1[-.\s]?)?\(\d{3}\)[-.\s]?\d{3}[-.\s]?\d{4}"
                         r"|\b(?:\+?1[-.\s]?)?\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")),
    ("ADDRESS", re.compile(r"\b\d{1,5}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+"
                           r"(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Court|Ct|Way)\b")),
    # titled names, then bare two-word names
    ("NAME", re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?")),
    ("NAME", re.compile(r"\b[A-Z][a-z]{1,15}\s+[A-Z][a-z]{1,15}\b")),
]

TITLES = {"mr", "mrs", "ms", "miss", "dr"}


def _is_vocabulary(phrase):
    """True when a NAME match is policy wording and must be left alone."""
    words = [w.strip(".").lower() for w in phrase.split()]
    return any(w in STOP for w in words)


def name_tokens(text):
    """The individual words of every name in `text`, so the writer can sweep a
    bare first name out of a field where the full name never appeared."""
    found = set()
    for label, pattern in RULES:
        if label != "NAME":
            continue
        for match in pattern.findall(text or ""):
            phrase = match if isinstance(match, str) else match[0]
            if _is_vocabulary(phrase):
                continue
            for word in phrase.split():
                word = word.strip(".")
                if len(word) > 2 and word.lower() not in STOP and word.lower() not in TITLES:
                    found.add(word)
    return found


def redact(text, also=()):
    """Return (clean_text, counts). `also` is a set of single name tokens gathered
    from the whole record - that is what catches the echoed first name."""
    if not text:
        return text, {}

    counts = {}
    for label, pattern in RULES:
        def swap(m, label=label):
            if label == "NAME" and _is_vocabulary(m.group(0)):
                return m.group(0)
            counts[label] = counts.get(label, 0) + 1
            return "[%s]" % label
        text = pattern.sub(swap, text)

    for token in sorted(also, key=len, reverse=True):
        text, n = re.subn(r"\b%s\b" % re.escape(token), "[NAME]", text)
        if n:
            counts["NAME"] = counts.get("NAME", 0) + n
    return text, counts


def looks_clean(text, also=()):
    """Cheap assertion used by the trace writer. Anything that still matches a
    structured identifier, or a known name token, means redaction was bypassed."""
    text = text or ""
    for label, pattern in RULES:
        if label in ("CLAIM_ID", "EMAIL", "PHONE") and pattern.search(text):
            return False
    return not any(re.search(r"\b%s\b" % re.escape(t), text) for t in also)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    record = {
        "question": "CLM-2024-10042, insured Rebecca Lindqvist. Rental empty 45 days "
                    "between tenants but she drained the system. Covered?",
        "answer": "The exception applies, which Rebecca did by draining the system.",
        "title": "Water Backup and Sump Discharge Coverage endorsement (HO-0820).",
    }
    tokens = set()
    for value in record.values():
        tokens |= name_tokens(value)
    print("name tokens found across the record:", sorted(tokens), "\n")
    for field, value in record.items():
        clean, counts = redact(value, also=tokens)
        print("%-9s %s\n%-9s %s  %s\n" % ("in :", value, "out:", clean, counts))
