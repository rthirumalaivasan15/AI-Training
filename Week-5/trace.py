"""One JSON line per answered question.

Redaction happens inside write(), before json.dumps is ever called. There is no
path through this module that puts an un-redacted question on disk, and write()
raises rather than falling back if a structured identifier survives the pass.
"""
import io
import os
import json
import uuid
import hashlib
import datetime
from redact import redact, looks_clean, name_tokens

TRACE_DIR = "traces"
TRACE_FILE = os.path.join(TRACE_DIR, "traces.jsonl")
CORPUS = "chunks.jsonl"

SCHEMA = "week5-trace-v1"

# every free-text field goes through the redactor - the model's scratchpad quotes
# the question back at itself, so it leaks names just as readily as the question
TEXT_FIELDS = ("question", "raw_output", "reasoning")


def corpus_fingerprint(path=CORPUS):
    """Replay has to know it is reading the same 48 chunks the trace was written
    against. Chunk ids alone would not catch a re-chunk that reused the ids."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


def new_trace_id():
    return "trc_" + uuid.uuid4().hex[:12]


def write(record, path=TRACE_FILE):
    """Redact, assert, append. Returns the record as it was actually stored."""
    record = dict(record)

    # pass 1: collect every name token anywhere in the record. The model echoes
    # the claimant back as a bare first name, which no two-word rule can catch,
    # so the full name found in the question is what unlocks the one in the answer.
    tokens = set()
    for field in TEXT_FIELDS:
        tokens |= name_tokens(record.get(field, ""))

    # pass 2: redact each field, sweeping those single tokens through all of them
    counts = {}
    for field in TEXT_FIELDS:
        clean, hits = redact(record.get(field, ""), also=tokens)
        record[field] = clean
        for label, n in hits.items():
            counts[label] = counts.get(label, 0) + n
    record["redactions"] = counts

    # if this ever fires, something reached the writer around redact()
    for field in TEXT_FIELDS:
        if not looks_clean(record.get(field, ""), also=tokens):
            raise AssertionError("identifier survived redaction in %r - refusing "
                                 "to write trace %s" % (field, record.get("trace_id")))

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with io.open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_all(path=TRACE_FILE):
    with io.open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def by_id(trace_id, path=TRACE_FILE):
    for row in read_all(path):
        if row["trace_id"] == trace_id:
            return row
    raise KeyError(trace_id)


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
