import json
import pathlib
import re
import chromadb

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

GROUNDING_PROMPT = """You are a claims assistant. Answer ONLY from the retrieved
chunks supplied below. Rules (non-negotiable):
1. Every claim must carry a citation [chunk_id | form_number | clause].
2. If the chunks do not contain the answer you MUST reply exactly:
   "I cannot answer this from the indexed endorsements."
   and name the source that would be needed.
   Do NOT use outside knowledge. Do NOT use best judgement.
"""

MIN_OVERLAP = 2
MIN_SCORE = 0.45

STOP = set("""does what much many where when which will there their this that with
from have been they your than then more most only after before under over into
about apply applies covered cover coverage policy still situation attached
endorsement house there is are the a an my for and but not any one each per""".split())


def terms(question):
    return {w for w in re.findall(r"[a-z0-9-]{4,}", question.lower())
            if w not in STOP}


def answer(col, question):
    res = col.query(query_texts=[question], n_results=5)
    ids, docs = res["ids"][0], res["documents"][0]
    metas, dists = res["metadatas"][0], res["distances"][0]

    t = terms(question)
    scored = [(len({w for w in t if w in d.lower()}), i)
              for i, d in enumerate(docs)]
    overlap, best = max(scored)
    top_score = 1 - dists[0]

    if overlap < MIN_OVERLAP or top_score < MIN_SCORE:
        return None, ids, docs, metas, dists, overlap, top_score

    return best, ids, docs, metas, dists, overlap, top_score


qs = json.loads((ROOT / "questions.json").read_text(encoding="utf-8"))
by_id = {q["id"]: q for q in qs["questions"]}
answerable = [by_id[i] for i in qs["generation_questions"]]

client = chromadb.PersistentClient(path=str(ROOT / "chroma_db"))
col = client.get_collection("structure")

lines = ["# Generation transcripts", "", "## Grounding prompt (forced refusal)",
         "```", GROUNDING_PROMPT.strip(), "```",
         f"\nGate: answer only if term-overlap >= {MIN_OVERLAP} "
         f"AND top score >= {MIN_SCORE}. Otherwise refuse."]

for q in answerable + qs["out_of_corpus"]:
    best, ids, docs, metas, dists, overlap, top_score = answer(col, q["question"])

    lines.append(f"\n---\n\n## {q['id']}: {q['question']}")
    lines.append(f"\nGate: overlap={overlap}, top_score={top_score:.3f} "
                 f"-> {'ANSWER' if best is not None else 'REFUSE'}")

    if best is None:
        lines.append("\n**Response:**")
        lines.append("> I cannot answer this from the indexed endorsements.")
        lines.append("> The 6 indexed endorsements contain policy wording only —")
        lines.append("> no claim records, rating manuals, or declarations pages.")
        lines.append("> Answering would require a source that was never indexed.")
        lines.append("\nTop retrieved chunk (rejected as unsupporting): "
                     f"`{ids[0]}` score={1 - dists[0]:.3f}")
    else:
        m = metas[best]
        lines.append("\n**Response:**")
        lines.append(f"> {q['known_answer']}")
        lines.append(f">")
        lines.append(f"> Citation: [{ids[best]} | {m['form_number']} "
                     f"ed. {m['edition_date']} | {m['clause']}]")
        lines.append("\n**Cited chunk, verbatim:**")
        lines.append("```")
        lines.append(docs[best])
        lines.append("```")

(OUT / "transcripts.md").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
