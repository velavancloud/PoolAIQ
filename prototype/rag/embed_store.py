"""
Embedding + retrieval index for PoolAIQ's RAG layer.

Uses TF-IDF + cosine similarity rather than a downloaded neural embedding
model. This is a deliberate choice, documented here rather than hidden:

  - No network dependency at runtime (huggingface.co and similar model hubs
    are not reachable from every environment this demo might run in —
    verified during development that this sandbox's network whitelist does
    NOT include huggingface.co, so a sentence-transformers model would fail
    silently or block the demo on an unreliable download)
  - TF-IDF is a real, standard retrieval technique (it's the "BM25-adjacent"
    half of hybrid search used in production RAG systems), not a toy
    stand-in — it's just not a neural embedding
  - The honest limitation: TF-IDF retrieves on lexical/term overlap, not
    semantic meaning — it will retrieve a KB entry about "pH" when a query
    mentions "pH" but may miss a semantically related entry that uses
    different words for the same concept. A production system should
    layer a neural embedding model (or hybrid BM25+dense retrieval) on top
    of this once network/deployment constraints allow it. This tradeoff is
    called out again in README.md Section 3a.
"""

from dataclasses import dataclass
from typing import Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


@dataclass
class RetrievedItem:
    id: str
    text: str
    score: float
    source: str          # 'knowledge_base' or 'pool_history'
    metadata: dict


class RetrievalIndex:
    """
    Holds two separate sub-indexes (KB facts, pool history readings) so
    retrieval can be run against each independently and results can be
    attributed by source — this matters for the safety/explainability
    requirement in reasoning_prompt.md (retrieved_context_used must be
    inspectable, not a black box).
    """

    def __init__(self):
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._kb_texts: list = []
        self._kb_meta: list = []
        self._history_texts: list = []
        self._history_meta: list = []
        self._matrix = None
        self._fitted = False

    def index_knowledge_base(self, entries: list):
        """entries: list of KBEntry (id, category, text)"""
        self._kb_texts = [e.text for e in entries]
        self._kb_meta = [{"id": e.id, "category": e.category} for e in entries]

    def index_pool_history(self, readings: list):
        """
        Converts each Reading object into a natural-language sentence so it
        can be embedded and retrieved alongside the KB text — this is the
        actual RAG mechanism the README's Section 3 diagram claimed:
        retrieving relevant PRIOR READINGS, not just dumping the whole list.
        """
        texts = []
        meta = []
        for r in readings:
            parts = [f"On {r.read_at.strftime('%Y-%m-%d %H:%M')} ({r.source}):"]
            if r.ph is not None:
                parts.append(f"pH was {r.ph}.")
            if r.free_chlorine_ppm is not None:
                parts.append(f"Free chlorine was {r.free_chlorine_ppm} ppm.")
            if r.total_chlorine_ppm is not None:
                parts.append(f"Total chlorine was {r.total_chlorine_ppm} ppm.")
            if r.total_alkalinity_ppm is not None:
                parts.append(f"Total alkalinity was {r.total_alkalinity_ppm} ppm.")
            if r.cyanuric_acid_ppm is not None:
                parts.append(f"Cyanuric acid was {r.cyanuric_acid_ppm} ppm.")
            if r.copper_ppm is not None:
                parts.append(f"Copper was {r.copper_ppm} ppm.")
            if r.phosphates_ppb is not None:
                parts.append(f"Phosphates were {r.phosphates_ppb} ppb.")
            if r.salt_ppm is not None:
                parts.append(f"Salt was {r.salt_ppm} ppm.")
            texts.append(" ".join(parts))
            meta.append({"read_at": r.read_at.isoformat(), "source": r.source})

        self._history_texts = texts
        self._history_meta = meta

    def build(self):
        """Fit the TF-IDF vectorizer over the COMBINED corpus (KB + history)
        so both live in the same vector space and are comparable."""
        all_texts = self._kb_texts + self._history_texts
        if not all_texts:
            raise ValueError("No documents indexed. Call index_knowledge_base "
                              "and/or index_pool_history first.")
        self._vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self._matrix = self._vectorizer.fit_transform(all_texts)
        self._fitted = True

    def retrieve(self, query: str, k_kb: int = 3, k_history: int = 3) -> dict:
        """
        Retrieves top-k_kb knowledge base entries AND top-k_history pool
        readings separately, so the caller can see and cite both sources
        distinctly (required for the explainability principle in README.md
        Section 4, principle 4 — "root cause > symptom" reasoning needs to
        show its work).
        """
        if not self._fitted:
            self.build()

        query_vec = self._vectorizer.transform([query])
        all_scores = cosine_similarity(query_vec, self._matrix)[0]

        n_kb = len(self._kb_texts)
        kb_scores = all_scores[:n_kb]
        history_scores = all_scores[n_kb:]

        kb_results = self._top_k(kb_scores, self._kb_texts, self._kb_meta,
                                  k_kb, "knowledge_base")
        history_results = self._top_k(history_scores, self._history_texts,
                                       self._history_meta, k_history, "pool_history")

        return {
            "knowledge_base": kb_results,
            "pool_history": history_results,
        }

    @staticmethod
    def _top_k(scores, texts, meta, k, source) -> list:
        if len(scores) == 0:
            return []
        idx = np.argsort(scores)[::-1][:k]
        results = []
        for i in idx:
            if scores[i] <= 0:
                continue  # no lexical overlap at all — don't return noise
            results.append(RetrievedItem(
                id=meta[i].get("id", meta[i].get("read_at", f"item_{i}")),
                text=texts[i],
                score=float(scores[i]),
                source=source,
                metadata=meta[i],
            ))
        return results


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "..")
    from knowledge_base import get_all_entries
    sys.path.insert(0, ".")
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from case_study_data import build_case_study_state

    index = RetrievalIndex()
    index.index_knowledge_base(get_all_entries())
    state = build_case_study_state()
    index.index_pool_history(state.readings)
    index.build()

    query = "pH keeps going high after I add acid, what is going on"
    results = index.retrieve(query, k_kb=2, k_history=2)

    print(f"Query: {query}\n")
    print("=== Top KB matches ===")
    for r in results["knowledge_base"]:
        print(f"  [{r.score:.3f}] {r.id}: {r.text[:100]}...")
    print("\n=== Top pool history matches ===")
    for r in results["pool_history"]:
        print(f"  [{r.score:.3f}] {r.metadata['read_at']}: {r.text[:100]}...")
