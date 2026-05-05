"""DebatePipeline orchestrator (handoff §4.3).

End-to-end flow per handoff §0:
    PDF
        ↓ pdf_parser.parse_pdf()                 — Stage 0
        ↓ ParagraphShortSummarizer               — pre-compute paragraph summaries
    ParsedPaper
        ↓ asyncio.gather(InitialSummarizerAgent × 3)   — Stage 1
    [InitialSummary, ...]
        ↓ VerifierAgent (1 call)                       — Stage 2
    [Issue, ...]
        ↓ asyncio.gather(EvidenceRetrieverAgent × N)   — Stage 3 (N = #issues)
    [EvidenceBundle, ...]
        ↓ RefinerAgent (1 call)                        — Stage 4
    FinalSummary

Failure handling (handoff §8): an initial summarizer that fails after retries
is dropped (need ≥ 2 to continue). Verifier 0-issues case skips retrieval.
Empty evidence bundles are passed through to the refiner so it can flag them.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from src.agents import (
    EvidenceRetrieverAgent,
    InitialSummarizerAgent,
    PeerReviewVerifier,
    RefinerAgent,
    RefinerOutput,
    VerifierAgent,
)
from src.config.loader import PipelineConfig
from src.config.settings import settings
from src.llm_clients import make_client
from src.llm_clients.base import LLMClient, LLMError
from src.preprocessing.paragraph_summarizer import ParagraphShortSummarizer
from src.preprocessing.pdf_parser import parse_pdf
from src.schemas.evidence import EvidenceBundle
from src.schemas.issue import Issue
from src.schemas.paper import ParsedPaper
from src.schemas.summary import (
    FinalSummary,
    FinalSummaryMetadata,
    InitialSummary,
)
from src.utils.logging import get_logger


class PipelineError(RuntimeError):
    """Raised when the pipeline cannot continue (e.g. < 2 initial summaries)."""


def _consensus_histogram(issues: list[Issue]) -> dict[str, int]:
    """How many issues were raised by 1 / 2 / 3+ reviewers.

    Empty raised_by (single_judge mode) is reported as ``judge``.
    """
    hist: dict[str, int] = {}
    for issue in issues:
        n = len(issue.raised_by)
        if n == 0:
            key = "judge"
        elif n == 1:
            key = "1_reviewer"
        elif n == 2:
            key = "2_reviewers"
        else:
            key = "3_plus_reviewers"
        hist[key] = hist.get(key, 0) + 1
    return hist


class DebatePipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.log = get_logger("pipeline")

        # Build the three initial summarizer clients.
        self._initial_clients: list[tuple[str, LLMClient]] = []
        for agent_spec in config.pipeline.initial_agents:
            agent_id = agent_spec.id or f"agent_{agent_spec.provider}"
            client = make_client(
                agent_spec.provider, agent_spec.model, agent_spec.temperature
            )
            self._initial_clients.append((agent_id, client))

        # Pipeline (verifier/retriever/refiner) main client.
        plc = config.pipeline.pipeline_llm
        self._pipeline_client: LLMClient = make_client(
            plc.provider, plc.model, plc.temperature
        )

        # Optional paragraph short-summarizer client.
        if config.pipeline.paragraph_summarizer is not None:
            ps = config.pipeline.paragraph_summarizer
            self._paragraph_client: LLMClient | None = make_client(
                ps.provider, ps.model, ps.temperature
            )
            self._paragraph_target_length = ps.target_length
        else:
            self._paragraph_client = None
            self._paragraph_target_length = 200

        # Agents are stateless, instantiate once.
        self._summarizer_agents = [
            InitialSummarizerAgent(client=c, agent_id=aid)
            for aid, c in self._initial_clients
        ]
        # Verification: dispatch on config.
        self._verification_mode = config.pipeline.verification_mode
        if self._verification_mode == "mutual_peer_review":
            # The 3 initial summarizer LLMs ALSO act as 3 reviewers — true
            # heterogeneous mutual evaluation. Each reviewer independently
            # critiques all 3 drafts; aggregator merges + tags by consensus.
            self._peer_verifier: PeerReviewVerifier | None = PeerReviewVerifier(
                reviewer_clients=list(self._initial_clients),
            )
            self._verifier: VerifierAgent | None = None
        elif self._verification_mode == "single_judge":
            self._peer_verifier = None
            self._verifier = VerifierAgent(client=self._pipeline_client)
        else:
            raise ValueError(
                f"Unknown verification_mode: {self._verification_mode!r}. "
                f"Expected 'mutual_peer_review' or 'single_judge'."
            )
        self._retriever = EvidenceRetrieverAgent(client=self._pipeline_client)
        self._refiner = RefinerAgent(client=self._pipeline_client)
        self._paragraph_summarizer = ParagraphShortSummarizer(
            client=self._paragraph_client,
            target_length=self._paragraph_target_length,
        )

    # ----------------------------------------------------------- public API

    async def healthcheck(self) -> dict[str, bool]:
        """Ping every distinct underlying client (handoff §5.4)."""
        unique: dict[str, LLMClient] = {}
        for aid, c in self._initial_clients:
            unique[c.model_id + "::" + aid] = c
        unique["pipeline::" + self._pipeline_client.model_id] = self._pipeline_client
        if self._paragraph_client is not None:
            unique["paragraph::" + self._paragraph_client.model_id] = self._paragraph_client

        results: dict[str, bool] = {}
        for key, c in unique.items():
            try:
                results[key] = await c.healthcheck()
            except LLMError as e:
                self.log.warning("healthcheck_failed", client=key, err=str(e))
                results[key] = False
        return results

    async def run(self, pdf_path: Path | str) -> FinalSummary:
        pdf_path = Path(pdf_path)
        self.log.info("pipeline_start", pdf=str(pdf_path))

        # ---------------- Stage 0: parse PDF
        paper: ParsedPaper = parse_pdf(pdf_path)
        self.log.info(
            "pdf_parsed",
            title=paper.title[:80],
            paragraphs=len(paper.paragraphs),
            arxiv_id=paper.arxiv_id,
        )
        if not paper.paragraphs:
            raise PipelineError("PDF parsing produced zero paragraphs.")

        # Stage 0b: pre-compute paragraph short summaries (cheap).
        await self._paragraph_summarizer.run(paper)
        self.log.info("paragraph_summaries_ready")

        # Truncate the paper if it exceeds the refiner context budget.
        paper, truncated = self._enforce_paragraph_budget(paper)

        # ---------------- Stage 1: 3 initial summarizers in parallel.
        initial_summaries, failed_agent_ids = await self._run_initial_summarizers(paper)
        if len(initial_summaries) < 2:
            raise PipelineError(
                f"Only {len(initial_summaries)} initial summary/ies succeeded; "
                f"≥ 2 required (handoff §8)."
            )

        # ---------------- Stage 2: verification (mode-dependent).
        # In mutual_peer_review mode, the 3 initial-summarizer LLMs act as 3
        # heterogeneous reviewers; each issue is tagged with raised_by
        # showing which reviewers flagged it (consensus signal). In
        # single_judge mode, a single pipeline_llm verifies all drafts.
        try:
            if self._peer_verifier is not None:
                issues = await self._peer_verifier.run(paper, initial_summaries)
            else:
                assert self._verifier is not None  # narrow for type checker
                issues = await self._verifier.run(paper, initial_summaries)
        except LLMError as e:
            self.log.warning("verifier_failed", err=str(e))
            issues = []
        self.log.info(
            "issues_raised",
            count=len(issues),
            mode=self._verification_mode,
            consensus_breakdown=_consensus_histogram(issues),
        )

        # ---------------- Stage 3: per-issue evidence retrieval, parallel.
        evidence_bundles: list[EvidenceBundle]
        if issues:
            evidence_bundles = await asyncio.gather(
                *[self._retriever.run(issue, paper) for issue in issues]
            )
        else:
            evidence_bundles = []
        self.log.info(
            "evidence_collected",
            issues_with_evidence=sum(1 for b in evidence_bundles if b.evidence),
        )

        # ---------------- Stage 4: refiner (single call).
        refiner_out: RefinerOutput = await self._refiner.run(
            paper=paper,
            summaries=initial_summaries,
            issues=issues,
            evidence_bundles=evidence_bundles,
        )

        # ---------------- Assemble metadata.
        evidence_paragraphs_used = sorted({
            ev.paragraph_id
            for bundle in evidence_bundles
            for ev in bundle.evidence
        })
        usage_total_prompt = sum(
            c.usage.prompt_tokens
            for c in [
                *[cl for _, cl in self._initial_clients],
                self._pipeline_client,
                self._paragraph_client,
            ]
            if c is not None
        )
        usage_total_completion = sum(
            c.usage.completion_tokens
            for c in [
                *[cl for _, cl in self._initial_clients],
                self._pipeline_client,
                self._paragraph_client,
            ]
            if c is not None
        )
        total_calls = sum(
            c.usage.calls
            for c in [
                *[cl for _, cl in self._initial_clients],
                self._pipeline_client,
                self._paragraph_client,
            ]
            if c is not None
        )

        metadata = FinalSummaryMetadata(
            arxiv_id=paper.arxiv_id,
            title=paper.title,
            paper_paragraph_count=len(paper.paragraphs),
            initial_agents=[aid for aid, _ in self._initial_clients],
            pipeline_llm=f"{self.config.pipeline.pipeline_llm.provider}:{self._pipeline_client.model_id}",
            verification_mode=self._verification_mode,
            issues_raised=len(issues),
            issues_addressed=list(refiner_out.issues_addressed),
            evidence_paragraphs_used=evidence_paragraphs_used,
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_llm_calls=total_calls,
            total_tokens_used={
                "prompt": usage_total_prompt,
                "completion": usage_total_completion,
            },
            truncated=truncated,
            failed_initial_agents=failed_agent_ids,
            consensus_breakdown=_consensus_histogram(issues),
        )

        final = FinalSummary(
            tldr=refiner_out.tldr,
            core_idea=refiner_out.core_idea,
            key_contributions=refiner_out.key_contributions,
            method=refiner_out.method,
            experiments=refiner_out.experiments,
            limitations=refiner_out.limitations,
            metadata=metadata,
        )
        self.log.info(
            "pipeline_done",
            tokens_prompt=usage_total_prompt,
            tokens_completion=usage_total_completion,
            calls=total_calls,
            issues=len(issues),
            issues_addressed=len(refiner_out.issues_addressed),
        )
        return final

    # ----------------------------------------------------------- helpers

    async def _run_initial_summarizers(
        self, paper: ParsedPaper
    ) -> tuple[list[InitialSummary], list[str]]:
        """Run all 3 in parallel; collect successes, log failures (§8)."""
        async def _safe(agent: InitialSummarizerAgent) -> InitialSummary | str:
            try:
                return await agent.run(paper)
            except LLMError as e:
                self.log.warning(
                    "initial_summarizer_failed", agent=agent.agent_id, err=str(e)
                )
                return agent.agent_id

        results = await asyncio.gather(
            *[_safe(a) for a in self._summarizer_agents], return_exceptions=False
        )
        ok: list[InitialSummary] = []
        failed_ids: list[str] = []
        for r in results:
            if isinstance(r, str):
                failed_ids.append(r)
            else:
                ok.append(r)
        return ok, failed_ids

    def _enforce_paragraph_budget(
        self, paper: ParsedPaper
    ) -> tuple[ParsedPaper, bool]:
        """If the paper is too long for the refiner context, drop middle
        paragraphs (handoff §8): keep abstract + introduction + conclusion in
        full, prefer paragraphs that contain potential evidence references.

        Heuristic: if paragraph count exceeds ``max_paragraphs_in_refiner_context``,
        keep the first 60% (intro/method usually here) and last 20%
        (experiments/conclusion), and drop a uniform sample of middles.
        """
        max_n = self.config.constraints.max_paragraphs_in_refiner_context
        if len(paper.paragraphs) <= max_n:
            return paper, False

        keep_head = int(max_n * 0.65)
        keep_tail = max_n - keep_head
        head = paper.paragraphs[:keep_head]
        tail = paper.paragraphs[-keep_tail:]
        kept = head + tail

        # Re-renumber to preserve consecutive Pn IDs (so verifier doesn't see gaps).
        # Actually preserve original IDs: gap-tolerant renumbering would
        # invalidate any evidence_refs from other agents. Keep IDs as-is.
        truncated_paper = paper.model_copy(update={"paragraphs": kept})
        self.log.info(
            "paper_truncated",
            original=len(paper.paragraphs),
            kept=len(kept),
        )
        return truncated_paper, True
