"""Prove the trace plumbing works without spending a single model call.

The model is stubbed, so the answers produced here are meaningless and are
written to a scratch file that is deleted afterwards. Nothing this file produces
goes near traces/traces.jsonl or near the taxonomy. What it checks is only
mechanical: that redaction fires before the write, that the sample is
reproducible from a seed, and that a trace carries enough to be rebuilt.
"""
import os
import sys
import tempfile

import trace as tracer
import assistant
import sample
import replay

PII = ("Mrs. Eleanor Whitfield, CLM-2024-88431, reachable on (555) 271-0043 or "
       "eleanor.w@example.com at 14 Maple Street. Burst supply line, away three "
       "weeks. Does E-17 apply?")

CLEAN = ["Under HO-0304 what counts as sudden and accidental?",
         "What is the per loss event limit on the water backup form?",
         "How often does the insured have to test the sump pump?",
         "Does E-18 have any exception at all?",
         "What is cosmetic damage under HO-0415?"]


def stub(system, user, params=None, model=None):
    """Deterministic fake answer that echoes the first chunk id it was given."""
    first = user.split("[", 1)[1].split("]", 1)[0]
    # the bare "Eleanor" is the case a two-word name rule cannot see on its own,
    # and it is exactly how the real model echoed a claimant back at us
    return ("Stubbed reply for self-test only, which Eleanor reported [%s]." % first,
            "Stubbed reasoning mentioning Whitfield and claim CLM-2024-88431.")


def redact_check(text):
    """True when text passes through the redactor untouched."""
    from redact import redact
    return redact(text)[0] == text


def ok(label, condition, detail=""):
    print("  %-4s %s%s" % ("PASS" if condition else "FAIL", label,
                           (" - " + detail) if detail else ""))
    return bool(condition)


def main():
    real_call = assistant.call_model
    assistant.call_model = stub
    scratch = os.path.join(tempfile.mkdtemp(), "selftest.jsonl")
    passed = []

    try:
        print("1. redaction runs before the write")
        rec = assistant.answer(PII, path=scratch, extra={"source": "selftest"})
        passed.append(ok("claimant name gone", "Whitfield" not in rec["question"]))
        passed.append(ok("claim number gone", "88431" not in rec["question"]))
        passed.append(ok("phone gone", "271-0043" not in rec["question"]))
        passed.append(ok("email gone", "example.com" not in rec["question"]))
        passed.append(ok("counts recorded", rec["redactions"], str(rec["redactions"])))

        # the stub deliberately puts a name and a claim number in the model's
        # scratchpad, because that field leaks just as easily as the question
        passed.append(ok("scratchpad redacted too", "Whitfield" not in rec["reasoning"]))
        passed.append(ok("echoed bare first name caught",
                         "Eleanor" not in rec["raw_output"],
                         "one-word echo of a two-word name"))

        raw = open(scratch, encoding="utf-8").read()
        passed.append(ok("nothing raw ever hit disk",
                         all(s not in raw for s in
                             ("Eleanor", "Whitfield", "88431", "271-0043", "eleanor.w"))))
        passed.append(ok("policy vocabulary survived", "E-17" in rec["question"]))
        passed.append(ok("endorsement titles not mistaken for names",
                         redact_check("Water Backup and Sump Discharge Coverage"),
                         "corpus-derived stoplist"))

        print("\n2. every field replay needs is present")
        for field in ("trace_id", "prompt_version", "prompt_sha", "corpus_sha",
                      "model", "params", "retrieved", "raw_output", "retriever", "k"):
            passed.append(ok(field, field in rec and rec[field] not in (None, "", [])))
        passed.append(ok("chunk ids carry scores",
                         all("score" in r and "rank" in r for r in rec["retrieved"])))

        print("\n3. the writer refuses to be bypassed")
        try:
            tracer.write({"trace_id": "bad", "question": "claim CLM-2024-99999",
                          "raw_output": ""}, path=scratch + ".never")
            leaked = open(scratch + ".never", encoding="utf-8").read()
            passed.append(ok("identifier cannot reach disk", "99999" not in leaked,
                             "redacted on the way in"))
        except AssertionError:
            passed.append(ok("identifier cannot reach disk", True, "raised"))

        print("\n4. sampling is reproducible from the seed")
        for q in CLEAN:
            assistant.answer(q, path=scratch, extra={"source": "selftest"})
        a, _ = sample.draw(scratch, seed=20250907, n=3)
        b, _ = sample.draw(scratch, seed=20250907, n=3)
        c, _ = sample.draw(scratch, seed=999, n=3)
        ids = lambda rows: [r["trace_id"] for r in rows]
        passed.append(ok("same seed, same draw", ids(a) == ids(b)))
        passed.append(ok("different seed, different draw", ids(a) != ids(c)))

        print("\n5. a trace rebuilds into the same context it was answered from")
        rebuilt = replay.rebuild_context(rec)
        for row in rec["retrieved"]:
            passed.append(ok("chunk %s back in context" % row["chunk_id"],
                             ("[%s]" % row["chunk_id"]) in rebuilt))
        passed.append(ok("no drift guard trips", replay.check(rec) == [],
                         "corpus and prompt match"))

    finally:
        assistant.call_model = real_call
        for path in (scratch, scratch + ".never"):
            if os.path.exists(path):
                os.remove(path)

    print("\n%d/%d checks passed" % (sum(passed), len(passed)))
    return 0 if all(passed) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
