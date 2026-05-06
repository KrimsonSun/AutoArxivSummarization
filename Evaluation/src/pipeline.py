"""Evaluation pipeline orchestrator.

Loose mode (default — Steps 1–4):
  1. Claim extraction (LLM)
  2. BM25 retrieval per claim
  3. NLI verification per claim (LLM)
  4. Aggregate → evidence_coverage + hallucination_rate

Strict mode (when scoring.strict_mode=True — Steps 1–6):
  1–4 same as loose
  5. Paper-side claim extraction (LLM, once per paper)
  6. Recall check (LLM, once per (paper, summary))
  → adds paper_recall + F1 to the report

Inputs:
  • A summary in one of three forms:
      - FinalSummary JSON (RefinedSummarization output)
      - Plain text / Markdown summary (any baseline)
  • A paper, either:
      - PDF file
      - Pre-parsed PaperBundle JSON

Output: EvaluationReport with all metrics.
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
from src.paper_claim_extractor import PaperClaimExtractor
from src.recall_checker import RecallChecker
from src.retriever import make_retriever
from src.schemas import (
    Claim,
    ClaimVerification,
    CoverageCounts,
    EvaluationReport,
    EvidenceChunk,
    PaperBundle,
    PaperClaim,
    PaperClaimCoverage,
)
from src.scorer import assemble_report, f1_of, score, score_recall
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
        # Pick verifier per config: LLM-as-judge or local DeBERTa-NLI.
        verifier_kind = config.scoring.verifier_kind.lower()
        if verifier_kind == "deberta_nli":
            from src.nli_verifier import NLIVerifier, NLIThresholds
            self._verifier = NLIVerifier(
                model_name=config.scoring.nli_model,
                thresholds=NLIThresholds(
                    entailment_supported=config.scoring.nli_entailment_supported,
                    entailment_partial=config.scoring.nli_entailment_partial,
                    contradiction_strong=config.scoring.nli_contradiction_strong,
                ),
            )
        elif verifier_kind == "llm":
            self._verifier = ClaimVerifier(
                self._verifier_client,
                strict=config.scoring.strict_verifier_prompt,
            )
        else:
            raise ValueError(
                f"Unknown verifier_kind {verifier_kind!r}; expected 'llm' or 'deberta_nli'"
            )
        # Strict-mode components (initialised even when disabled — instantiation is cheap)
        self._paper_claim_extractor = PaperClaimExtractor(self._extractor_client)
        self._recall_checker = RecallChecker(self._verifier_client)

    # -------------------------------------------------- public API

    async def run(
        self,
        summary_path: str | Path,
        paper_path: str | Path,
        paper_claims: list[PaperClaim] | None = None,
    ) -> EvaluationReport:
        """Evaluate one (summary, paper) pair.

        ``paper_claims`` is optional pre-extracted paper claims (reuse across
        multiple summaries on the same paper to avoid re-extraction cost).
        Pass ``None`` to extract fresh.
        """
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

        # ---------- Step 4: aggregate (loose-mode metrics)
        counts, coverage, hallucination = score(verifications, self.config.scoring)

        # ---------- Steps 5–6: strict mode (paper-side recall + F1)
        paper_total_claims = 0
        paper_coverage_counts = CoverageCounts()
        paper_recall = 0.0
        f1 = 0.0
        per_paper_claim: list[PaperClaimCoverage] = []
        if self.config.scoring.strict_mode:
            # Step 5: paper-side claim extraction (cache-friendly via parameter)
            if paper_claims is None:
                paper_claims = await self._paper_claim_extractor.run(paper)
            self.log.info("paper_claims_extracted", n=len(paper_claims))

            # Step 6: recall check (one batched LLM call)
            summary_text = _summary_to_text(summary_input)
            per_paper_claim = await self._recall_checker.run(paper_claims, summary_text)
            self.log.info("recall_check_complete", n=len(per_paper_claim))

            paper_coverage_counts, paper_recall = score_recall(
                per_paper_claim, self.config.scoring
            )
            paper_total_claims = paper_coverage_counts.total
            f1 = f1_of(coverage, paper_recall)
            self.log.info(
                "strict_metrics",
                paper_recall=round(paper_recall, 4),
                f1=round(f1, 4),
                covered=paper_coverage_counts.covered,
                partial=paper_coverage_counts.partial,
                not_covered=paper_coverage_counts.not_covered,
            )

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
            paper_total_claims=paper_total_claims,
            paper_coverage_counts=paper_coverage_counts,
            paper_recall=paper_recall,
            f1=f1,
            per_paper_claim=per_paper_claim,
            strict_mode=self.config.scoring.strict_mode,
        )
        self.log.info(
            "report_ready",
            evidence_coverage=round(coverage, 4),
            hallucination_rate=round(hallucination, 4),
            paper_recall=round(paper_recall, 4),
            f1=round(f1, 4),
            total_claims=counts.total,
            paper_total_claims=paper_total_claims,
        )
        return report

    async def extract_paper_claims(self, paper_path: str | Path) -> list[PaperClaim]:
        """Pre-compute paper claims for re-use across multiple summaries.

        The orchestrator calls this once per paper, then passes the result to
        ``run(...)`` for each summary on that paper. Avoids re-extracting the
        same claims 6 times (once per method).
        """
        paper: PaperBundle = parse_paper(paper_path)
        return await self._paper_claim_extractor.run(paper)

    async def healthcheck(self) -> bool:
        return await self._extractor_client.healthcheck() and \
               await self._verifier_client.healthcheck()

    # -------------------------------------------------- helpers

    def _config_snapshot(self) -> dict[str, Any]:
        return {
            "extractor_model": self.config.extractor.model,
            "verifier_kind": self.config.scoring.verifier_kind,
            "verifier_model": (
                self.config.scoring.nli_model
                if self.config.scoring.verifier_kind == "deberta_nli"
                else self.config.verifier.model
            ),
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


def _summary_to_text(summary_input: dict) -> str:
    """Flatten any summary input into plain text for the recall checker."""
    if summary_input["kind"] == "plain":
        return summary_input["text"]
    fs = summary_input["data"]
    parts: list[str] = []
    for f in ("tldr", "core_idea"):
        v = fs.get(f)
        if isinstance(v, str):
            parts.append(v)
    for c in fs.get("key_contributions") or []:
        if isinstance(c, dict) and isinstance(c.get("text"), str):
            parts.append(c["text"])
    method = fs.get("method") or {}
    if isinstance(method, dict):
        if isinstance(method.get("overview"), str):
            parts.append(method["overview"])
        for comp in method.get("components") or []:
            if isinstance(comp, dict) and isinstance(comp.get("description"), str):
                parts.append(f"{comp.get('name', '')}: {comp['description']}")
    experiments = fs.get("experiments") or {}
    if isinstance(experiments, dict):
        if isinstance(experiments.get("setup"), str):
            parts.append(experiments["setup"])
        for f in experiments.get("key_findings") or []:
            if isinstance(f, dict) and isinstance(f.get("text"), str):
                parts.append(f["text"])
    for lim in fs.get("limitations") or []:
        if isinstance(lim, str):
            parts.append(lim)
    return "\n\n".join(parts)
