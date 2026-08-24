# Code diff — baseline pipeline vs structure-aware pipeline

Baseline = naive fixed-size chunker, metadata limited to source_file + form_number.
Final    = adds the structure-aware chunker, the full metadata set, and dual indexing.

```diff
--- a/src/chunkers.py
+++ b/src/chunkers.py
@@ -1,24 +1,57 @@
-import re
-
-
-def parse_header(text, source_file):
-    def grab(field):
-        m = re.search(rf"^{field}:\s*(.+)$", text, re.MULTILINE)
-        return m.group(1).strip() if m else ""
-
-    return {
-        "source_file": source_file,
-        "form_number": grab("FORM NUMBER"),
-    }
-
-
-def naive_chunks(text, size=400, overlap=50):
-    chunks = []
-    step = size - overlap
-    i = 0
-    while i < len(text):
-        piece = text[i:i + size].strip()
-        if piece:
-            chunks.append(piece)
-        i += step
-    return chunks
+import re
+
+
+def parse_header(text, source_file):
+    def grab(field):
+        m = re.search(rf"^{field}:\s*(.+)$", text, re.MULTILINE)
+        if not m:
+            raise ValueError(f"{source_file}: missing {field}")
+        return m.group(1).strip()
+
+    return {
+        "source_file": source_file,
+        "form_number": grab("FORM NUMBER"),
+        "policy_line": grab("POLICY LINE"),
+        "edition_date": grab("EDITION"),
+    }
+
+def structure_chunks(text, meta):
+    chunks = []
+    form_tag = f"FORM {meta['form_number']} ed. {meta['edition_date']}"
+
+    parts = re.split(r"(?m)^(?=CLAUSE\s+\d)", text)
+    head, clauses = parts[0], parts[1:]
+
+    chunks.append({"text": head.strip(), "clause": "header"})
+
+    for clause in clauses:
+        title = clause.splitlines()[0].strip()
+        rows = [ln for ln in clause.splitlines() if re.match(r"^\|\s*E-\d+", ln)]
+
+        if rows:
+            header_row = next(ln for ln in clause.splitlines()
+                              if ln.startswith("| Code"))
+            intro = clause[:clause.index(header_row)].strip()
+            for row in rows:
+                code = re.match(r"^\|\s*(E-\d+)", row).group(1)
+                chunks.append({
+                    "text": f"{form_tag}\n{intro}\n{header_row}\n{row.strip()}",
+                    "clause": f"{title} row {code}",
+                })
+        else:
+            chunks.append({"text": f"{form_tag}\n{clause.strip()}",
+                           "clause": title})
+
+    return chunks
+
+
+def naive_chunks(text, size=400, overlap=50):
+    chunks = []
+    step = size - overlap
+    i = 0
+    while i < len(text):
+        piece = text[i:i + size].strip()
+        if piece:
+            chunks.append(piece)
+        i += step
+    return chunks
--- a/src/ingest.py
+++ b/src/ingest.py
@@ -1,29 +1,42 @@
-import pathlib
-import chromadb
-from chunkers import parse_header, naive_chunks
-
-ROOT = pathlib.Path(__file__).resolve().parents[1]
-DATA = ROOT / "data" / "endorsements"
-
-client = chromadb.PersistentClient(path=str(ROOT / "chroma_db"))
-
-try:
-    client.delete_collection("naive")
-except Exception:
-    pass
-col = client.create_collection("naive", metadata={"hnsw:space": "cosine"})
-
-total = 0
-for f in sorted(DATA.glob("*.txt")):
-    text = f.read_text(encoding="utf-8")
-    meta = parse_header(text, f.name)
-    pieces = naive_chunks(text)
-
-    ids = [f"naive:{meta['form_number']}:{n:03d}" for n in range(len(pieces))]
-    metas = [dict(meta) for _ in pieces]
-
-    col.add(ids=ids, documents=pieces, metadatas=metas)
-    total += len(pieces)
-    print(f"{f.name}: {len(pieces)} chunks")
-
-print(f"\nindexed {total} chunks total")
+import pathlib
+import chromadb
+from chunkers import parse_header, naive_chunks, structure_chunks
+
+ROOT = pathlib.Path(__file__).resolve().parents[1]
+DATA = ROOT / "data" / "endorsements"
+
+client = chromadb.PersistentClient(path=str(ROOT / "chroma_db"))
+
+for name in ("naive", "structure"):
+    try:
+        client.delete_collection(name)
+    except Exception:
+        pass
+
+naive_col = client.create_collection("naive", metadata={"hnsw:space": "cosine"})
+struct_col = client.create_collection("structure", metadata={"hnsw:space": "cosine"})
+
+n_total = s_total = 0
+for f in sorted(DATA.glob("*.txt")):
+    text = f.read_text(encoding="utf-8")
+    meta = parse_header(text, f.name)
+
+    pieces = naive_chunks(text)
+    naive_col.add(
+        ids=[f"naive:{meta['form_number']}:{n:03d}" for n in range(len(pieces))],
+        documents=pieces,
+        metadatas=[dict(meta, chunker="naive", clause="") for _ in pieces],
+    )
+    n_total += len(pieces)
+
+    sc = structure_chunks(text, meta)
+    struct_col.add(
+        ids=[f"struct:{meta['form_number']}:{n:03d}" for n in range(len(sc))],
+        documents=[c["text"] for c in sc],
+        metadatas=[dict(meta, chunker="structure", clause=c["clause"]) for c in sc],
+    )
+    s_total += len(sc)
+
+    print(f"{f.name}: naive={len(pieces)}  structure={len(sc)}")
+
+print(f"\nnaive total={n_total}   structure total={s_total}")
```
