import re


def parse_header(text, source_file):
    def grab(field):
        m = re.search(rf"^{field}:\s*(.+)$", text, re.MULTILINE)
        if not m:
            raise ValueError(f"{source_file}: missing {field}")
        return m.group(1).strip()

    return {
        "source_file": source_file,
        "form_number": grab("FORM NUMBER"),
        "policy_line": grab("POLICY LINE"),
        "edition_date": grab("EDITION"),
    }

def structure_chunks(text, meta):
    chunks = []
    form_tag = f"FORM {meta['form_number']} ed. {meta['edition_date']}"

    parts = re.split(r"(?m)^(?=CLAUSE\s+\d)", text)
    head, clauses = parts[0], parts[1:]

    chunks.append({"text": head.strip(), "clause": "header"})

    for clause in clauses:
        title = clause.splitlines()[0].strip()
        rows = [ln for ln in clause.splitlines() if re.match(r"^\|\s*E-\d+", ln)]

        if rows:
            header_row = next(ln for ln in clause.splitlines()
                              if ln.startswith("| Code"))
            intro = clause[:clause.index(header_row)].strip()
            for row in rows:
                code = re.match(r"^\|\s*(E-\d+)", row).group(1)
                chunks.append({
                    "text": f"{form_tag}\n{intro}\n{header_row}\n{row.strip()}",
                    "clause": f"{title} row {code}",
                })
        else:
            chunks.append({"text": f"{form_tag}\n{clause.strip()}",
                           "clause": title})

    return chunks


def naive_chunks(text, size=400, overlap=50):
    chunks = []
    step = size - overlap
    i = 0
    while i < len(text):
        piece = text[i:i + size].strip()
        if piece:
            chunks.append(piece)
        i += step
    return chunks
