"""Minimal PDF → list[PaperParagraph].

Independent of RefinedSummarization's parser to keep this module standalone.
Strategy: pdfplumber word coords → group into lines → group lines into
paragraphs by vertical-gap heuristic. Sections are NOT classified here
(Evaluation doesn't need them — retrieval is over flat paragraphs).

Also accepts a pre-parsed paragraph JSON if you've already parsed the PDF
elsewhere — useful when comparing baselines on a shared corpus.
"""
from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from typing import Any

import pdfplumber

from src.schemas import PaperBundle, PaperParagraph

_NOISE = re.compile(
    r"^("
    r"figure\s*\d+[:.]"
    r"|fig\.\s*\d+[:.]"
    r"|table\s*\d+[:.]"
    r"|algorithm\s*\d+[:.]"
    r"|\[\d+\]\s+[A-Z]"
    r"|\d+\s*$"
    r")",
    re.IGNORECASE,
)


def parse_paper(path: str | Path) -> PaperBundle:
    """Top-level entry. ``path`` may point at a PDF or at a JSON file
    matching the PaperBundle schema (lets you skip re-parsing)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    if p.suffix.lower() == ".json":
        with open(p, "r", encoding="utf-8") as f:
            return PaperBundle.model_validate(json.load(f))
    return _parse_pdf(p)


# ---------------------------------------------------------------- PDF parsing

def _parse_pdf(pdf: Path) -> PaperBundle:
    all_lines: list[dict[str, Any]] = []
    with pdfplumber.open(pdf) as doc:
        for page_idx, page in enumerate(doc.pages):
            words = page.extract_words(x_tolerance=2, y_tolerance=3)
            for line in _lines_from_words(words):
                all_lines.append({"page": page_idx, **line})

    if not all_lines:
        return PaperBundle(arxiv_id=_arxiv_id_from_filename(pdf), title=pdf.stem)

    # Cut off references / bibliography.
    all_lines = _cut_at_references(all_lines)

    # Group lines into paragraphs by vertical-gap heuristic.
    paragraphs_text = _group_into_paragraphs(all_lines)

    typed: list[PaperParagraph] = []
    for idx, text in enumerate(paragraphs_text, start=1):
        text = _clean_artefacts(text)
        if not _looks_real(text):
            continue
        typed.append(PaperParagraph(id=f"P{idx}", text=text))

    # Re-number (some paragraphs were dropped) so IDs stay contiguous P1..Pn.
    typed = [PaperParagraph(id=f"P{i+1}", text=p.text) for i, p in enumerate(typed)]

    title = _guess_title(all_lines)
    arxiv_id = _arxiv_id_from_filename(pdf)
    return PaperBundle(arxiv_id=arxiv_id, title=title, paragraphs=typed)


# --------------------------------------------------------------- helper passes

def _lines_from_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not words:
        return []
    words = sorted(words, key=lambda w: (round(w["top"], 0), w["x0"]))
    out: list[dict[str, Any]] = []
    cur_top: float | None = None
    cur: list[dict[str, Any]] = []
    for w in words:
        if cur_top is None or abs(w["top"] - cur_top) <= 2.0:
            cur.append(w)
            if cur_top is None:
                cur_top = w["top"]
        else:
            out.append(_finalize(cur))
            cur = [w]
            cur_top = w["top"]
    if cur:
        out.append(_finalize(cur))
    return out


def _finalize(words: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "text": " ".join(w["text"] for w in words),
        "top": min(w["top"] for w in words),
        "bottom": max(w["bottom"] for w in words),
    }


def _cut_at_references(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for idx, L in enumerate(lines):
        t = L["text"].strip().lower()
        if re.fullmatch(r"(?:\d+\.?\s+)?(references|bibliography)", t):
            return lines[:idx]
    return lines


def _group_into_paragraphs(lines: list[dict[str, Any]]) -> list[str]:
    # Median gap per page → paragraph break > 1.55× median.
    by_page: dict[int, list[float]] = {}
    prev = None
    for L in lines:
        if prev is not None and prev["page"] == L["page"]:
            g = L["top"] - prev["bottom"]
            if g > 0:
                by_page.setdefault(L["page"], []).append(g)
        prev = L
    median_gap = {p: (statistics.median(gs) if gs else 11.0) for p, gs in by_page.items()}

    paragraphs: list[str] = []
    cur: list[str] = []
    prev = None
    for L in lines:
        is_break = False
        if prev is not None and cur:
            if prev["page"] != L["page"]:
                # only break if previous line ends in sentence-end punctuation
                if re.search(r'[.!?][")\]]?\s*$', cur[-1]):
                    is_break = True
            else:
                gap = L["top"] - prev["bottom"]
                if gap > median_gap.get(L["page"], 11.0) * 1.55:
                    is_break = True
        if is_break and cur:
            paragraphs.append(_join(cur))
            cur = []
        cur.append(L["text"])
        prev = L
    if cur:
        paragraphs.append(_join(cur))
    return paragraphs


def _join(line_texts: list[str]) -> str:
    s = " ".join(line_texts)
    s = re.sub(r"-\s+([a-z])", r"\1", s)  # un-hyphenate line breaks
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _clean_artefacts(text: str) -> str:
    return re.sub(r"^[\w\d.:]*viXra[\w\d.:]*\s*", "", text, flags=re.IGNORECASE).strip()


def _looks_real(text: str) -> bool:
    if len(text) < 60:
        return False
    if _NOISE.match(text):
        return False
    digit_ratio = sum(c.isdigit() for c in text) / max(1, len(text))
    return digit_ratio < 0.4


def _guess_title(lines: list[dict[str, Any]]) -> str:
    # First non-trivial line that isn't a permission notice.
    for L in lines[:8]:
        t = L["text"].strip()
        if 8 <= len(t) <= 200 and "permission" not in t.lower():
            return t
    return ""


def _arxiv_id_from_filename(p: Path) -> str | None:
    m = re.search(r"(\d{4}\.\d{4,5})", p.name)
    return m.group(1) if m else None
