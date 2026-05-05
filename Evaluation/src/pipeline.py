"""Evaluation pipeline orchestrator (Steps 1–4).

Inputs:
  • A summary in one of three forms:
      - FinalSummary JSON (RefinedSummarization output)
      - Plain text / Markdown summary (any baseline)
  • A paper, either:
      - PDF file
      - Pre-parsed PaperBundle JSON

Output: EvaluationReport with coverage + hallucination metrics.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config_loader import EvalConfig
from src.extractor import ClaimExtractor
from src.llm_client import LLMClient
from src.logging import get_logger
from src.paper_chunker import parse_paper
from src.retriever import make_retriever
from src.schemas import (
    Claim,
    ClaimVerification,
    EvaluationReport,
    EvidenceChunk,
    PaperBundle,
)
from src.scorer import assemble_report, score
from src.verifier import ClaimVerifier


class EvaluationPipeline:
    def __init__(self, config: EvalConfig):
        self.config = config
        self.log = get_logger("eval_pipeline")

        # Two LLM clients (extractor + verifier may be the same or different).
        self._extractor_client = LLMClient(
            model=config.extractor.model,
            temperature=config.extractor.temperature,
            max_tokens=config.extractor.max_tokens,
        )
        if config.verifier.model == config.extractor.model and \
           config.verifier.temperature == config.extractor.temperature:
            # Shared client reduces httpx connection churn.
            self._verifier_client = self._extractor_client
        else:
            self._verifier_client = LLMClient(
                model=config.verifier.model,
                temperature=config.verifier.temperature,
                max_tokens=config.verifier.max_tokens,
            )

        self._extractor = ClaimExtractor(self._extractor_client)
        self._verifier = ClaimVerifier(self._verifier_client)

    # -------------------------------------------------- public API

    async def run(
        self,
        summary_path: str | Path,
        paper_path: str | Path,
    ) -> EvaluationReport:
        summary_input = _load_summary(summary_path)
        paper: PaperBundle = parse_paper(paper_path)
        self.log.info(
            "loaded",
            summary_kind=summary_input["kind"],
            paper_paragraphs=len(paper.paragraphs),
        )

        # ---------- Step 1: claim extraction
        if summary_input["kind"] == "final_summary":
            claims: list[Claim] = await self._extractor.from_final_summary(
                summary_input["data"]
            )
        else:
            claims = await self._extractor.from_plain_text(summary_input["text"])
        self.log.info("claims_extracted", n=len(claims))

        if not claims:
            return _empty_report(paper, self._config_snapshot())

        # ---------- Step 2: per-claim retrieval (CPU, fast)
        retriever = make_retriever(paper, self.config.retrieval.method)
        per_claim_evidence: list[list[EvidenceChunk]] = [
            retriever.topk(c.text, self.config.retrieval.top_k)
            for c in claims
        ]
        self.log.info(
            "evidence_retrieved",
            method=self.config.retrieval.method,
            top_k=self.config.retrieval.top_k,
            mean_hits=(
                sum(len(e) for e in per_claim_evidence) / max(1, len(claims))
            ),
        )

        # ---------- Step 3: verification (parallel LLM calls)
        verifications: list[ClaimVerification] = await asyncio.gather(
            *[
                self._verifier.run(claim, evidence)
                for claim, evidence in zip(claims, per_claim_evidence)
            ]
        )
        self.log.info("verifications_complete", n=len(verifications))

        # ---------- Step 4: aggregate
        counts, coverage, hallucination = score(verifications, self.config.scoring)
        report = assemble_report(
            arxiv_id=paper.arxiv_id,
            title=paper.title,
            paper_paragraph_count=len(paper.paragraphs),
            verifications=verifications,
            counts=counts,
            coverage=coverage,
            hallucination=hallucination,
            config_snapshot=self._config_snapshot(),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.log.info(
            "report_ready",
            evidence_coverage=round(coverage, 4),
            hallucination_rate=round(hallucination, 4),
            total_claims=counts.total,
            supported=counts.supported,
            partial=counts.partial,
            unsupported=counts.unsupported,
            contradicted=counts.contradicted,
        )
        return report

    async def healthcheck(self) -> bool:
        return await self._extractor_client.healthcheck() and \
               await self._verifier_client.healthcheck()

    # -------------------------------------------------- helpers

    def _config_snapshot(self) -> dict[str, Any]:
        return {
            "extractor_model": self.config.extractor.model,
            "verifier_model": self.config.verifier.model,
            "retrieval": self.config.retrieval.model_dump(),
            "scoring": self.config.scoring.model_dump(),
        }


# ---------------------------------------------------------- summary loading

def _load_summary(path: str | Path) -> dict:
    """Detect summary format and return a dict the orchestrator can route on."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    suffix = p.suffix.lower()
    if suffix == ".json":
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        # FinalSummary has these top-level keys per RefinedSummarization schema.
        if isinstance(data, dict) and "tldr" in data and "method" in data:
            return {"kind": "final_summary", "data": data}
        # Otherwise treat the JSON's "summary" / "text" field as plain text.
        if isinstance(data, dict) and isinstance(data.get("text"), str):
            return {"kind": "plain", "text": data["text"]}
        raise ValueError(
            f"Unrecognised JSON summary shape in {p}. Expected FinalSummary "
            f"(with 'tldr', 'method' keys) or {{'text': '...'}}."
        )
    # .md / .txt → plain text
    return {"kind": "plain", "text": p.read_text(encoding="utf-8")}


def _empty_report(paper: PaperBundle, snapshot: dict) -> EvaluationReport:
    from src.schemas import VerdictCounts
    return EvaluationReport(
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        paper_paragraph_count=len(paper.paragraphs),
        total_claims=0,
        counts=VerdictCounts(),
        evidence_coverage=0.0,
        hallucination_rate=0.0,
        per_claim=[],
        eval_config=snapshot,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
