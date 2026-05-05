"""PDF → ParsedPaper (handoff §2.1).

Strategy:
1.  Use ``pdfplumber.extract_words`` to get word-level (x0, top, text) for each
    page. Word-level beats line-level because we can reconstruct paragraphs
    from vertical gaps between lines (PDF text streams have no paragraph
    delimiters; we must infer them).
2.  Group words into lines by `top` (within ±2pt of each other).
3.  Detect paragraph boundaries when the vertical gap between two
    consecutive lines exceeds ~1.5× the median gap on that page.
4.  Detect section headings (numbered like "1 Introduction" or bare like
    "Method") and use them to assign Section labels to subsequent paragraphs.
5.  Cut the document at the References/Bibliography heading.
6.  Drop figure/table captions, footnotes, and other noise via regex filters.
7.  Number the surviving paragraphs P1, P2, ... globally.

This is heuristic but works well for typical arXiv layouts. The verifier
agent downstream will catch any parser-induced errors as ``factual_error``.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

import pdfplumber

from src.schemas.paper import Paragraph, ParsedPaper, SectionName

# ---------------------------------------------------------------- regex tables

# Numbered headings: "1 Introduction", "2.3 Method", "3. Experiments"
_NUM_HEADING = re.compile(
    r"^(?P<num>\d+(?:\.\d+)*)\.?\s+(?P<rest>[A-Z][A-Za-z][A-Za-z0-9 \-:&/,]{1,80})$"
)
# Bare heading lines (no number)
_BARE_HEADINGS = {
    "abstract",
    "introduction",
    "background",
    "related work",
    "method",
    "methods",
    "methodology",
    "approach",
    "model",
    "framework",
    "architecture",
    "algorithm",
    "experiment",
    "experiments",
    "evaluation",
    "results",
    "discussion",
    "ablation",
    "analysis",
    "conclusion",
    "conclusions",
    "summary",
    "references",
    "bibliography",
    "acknowledgments",
    "acknowledgements",
}

# Section name normalisation
_SECTION_KEYWORDS: dict[str, SectionName] = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "background": "Introduction",
    "related work": "Introduction",
    "method": "Method",
    "methods": "Method",
    "methodology": "Method",
    "approach": "Method",
    "model": "Method",
    "framework": "Method",
    "architecture": "Method",
    "algorithm": "Method",
    "experiment": "Experiments",
    "experiments": "Experiments",
    "evaluation": "Experiments",
    "results": "Experiments",
    "discussion": "Experiments",
    "ablation": "Experiments",
    "analysis": "Experiments",
    "conclusion": "Conclusion",
    "conclusions": "Conclusion",
    "summary": "Conclusion",
}

_NOISE_LINE = re.compile(
    r"^("
    r"figure\s*\d+[:.]"
    r"|fig\.\s*\d+[:.]"
    r"|table\s*\d+[:.]"
    r"|algorithm\s*\d+[:.]"
    r"|\[\d+\]\s+[A-Z]"        # reference list entries
    r"|arxiv:\s*\d{4}\."
    r"|^\d+\s*$"               # bare page number
    r")",
    re.IGNORECASE,
)


# ------------------------------------------------------------------ public API

def parse_pdf(pdf_path: str | Path) -> ParsedPaper:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    # Stage 1: collect all (page_idx, line_top, line_text) across the whole PDF.
    all_lines: list[dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            words = page.extract_words(x_tolerance=2, y_tolerance=3)
            for line in _group_words_into_lines(words):
                all_lines.append({"page": page_idx, **line})

    if not all_lines:
        return ParsedPaper(title=pdf_path.stem, abstract="", paragraphs=[])

    # Stage 2: drop boilerplate (header/footer lines that repeat across pages).
    all_lines = _drop_repeating_lines(all_lines)

    # Stage 3: cut the document at references / bibliography.
    all_lines = _cut_at_references(all_lines)

    # Stage 4: classify each line as heading vs body.
    classified = _classify_lines(all_lines)

    # Stage 5: group body lines into paragraphs using vertical-gap heuristic
    # within each (page, section) span, attaching the most recent heading.
    raw_paragraphs = _group_into_paragraphs(classified)

    # Stage 6: heuristic head extraction (title / authors / abstract).
    title, authors, abstract, body_paragraphs = _extract_head(raw_paragraphs)

    # Stage 7: build typed Paragraph objects with global P# IDs.
    abstract = _clean_text_artefacts(abstract)
    typed: list[Paragraph] = []
    pid = 1
    if abstract:
        typed.append(Paragraph(id=f"P{pid}", section="Abstract", text=abstract))
        pid += 1
    for section, text in body_paragraphs:
        text = _clean_text_artefacts(text)
        if not _looks_like_real_paragraph(text):
            continue
        typed.append(Paragraph(id=f"P{pid}", section=section, text=text))
        pid += 1

    # arXiv id: try filename first, then full text (excluding the bogus front-page boilerplate).
    arxiv_id = _guess_arxiv_id(pdf_path.name) or _guess_arxiv_id_from_pdf(pdf_path)

    return ParsedPaper(
        title=title or pdf_path.stem,
        authors=authors,
        abstract=abstract or "",
        paragraphs=typed,
        arxiv_id=arxiv_id,
    )


# ----------------------------------------------- stage helpers


def _group_words_into_lines(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group a page's words into visual lines by top-coordinate."""
    if not words:
        return []
    # Sort by top, then by x0
    words = sorted(words, key=lambda w: (round(w["top"], 0), w["x0"]))
    lines: list[dict[str, Any]] = []
    current_top: float | None = None
    current_words: list[dict[str, Any]] = []
    for w in words:
        if current_top is None or abs(w["top"] - current_top) <= 2.0:
            current_words.append(w)
            current_top = w["top"] if current_top is None else current_top
        else:
            lines.append(_finalize_line(current_words))
            current_words = [w]
            current_top = w["top"]
    if current_words:
        lines.append(_finalize_line(current_words))
    return lines


def _finalize_line(words: list[dict[str, Any]]) -> dict[str, Any]:
    text = " ".join(w["text"] for w in words)
    top = min(w["top"] for w in words)
    bottom = max(w["bottom"] for w in words)
    x0 = min(w["x0"] for w in words)
    return {"text": text, "top": top, "bottom": bottom, "x0": x0}


def _drop_repeating_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pages = {l["page"] for l in lines}
    if len(pages) < 3:
        return lines  # too few pages to detect boilerplate reliably
    counts: Counter[str] = Counter()
    seen_per_page: dict[int, set[str]] = {}
    for L in lines:
        seen_per_page.setdefault(L["page"], set()).add(L["text"].strip())
    for s in seen_per_page.values():
        for t in s:
            counts[t] += 1
    threshold = max(2, len(pages) // 2)
    boilerplate = {t for t, c in counts.items() if c >= threshold and 1 <= len(t) <= 80}
    return [L for L in lines if L["text"].strip() not in boilerplate]


def _cut_at_references(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for idx, L in enumerate(lines):
        text = L["text"].strip().lower()
        # Bare or numbered: "References", "7 References", etc.
        if re.fullmatch(r"(?:\d+\.?\s+)?(references|bibliography)", text):
            return lines[:idx]
    return lines


def _classify_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tag each line as 'heading' (with section type) or 'body'."""
    out = []
    for L in lines:
        text = L["text"].strip()
        kind: str = "body"
        section: SectionName | None = None
        if not text:
            continue
        m = _NUM_HEADING.match(text)
        bare_match = text.lower() in _BARE_HEADINGS
        if (m and len(text) <= 80) or bare_match:
            kind = "heading"
            heading_lower = text.lower()
            if m:
                heading_lower = m.group("rest").lower()
            section = _classify_heading(heading_lower)
        out.append({**L, "kind": kind, "section": section, "text": text})
    return out


def _classify_heading(heading_lower: str) -> SectionName:
    h = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s+", "", heading_lower).strip()
    for kw, section in _SECTION_KEYWORDS.items():
        if kw in h:
            return section
    return "Other"


def _group_into_paragraphs(
    classified: list[dict[str, Any]],
) -> list[tuple[SectionName | None, str]]:
    """Walk lines, maintain current section, group adjacent body lines into
    paragraphs separated by larger-than-typical vertical gaps.

    Returns: [(section_or_None, paragraph_text), ...]. ``section`` is None
    for material before the first heading (used for title/author/abstract
    detection in the next stage).
    """
    # Compute median inter-line gap per page (excluding gaps that span pages).
    by_page: dict[int, list[float]] = {}
    prev: dict[str, Any] | None = None
    for L in classified:
        if prev is not None and prev["page"] == L["page"]:
            gap = L["top"] - prev["bottom"]
            if gap > 0:
                by_page.setdefault(L["page"], []).append(gap)
        prev = L
    median_gap_per_page = {
        p: (statistics.median(gs) if gs else 11.0) for p, gs in by_page.items()
    }

    paragraphs: list[tuple[SectionName | None, str]] = []
    current_section: SectionName | None = None
    current_words: list[str] = []
    prev = None
    for L in classified:
        # Heading flushes whatever we've buffered, then updates section.
        if L["kind"] == "heading":
            if current_words:
                paragraphs.append((current_section, _finalize_paragraph(current_words)))
                current_words = []
            current_section = L["section"] or current_section
            prev = L
            continue

        # Body line — decide whether to start a new paragraph based on gap.
        is_break = False
        if prev is not None:
            if prev["page"] != L["page"]:
                # Page break: only treat as paragraph break if previous line
                # ended on sentence-end punctuation (otherwise it's mid-paragraph).
                if current_words and re.search(r'[.!?][")\]]?\s*$', current_words[-1]):
                    is_break = True
            else:
                med = median_gap_per_page.get(L["page"], 11.0)
                gap = L["top"] - prev["bottom"]
                if gap > med * 1.55 and current_words:
                    is_break = True

        if is_break and current_words:
            paragraphs.append((current_section, _finalize_paragraph(current_words)))
            current_words = []

        current_words.append(L["text"])
        prev = L

    if current_words:
        paragraphs.append((current_section, _finalize_paragraph(current_words)))

    return paragraphs


def _finalize_paragraph(line_texts: list[str]) -> str:
    # Join with spaces, fix hyphenated line breaks.
    joined = " ".join(line_texts)
    joined = re.sub(r"-\s+([a-z])", r"\1", joined)
    joined = re.sub(r"\s+", " ", joined).strip()
    return joined


def _extract_head(
    paragraphs: list[tuple[SectionName | None, str]],
) -> tuple[str, list[str], str, list[tuple[SectionName, str]]]:
    """Pull title / authors / abstract from the unsectioned head, return rest."""
    title = ""
    authors: list[str] = []
    abstract = ""

    head_idx = 0
    # First paragraph with section None and "Abstract" heading nearby — but
    # we may also see explicit ``section == "Abstract"`` paragraphs.
    # Title heuristic: the first None-sectioned paragraph that's relatively
    # short and doesn't look like a permission notice.
    while head_idx < len(paragraphs) and paragraphs[head_idx][0] is None:
        text = paragraphs[head_idx][1]
        head_idx += 1
        low = text.lower()
        if "permission" in low or "copyright" in low or "license" in low:
            continue
        # First viable head paragraph: try to pull title + maybe authors out of it.
        # Often title and authors run together in our reconstruction; split on
        # author-list markers.
        if not title:
            # Title = first sentence-ish / up to first email or '*' marker
            t_match = re.split(
                r"\s+(?=(?:[A-Z]\w+\s*∗|\bAbstract\b|\b\w+@\w+))",
                text,
                maxsplit=1,
            )
            title = t_match[0].strip()
            remainder = t_match[1] if len(t_match) > 1 else ""
            if remainder:
                # Author chunk: anything before "Abstract" word
                au_chunk = re.split(r"\bAbstract\b", remainder, maxsplit=1)[0]
                authors = _parse_authors(au_chunk)
            continue
        # Subsequent head paragraphs without author yet → maybe authors line.
        if not authors and re.search(r",|\band\b", text) and "@" in text:
            authors = _parse_authors(text)

    # Find abstract paragraph: first one whose section is Abstract.
    rest: list[tuple[SectionName, str]] = []
    for sec, text in paragraphs[head_idx:]:
        if sec == "Abstract" and not abstract:
            abstract = text
            continue
        rest.append((sec or "Other", text))

    # Fallback: if no Abstract section, take the first paragraph from rest.
    if not abstract and rest:
        abstract = rest[0][1]
        rest = rest[1:]

    return title, authors, abstract, rest


def _parse_authors(chunk: str) -> list[str]:
    chunk = chunk.strip()
    if not chunk:
        return []
    # Stop at @ (email) — names come before emails.
    chunk = re.split(r"\s+\w+@\w+", chunk)[0]
    parts = re.split(r",|\band\b", chunk)
    return [re.sub(r"[∗†‡§¶0-9]+$", "", p).strip() for p in parts if p.strip() and len(p.strip()) < 60]


def _looks_like_real_paragraph(text: str) -> bool:
    if len(text) < 60:
        return False
    if _NOISE_LINE.match(text):
        return False
    digit_ratio = sum(c.isdigit() for c in text) / max(1, len(text))
    if digit_ratio > 0.4:
        return False
    return True


def _guess_arxiv_id(s: str) -> str | None:
    # arXiv watermarks the first page rotated 90° on the left margin, which
    # pdfplumber sometimes reads back-to-front (e.g. ``6730.6071:viXra``).
    # Reverse-search and skip values that overlap that watermark.
    m = re.search(r"arXiv:(\d{4}\.\d{4,5})(?:v\d+)?", s, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"(\d{4}\.\d{4,5})(?:v\d+)?", s)
    if m:
        # If the surrounding text looks like the reversed watermark, drop it.
        ctx = s[max(0, m.start() - 8): m.end() + 8]
        if "viXra" in ctx or "arXiv" not in ctx and re.search(r"[a-z]:[Vv]i[Xx]ra", ctx):
            return None
        return m.group(1)
    return None


def _guess_arxiv_id_from_pdf(pdf_path: Path) -> str | None:
    """Search the first page only — arXiv stamps the id in the bottom-left."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text() or ""
            return _guess_arxiv_id(text)
    except Exception:
        return None


# ---------------------------------------------------------------- abstract cleanup

_VIXRA_PREFIX = re.compile(r"^[\w\d.:]*viXra[\w\d.:]*\s*", re.IGNORECASE)


def _clean_text_artefacts(text: str) -> str:
    """Strip arXiv watermark fragments that pdfplumber sometimes prepends."""
    return _VIXRA_PREFIX.sub("", text).strip()
