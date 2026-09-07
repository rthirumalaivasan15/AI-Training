"""Re-run one trace using only what the trace itself records.

    python replay.py trc_ab12cd34ef56

Nothing here reaches back into the live retriever. The chunk ids in the trace are
looked up in the pinned corpus, the prompt is looked up by its recorded version,
and the model and params come off the trace. If the corpus or the prompt has
moved underneath the trace, replay says so and stops rather than comparing two
answers that were produced from different inputs.
"""
import sys
import difflib

import prompts
import trace as tracer
import assistant
from index import load_chunks, META_FIELDS

_by_id = {r["chunk_id"]: r for r in load_chunks()}


def rebuild_context(record):
    """Rebuild the exact context block from chunk ids, in the recorded rank order."""
    hits = []
    for row in sorted(record["retrieved"], key=lambda r: r["rank"]):
        chunk = _by_id.get(row["chunk_id"])
        if chunk is None:
            raise KeyError("chunk %s is in the trace but not in the corpus"
                           % row["chunk_id"])
        hits.append({"chunk_id": chunk["chunk_id"], "text": chunk["text"],
                     "meta": {f: chunk[f] for f in META_FIELDS}})
    return assistant.build_context(hits)


def check(record):
    """Return a list of problems that would make the replay meaningless."""
    problems = []
    live_corpus = tracer.corpus_fingerprint()
    if record.get("corpus_sha") != live_corpus:
        problems.append("corpus moved: trace %s, now %s"
                        % (record.get("corpus_sha"), live_corpus))
    try:
        live_prompt = prompts.sha(record["prompt_version"])
        if record.get("prompt_sha") != live_prompt:
            problems.append("prompt %s edited: trace %s, now %s"
                            % (record["prompt_version"], record.get("prompt_sha"),
                               live_prompt))
    except KeyError as exc:
        problems.append(str(exc))
    return problems


def replay(trace_id, path=tracer.TRACE_FILE):
    record = tracer.by_id(trace_id, path)

    for problem in check(record):
        print("REFUSING TO REPLAY -", problem)
        return None

    if record["refused_by"] == "score floor":
        # no model call was made, so there is nothing to re-run - the trace
        # records that the guard fired before the question ever reached the model
        replayed = assistant.REFUSAL
    else:
        replayed, _ = assistant.call_model(
            prompts.get(record["prompt_version"]),
            "Context:\n\n%s\n\nQuestion: %s" % (rebuild_context(record),
                                                record["question"]),
            params=record["params"],
            model=record["model"],
        )
    return record, replayed


def report(trace_id, path=tracer.TRACE_FILE):
    out = replay(trace_id, path)
    if out is None:
        return
    record, replayed = out

    print("trace_id       :", record["trace_id"])
    print("written        :", record["ts"])
    print("question       :", record["question"])
    print("retriever / k  : %s / %d" % (record["retriever"], record["k"]))
    print("chunks + scores: " + ", ".join("%s %.4f" % (r["chunk_id"], r["score"])
                                          for r in record["retrieved"]))
    print("model          :", record["model"])
    print("params         :", record["params"])
    print("prompt         : %s (sha %s)" % (record["prompt_version"], record["prompt_sha"]))
    print("refused_by     :", record["refused_by"])

    print("\n--- ORIGINAL (from the trace) " + "-" * 42)
    print(record["raw_output"])
    print("\n--- REPLAYED (rebuilt from the trace alone) " + "-" * 28)
    print(replayed)

    same = replayed.strip() == record["raw_output"].strip()
    print("\nidentical: %s" % ("YES" if same else "NO"))
    if not same:
        print("\nunified diff, original -> replayed:")
        for line in difflib.unified_diff(record["raw_output"].splitlines(),
                                         replayed.splitlines(),
                                         "original", "replayed", lineterm="", n=1):
            print("  " + line)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        raise SystemExit("usage: python replay.py <trace_id> [trace_file]")
    report(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else tracer.TRACE_FILE)
