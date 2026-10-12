# Week 1 — How a Language Model Actually Works

Module 1 · Foundations · theory only

Topics: language models · tokens and tokenization · cost per token · context window ·
word embeddings (Word2Vec, GloVe) · static vs contextual embeddings · temperature and
sampling (top-p, top-k) · greedy vs sampled decoding · model families · decoder vs
encoder models · hallucination

---

### Q1. What is a large language model, in plain terms — and what is it not?

A neural network trained on a very large amount of text to do one thing: given a
sequence of tokens, give a probability to every possible next token. Generation is that
step in a loop — pick a token, append it, predict again — until a stop token. Answering,
summarising and writing code all come out of this one mechanism.

What it is **not**:
- **Not a database.** Facts are spread across weights as statistical tendencies, not
  stored in rows, so recall is approximate.
- **Not a search engine.** It knows its training data up to a cutoff, plus whatever is
  in the prompt. Nothing else.
- **Not a checked reasoner.** It produces reasoning-shaped text; nothing inside verifies
  the conclusion.

So any application that needs correct, current or private facts has to supply them
(retrieval, tools) and check the output.

### Q2. What is a token, and how does tokenization work?

A token is the unit the model reads and writes — usually a sub-word piece. Most modern
models use **byte-pair encoding (BPE)** or a close relative: start from bytes or
characters and repeatedly merge the most frequent adjacent pair into a new vocabulary
entry, until the vocabulary reaches a fixed size (tens of thousands to a few hundred
thousand entries). Common words end up as one token; rare words, codes and names are
split into several.

Rules of thumb for English: one token ≈ 3–4 characters ≈ ¾ of a word. Code, JSON,
numbers, IDs and most non-English languages take **more** tokens for the same meaning.
Each model family has its own tokenizer, so the same text has different token counts on
different models — always count with the model's own tokenizer.

### Q3. How do you work out what an LLM call costs, and why is the real bill usually higher than one call's price?

```
cost = (input_tokens × input_price + output_tokens × output_price) / 1,000,000
```

with prices quoted per million tokens. Output tokens usually cost **3–5× more** than
input, because input is processed in one parallel pass while output is generated one
token at a time.

The real bill is higher because one user request is often **many calls**. An agent
re-sends the whole growing conversation on every step, so its cost is the *sum over every
lap*, not the last call. Quoting one call's cost under-reports an agent badly.

**In this project:** Week 7 measured an agent's per-lap tokens growing
853 → ~1,150 → ~1,900 → ~2,100 over four laps; the last call alone would have shown
about a third of the true total. The cost formula lives in `llm.py`.

### Q4. What is the context window, and what happens when you run out of it?

The maximum number of tokens the model can consider at once — instructions, documents,
chat history, tool results **and** the answer all share it. If the input is too long the
API rejects the request, or your code has to drop or truncate something; if the output
budget is too small the answer is cut off (`finish_reason = "length"`).

Two practical points:
- **Bigger is not free.** Every token in the window is paid for on every call, and
  latency grows with input length.
- **Long contexts are used unevenly.** Models are often worse at using facts buried in
  the middle of a long context than at the start or end ("lost in the middle"), so
  retrieving the right 3 passages usually beats pasting 300.

### Q5. How do Word2Vec and GloVe produce word embeddings?

Both learn one fixed vector per word from co-occurrence in a large corpus, so that words
used in similar contexts get similar vectors.

- **Word2Vec** trains a shallow network on a prediction task: *skip-gram* predicts the
  surrounding words from a word; *CBOW* predicts a word from its surroundings. The
  learned weights are the embeddings. Negative sampling keeps training cheap.
- **GloVe** ("Global Vectors") starts from a global word–word co-occurrence matrix over
  the whole corpus and fits vectors so their dot product approximates the log of the
  co-occurrence counts.

Both give the famous vector arithmetic (king − man + woman ≈ queen). Both are **static**:
one vector per word, regardless of context (see Q6).

### Q6. What is the difference between static and contextual embeddings?

- **Static** (Word2Vec, GloVe): each word has exactly one vector. "Bank" in "river bank"
  and "bank account" gets the same vector, so meaning that depends on context is lost.
- **Contextual** (transformer models such as BERT and modern embedding models): the vector
  for each token is computed from the whole sentence through attention, so the two
  "bank"s get different vectors. Sentence/passage embedding models pool these token
  vectors into one vector for the whole text.

RAG uses contextual sentence embeddings: you embed a whole chunk, and similar *meanings*
land close together even with different words.

### Q7. What do temperature, top-k and top-p do?

They all shape how the next token is **sampled** from the model's probability
distribution.

- **Temperature** rescales the distribution. Near 0 it becomes sharp — the top token
  almost always wins (focused, repeatable). Above 1 it flattens — unlikely tokens get a
  real chance (varied, more drift).
- **Top-k** keeps only the k most likely tokens and samples among them.
- **Top-p (nucleus)** keeps the smallest set of tokens whose probabilities add up to p
  (e.g. 0.9) — a cut-off that adapts to how confident the model is.

Use low temperature for extraction, classification, JSON, code, grounded Q&A and above all
**evaluation** (randomness hides whether a change helped). Use higher values for
brainstorming and generating varied test cases. None of these settings changes what the
model knows.

### Q8. Greedy vs sampled decoding — and does temperature 0 guarantee identical output?

**Greedy** decoding always takes the most probable token (what temperature 0 approximates).
**Sampled** decoding draws from the distribution (shaped by temperature/top-k/top-p).
Greedy is repeatable but can be dull or loop; sampling is varied but less predictable.

Temperature 0 is **not a guarantee** of identical output. GPU floating-point
non-determinism (batching, parallel reduction order) can flip a near-tie between two
tokens, and once one token differs the rest of the text diverges. Providers also change
models and hardware. Design for "mostly stable": log every real output rather than
assuming you can regenerate it, and judge changes over many cases, not one run.

**In this project:** every run since Week 7 uses temperature 0 and still logs the full
output of every case, because a re-run is not the same evidence.

### Q9. Decoder-only vs encoder-only models — what are they for, and where do the major model families fit?

- **Encoder-only** (BERT family): read the whole input in both directions and produce a
  representation of it. Good for embeddings, classification and reranking. Not built to
  generate long text.
- **Decoder-only** (GPT, Claude, LLaMA, gpt-oss): generate left to right, each token
  attending only to earlier ones. This is the architecture of today's chat models.
- **Encoder–decoder** (T5, original Transformer): encode an input, decode an output.
  Used for translation and summarisation.

Families: **GPT** (OpenAI, closed weights, API), **Claude** (Anthropic, closed weights,
API), **LLaMA** (Meta, open weights you can self-host). "Open weights" matters when data
must stay in-house or you need to fine-tune; closed APIs usually lead on capability and
need no infrastructure.

**In this project:** the chat model is `openai/gpt-oss-120b` (open weights, served by
Groq); the embedding model is `all-MiniLM-L6-v2`, a small encoder (384 dimensions).

### Q10. Why do models hallucinate, and how do you reduce it?

The model is trained to produce the most **plausible** continuation, not the true one.
When the answer isn't in its context and only weakly in its training data, a fluent,
specific-sounding guess is still the most probable text — so it guesses, confidently.

Signs: specific figures, clause numbers or citations that appear nowhere in the provided
context; confident answers outside the given material; answers that change when you
rephrase.

Reduce it by:
- supplying the facts (retrieval, tools) and instructing "answer only from the context";
- giving an explicit, machine-detectable "not found / UNDETERMINED" option;
- requiring citations and **checking them in code**;
- low temperature for factual tasks;
- measuring the hallucination rate on an eval set rather than trusting the prompt.
