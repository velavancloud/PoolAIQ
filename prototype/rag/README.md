# RAG Layer

Real, working retrieval-augmented generation — not the placeholder that was
here before (a hardcoded Python list passed directly to the reasoning
engine). See `README.md` Section 3a at the project root for the full design
rationale and honestly-stated limitations.

## Files

- `knowledge_base.py` — seed corpus of 15 general pool chemistry facts,
  distinct from any specific pool's history
- `embed_store.py` — `RetrievalIndex` class: TF-IDF + cosine similarity
  retrieval over two separate corpora (knowledge base, pool history),
  queryable independently so results can be attributed by source

## Why TF-IDF, not a neural embedding model

Tested `sentence-transformers` during development — it requires downloading
a model from huggingface.co at runtime, which failed in this project's
sandboxed dev environment (network whitelist didn't include huggingface.co)
and would be a fragile dependency for a live demo on unknown wifi. TF-IDF has
zero network dependency after `pip install scikit-learn` and is a real,
standard retrieval technique — just not a neural one. The tradeoff (lexical
vs. semantic matching) is documented in the root README, and confirmed via
a real test case where it under-performs (see "Known limitations" there).

## Run the retrieval demo standalone

```bash
cd prototype/rag
python3 embed_store.py
```

This builds an index over the real case-study history + knowledge base and
runs a sample query ("pH keeps going high after I add acid"), printing the
top matches from both corpora with similarity scores.

## How it's wired into the reasoning engine

`reasoning_engine.py`'s `recommend()` function:
1. Builds a query from the pool's *current* out-of-range metrics
   (`build_query_from_state()`) — not a generic query, one grounded in
   what's actually happening right now
2. Retrieves top-3 KB entries + top-3 historical readings
3. Passes both through as `retrieved_context_used` in every branch of the
   output, matching the schema already specified in
   `../../prompts/reasoning_prompt.md`
4. When a hard-coded pattern detector (e.g. the alkalinity/pH coupling
   check) fires, it does an *additional* targeted lookup for its specific
   supporting KB entry by ID — not relying on top-k rank alone, since
   safety-relevant citations shouldn't depend on retrieval ranking quality
