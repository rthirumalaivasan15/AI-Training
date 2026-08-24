import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "endorsements"

qs = json.loads((ROOT / "questions.json").read_text(encoding="utf-8"))["questions"]

for q in qs:
    doc = next(f for f in DATA.glob("*.txt") if q["expected_form"] in f.name)
    text = doc.read_text(encoding="utf-8")
    ok = q["marker"] in text
    print(f"{q['id']}  {q['marker']!r:18} in {doc.name}: {'OK' if ok else 'NOT FOUND'}")

print(f"\ntable-row questions: {sum(q['table_row'] for q in qs)}  (need at least 3)")
