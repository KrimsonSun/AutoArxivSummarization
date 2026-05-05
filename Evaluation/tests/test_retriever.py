from __future__ import annotations

from src.retriever import BM25Retriever, _tokenize
from src.schemas import PaperBundle, PaperParagraph


def _paper() -> PaperBundle:
    return PaperBundle(
        paragraphs=[
            PaperParagraph(
                id="P1",
                text="The Transformer is a sequence-to-sequence model based on attention.",
            ),
            PaperParagraph(
                id="P2",
                text="It achieves 28.4 BLEU on the WMT 2014 English-to-German task.",
            ),
            PaperParagraph(
                id="P3",
                text="Recurrent neural networks process tokens sequentially.",
            ),
            PaperParagraph(
                id="P4",
                text="Convolutional networks parallelise across positions.",
            ),
        ]
    )


def test_bm25_returns_relevant_paragraph():
    r = BM25Retriever(_paper())
    hits = r.topk("Transformer model uses attention", k=2)
    pids = [h.paragraph_id for h in hits]
    assert "P1" in pids


def test_bm25_returns_numeric_paragraph_for_numeric_claim():
    r = BM25Retriever(_paper())
    hits = r.topk("28.4 BLEU on WMT 2014 English-German", k=1)
    assert hits[0].paragraph_id == "P2"


def test_bm25_empty_query_returns_empty():
    r = BM25Retriever(_paper())
    hits = r.topk("", k=3)
    assert hits == []


def test_tokenize_keeps_numbers_and_lowercases():
    t = _tokenize("BLEU score 28.4 on WMT-2014")
    assert "bleu" in t
    assert "28.4" in t
    # Hyphenated word survives because of \w+ but hyphens split per regex
    assert "wmt-2014" in t or "wmt" in t
