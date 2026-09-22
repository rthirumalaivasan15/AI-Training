import os
import re
import json

DATA_DIR = "data"
OUT_FILE = "chunks.jsonl"
CHUNK_SIZE = 250   # clause level - one exclusion row per chunk


def parse_header(text):
    def field(label):
        found = re.search(label + r":\s*(.+)", text)
        return found.group(1).strip() if found else ""

    return {
        "form_number": field("FORM NUMBER"),
        "edition": field("EDITION"),
        "policy_line": field("POLICY LINE"),
        "edition_date": field("EFFECTIVE DATE"),
        "title": field("TITLE"),
    }


def chunk_text(text, size):
    # split on blank lines, then pack paragraphs together until we hit the size
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for p in paras:
        if current and len(current) + len(p) > size:
            chunks.append(current)
            current = p
        else:
            current = current + "\n\n" + p if current else p
    if current:
        chunks.append(current)
    return chunks


def build(size=CHUNK_SIZE):
    rows = []
    for name in sorted(os.listdir(DATA_DIR)):
        if not name.endswith(".txt"):
            continue
        path = os.path.join(DATA_DIR, name)
        with open(path, encoding="utf-8") as f:
            text = f.read()

        meta = parse_header(text)
        for i, body in enumerate(chunk_text(text, size)):
            rows.append({
                "chunk_id": "%s_%s#%02d" % (meta["form_number"], meta["edition"], i),
                "text": body,
                "source_file": name,
                **meta,
            })
    return rows


if __name__ == "__main__":
    rows = build()
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    print("%d chunks from %d files" % (len(rows), len(set(r["source_file"] for r in rows))))
    for r in rows:
        head = r["text"].split("\n")[0][:60]
        print("  %-18s %-14s %s" % (r["chunk_id"], r["policy_line"], head))
