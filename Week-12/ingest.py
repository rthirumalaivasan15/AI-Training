"""Chunk the endorsement library - every edition of every form - into chunks.jsonl.

    python ingest.py

Clause-level chunks (the Week 4 chunker, unchanged: blank-line paragraphs packed to
~250 characters). Week 12 adds three things to every chunk's metadata:

- in_force_from / in_force_to (YYYYMMDD ints): the edition is in force from its own
  EFFECTIVE DATE until the day before the next edition of the same form takes effect
  (open-ended for the latest). This is what lets retrieval be resolved against a loss
  date in code instead of by whichever edition reads best.
- line_start: the line in the source file where the chunk begins, so a citation can
  link to the clause itself.
- the chunk id carries the edition: HO-0304_03-24#05 and HO-0304_01-25#05 are
  different clauses of different wordings, and a citation names which.
"""
import os
import re
import json
import datetime

DATA_DIR = "data"
OUT_FILE = "chunks.jsonl"
CHUNK_SIZE = 250
OPEN_END = 99991231


def parse_header(text):
    def field(label):
        found = re.search(label + r":\s*(.+)", text)
        return found.group(1).strip() if found else ""
    return {"form_number": field("FORM NUMBER"), "edition": field("EDITION"),
            "policy_line": field("POLICY LINE"), "edition_date": field("EFFECTIVE DATE"),
            "title": field("TITLE")}


def chunk_text(text, size):
    """Paragraph packing, returning (chunk, line number where it starts)."""
    lines = text.split("\n")
    paras, start, buf = [], None, []
    for i, line in enumerate(lines, 1):
        if line.strip():
            if not buf:
                start = i
            buf.append(line)
        elif buf:
            paras.append(("\n".join(buf).strip(), start))
            buf = []
    if buf:
        paras.append(("\n".join(buf).strip(), start))
    chunks, current, cur_start = [], "", None
    for p, line in paras:
        if current and len(current) + len(p) > size:
            chunks.append((current, cur_start))
            current, cur_start = p, line
        else:
            current, cur_start = (current + "\n\n" + p, cur_start) if current else (p, line)
    if current:
        chunks.append((current, cur_start))
    return chunks


def as_int(date_text):
    return int(date_text.replace("-", ""))


def build(size=CHUNK_SIZE):
    docs = []
    for name in sorted(os.listdir(DATA_DIR)):
        if name.endswith(".txt"):
            with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
                text = f.read()
            docs.append((name, text, parse_header(text)))

    # in-force window per edition: until the day before the next edition of the same form
    ranges = {}
    for form in {m["form_number"] for _, _, m in docs}:
        eds = sorted((m for _, _, m in docs if m["form_number"] == form), key=lambda m: m["edition_date"])
        for i, m in enumerate(eds):
            nxt = eds[i + 1]["edition_date"] if i + 1 < len(eds) else None
            end = (datetime.date.fromisoformat(nxt) - datetime.timedelta(days=1)).isoformat() if nxt else None
            ranges[(form, m["edition"])] = (as_int(m["edition_date"]), as_int(end) if end else OPEN_END)

    rows = []
    for name, text, meta in docs:
        lo, hi = ranges[(meta["form_number"], meta["edition"])]
        for i, (body, line) in enumerate(chunk_text(text, size)):
            rows.append({"chunk_id": "%s_%s#%02d" % (meta["form_number"], meta["edition"], i),
                         "text": body, "source_file": name, "line_start": line,
                         "in_force_from": lo, "in_force_to": hi, **meta})
    return rows


if __name__ == "__main__":
    rows = build()
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print("%d chunks from %d files" % (len(rows), len({r["source_file"] for r in rows})))
    for (form, ed) in sorted({(r["form_number"], r["edition"]) for r in rows}):
        r = next(x for x in rows if x["form_number"] == form and x["edition"] == ed)
        print("  %s ed. %s  in force %s .. %s" % (form, ed, r["in_force_from"], r["in_force_to"]))
