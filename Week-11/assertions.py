"""The four criteria that used to be inside the judge and never needed a model.

Each was criterion 1-4 of judge_v0.txt. A regex does them for nothing, the same
way every time, and says which field failed. They were deleted from the judge
when these went in - judge_v1.txt checks one thing only.

    claim_number        CLAIM NUMBER echoes the notes exactly, in CLM-YYYY-NNNNN form
    date_of_loss        DATE OF LOSS parses as YYYY-MM-DD and is the date in the notes
    excess_numeric      EXCESS is digits only, and matches the notes when they give one
    grounds_on_denial   a DENIED or PARTIAL position cites an exclusion code that exists
                        in the endorsements, or a numbered clause of a named form

Where the notes do not carry a fact, the only passing value is NOT STATED. A
summary that fills one in has invented it.

On grounds_on_denial: the brief asks for an exclusion id whenever a denial is
stated. A named clause is also accepted, because some correct denials rest on no
exclusion at all - HO-0612 pays only the code minimum under Clause 3, and there is
no E-code for "the upgrade is not a covered cost". Whether the cited ground is the
RIGHT one is not a regex question; that is the judge's criterion.
"""
import re
import datetime
from index import load_chunks

FIELD_NAMES = ("CLAIM NUMBER", "DATE OF LOSS", "POLICY FORMS", "LOSS", "COVERAGE POSITION",
               "GROUNDS", "EXCESS", "REASONING", "NEXT STEP")
NOT_STATED = "NOT STATED"

CLAIM = re.compile(r"CLM-\d{4}-\d{5}")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
CODE = re.compile(r"\bE-\d{2}\b")
CLAUSE = re.compile(r"\b[A-Z]{2}-\d{4}\s+Clause\s+\d+", re.I)

# gpt-oss writes E-17 with a non-breaking hyphen (U+2011). For finding an exclusion
# code that is still E-17. For a claim number it is not - a claims system lookup on
# CLM‑2024‑20011 finds nothing - so claim_number stays strict.
HYPHENS = re.compile("[‐‑‒–—−]")

KNOWN_CODES = set(CODE.findall(" ".join(r["text"] for r in load_chunks())))


def fields(summary):
    out = {}
    for line in (summary or "").splitlines():
        key, sep, value = line.partition(":")
        key = key.strip().strip("*").strip().upper()
        if sep and key in FIELD_NAMES and key not in out:
            out[key] = value.strip().strip("*").strip()
    return out


def claim_number(case, f):
    got, want = f.get("CLAIM NUMBER"), case.get("claim_number")
    if got is None:
        return False, "no CLAIM NUMBER line"
    if want is None:
        return got == NOT_STATED, "notes carry no claim number, summary says %r" % got
    if not CLAIM.fullmatch(got):
        return False, "%r is not in CLM-YYYY-NNNNN form%s" % (
            got, " (non-ASCII hyphen)" if HYPHENS.search(got) else "")
    return got == want, "notes %s, summary %s" % (want, got)


def date_of_loss(case, f):
    got, want = f.get("DATE OF LOSS"), case.get("date_of_loss")
    if got is None:
        return False, "no DATE OF LOSS line"
    if want is None:
        return got == NOT_STATED, "notes carry no date, summary says %r" % got
    if not ISO_DATE.fullmatch(got):
        return False, "%r is not YYYY-MM-DD" % got
    try:
        parsed = datetime.date.fromisoformat(got)
    except ValueError:
        return False, "%r is not a real date" % got
    return parsed.isoformat() == want, "notes %s, summary %s" % (want, got)


def excess_numeric(case, f):
    got, want = f.get("EXCESS"), case.get("excess")
    if got is None:
        return False, "no EXCESS line"
    if got == NOT_STATED:
        return want is None, ("notes give %d, summary says NOT STATED" % want) if want else "not in notes"
    if not re.fullmatch(r"\d+", got):
        return False, "%r is not a plain number" % got
    if want is not None and int(got) != want:
        return False, "notes %d, summary %s" % (want, got)
    return True, got


def grounds_on_denial(case, f):
    position = f.get("COVERAGE POSITION", "").upper()
    if position not in ("DENIED", "PARTIAL"):
        return True, "no denial stated (%s)" % (position or "no position")
    grounds = HYPHENS.sub("-", f.get("GROUNDS", ""))
    codes = set(CODE.findall(grounds))
    unknown = codes - KNOWN_CODES
    if unknown:
        return False, "cites %s, which no endorsement contains" % ", ".join(sorted(unknown))
    if codes or CLAUSE.search(grounds):
        return True, grounds
    return False, "%s with no exclusion code or clause in GROUNDS (%r)" % (position, grounds)


ASSERTIONS = [
    ("claim_number", claim_number),
    ("date_of_loss", date_of_loss),
    ("excess_numeric", excess_numeric),
    ("grounds_on_denial", grounds_on_denial),
]


def run(case, summary):
    f = fields(summary)
    out = []
    for name, check in ASSERTIONS:
        passed, detail = check(case, f)
        out.append({"name": name, "passed": bool(passed), "detail": detail})
    return out
