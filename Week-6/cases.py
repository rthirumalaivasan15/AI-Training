"""The eval set: 22 written cases plus regression cases replayed from real Week 5
failures.

Every case carries exactly one Week 5 taxonomy mode - the mode it was written to
exercise. The written cases also carry the structured facts the assertions check
against (claim number, date of loss, excess), taken from the notes when the case
was written, never from a summary.

The regression cases are not copied into cases.jsonl. They are read out of the
Week 5 trace file every time, so "replayed verbatim" is something the code does
rather than something I typed: the notes are the trace's question byte for byte
(redacted, as it was stored) and the passages are the trace's own retrieved chunk
ids in their recorded rank order. If the corpus has moved since the trace was
written, loading stops.
"""
import os
import json
import hashlib

CASES = "cases.jsonl"
CORPUS = "chunks.jsonl"
WEEK5_TRACES = os.path.join("..", "Week-5", "traces", "traces.jsonl")

# the five modes from Week-5/taxonomy.md, in its order
MODES = {
    1: "silent-but-not-fetched",
    2: "invented-consequence",
    3: "wrong-endorsement",
    4: "exception-skips-definition",
    5: "score-floor-refusal",
}

# each is the example trace for its mode in Week-5/taxonomy.md
REGRESSIONS = [
    ("R01", "trc_99613f4f2842", 1),   # candles business - said NOT_IN_DOCUMENTS, E-31 never fetched
    ("R02", "trc_4ab44f82de51", 2),   # roof replaced before inspection - invented a right to deny
    ("R03", "trc_df4ab8c54cd4", 4),   # empty 22 days - paid a burst without the 14-day test
]


def corpus_sha(path=CORPUS):
    # same fingerprint Week 5 wrote into every trace, over LF line endings so a
    # CRLF checkout of the same 48 chunks is not mistaken for a moved corpus
    with open(path, "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()[:12]


def written(path=CASES):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def regression(case_id, trace_id, mode, path=WEEK5_TRACES):
    with open(path, encoding="utf-8") as f:
        record = next((json.loads(line) for line in f
                       if ('"%s"' % trace_id) in line), None)
    if record is None:
        raise KeyError("trace %s not found in %s" % (trace_id, path))
    if record["corpus_sha"] != corpus_sha():
        raise RuntimeError("corpus moved since %s was written - replay would not be verbatim"
                           % trace_id)
    if record["refused_by"] == "score floor":
        raise RuntimeError("%s never reached the model, there is nothing to replay" % trace_id)

    return {
        "id": case_id,
        "mode": mode,
        "notes": record["question"],
        # the trace stored these redacted, so the notes carry none of them and a
        # summary that states one has made it up
        "claim_number": None,
        "date_of_loss": None,
        "excess": None,
        "pinned_chunks": [r["chunk_id"] for r in sorted(record["retrieved"],
                                                         key=lambda r: r["rank"])],
        "source_trace": trace_id,
        "trace_output": record["raw_output"],
    }


def load():
    return written() + [regression(*r) for r in REGRESSIONS]


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    rows = load()
    print("%d cases\n" % len(rows))
    for mode, name in MODES.items():
        ids = [c["id"] for c in rows if c["mode"] == mode]
        print("  %d %-28s %d  %s" % (mode, name, len(ids), " ".join(ids)))
    print("\nregression cases replayed from Week 5 traces:")
    for c in rows:
        if c.get("source_trace"):
            print("  %s <- %s  %s" % (c["id"], c["source_trace"], c["notes"][:60]))
