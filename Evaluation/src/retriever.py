"""Step 2 — Per-claim evidence retrieval.

Default: BM25 (no model download, runs anywhere including Colab CPU).
Optional: dense embedding via sentence-transformers (install
``pip install -e ".[embedding]"`` to enable).
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod

from rank_bm25 import BM25Okapi

from src.schemas import EvidenceChunk, PaperBundle


class Retriever(ABC):
    @abstractmethod
    def topk(self, claim_text: str, k: int) -> list[EvidenceChunk]: ...


class BM25Retriever(Retriever):
    """Word-level BM25 over paper paragraphs. Fast, no GPU, deterministic."""

    def __init__(self, paper: PaperBundle):
        self.paper = paper
        self._paragraph_tokens: list[list[str]] = [
            _tokenize(p.text) for p in paper.paragraphs
        ]
        # rank_bm25 raises on empty corpus — guard.
        if any(self._paragraph_tokens):
            self._bm25 = BM25Okapi(self._paragraph_tokens)
        else:
            self._bm25 = None

    def topk(self, claim_text: str, k: int) -> list[EvidenceChunk]:
        if self._bm25 is None or not self.paper.paragraphs:
            return []
        query = _tokenize(claim_text)
        if not query:
            return []
        scores = self._bm25.get_scores(query)
        # argsort desc, take top-k
        ranked = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True,
        )[:k]
        return [
            EvidenceChunk(
                paragraph_id=self.paper.paragraphs[i].id,
                text=self.paper.paragraphs[i].text,
                score=float(scores[i]),
            )
            for i in ranked
            if scores[i] > 0  # drop zero-score noise
        ]


# ---------------------------------------------------------------- tokenizer

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*|\d+(?:\.\d+)?")


def _tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text)]


# --------------------------------------------------------------------- factory

def make_retriever(paper: PaperBundle, method: str) -> Retriever:
    method = method.lower()
    if method == "bm25":
        return BM25Retriever(paper)
    if method == "embedding":
        # Lazy import so the module is optional.
        from src.retriever_embedding import EmbeddingRetriever  # type: ignore
        return EmbeddingRetriever(paper)
    raise ValueError(f"Unknown retrieval method: {method!r}")
