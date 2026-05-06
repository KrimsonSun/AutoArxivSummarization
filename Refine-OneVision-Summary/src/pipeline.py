"""OneVisionPipeline orchestrator (Refine-OneVision-Summary §1).

End-to-end flow:
    PDF
        ↓ pdf_parser.parse_pdf()                       — Stage 0
    ParsedPaper
        ↓ asyncio.gather(InitialSummarizerAgent × 3)   — Stage 1
    [InitialSummary, ...]                              ≤ 1000 words each
        ↓ GameTheoryVoter (K rounds, anonymous)        — Stage 2
    VotingTranscript + winning_draft
        ↓ SingleDraftVerifierAgent (FULL paragraphs)   — Stage 3
    [Issue, ...]
        ↓ asyncio.gather(EvidenceRetrieverAgent × N)   — Stage 4
    [EvidenceBundle, ...]
        ↓ SingleDraftRefinerAgent (single-source)      — Stage 5
    FinalSummary  ≤ 1000 words

Notable differences from v1 RefinedSummarization.DebatePipeline:
    • No paragraph_summarizer — verifier reads full paragraph text.
    • No mutual_peer_review verification — selection is the voter's job.
    • Refiner does NOT merge 3 drafts; it augments the winning draft.
    • Hard 1000-word cap enforced both in prompts and via post-hoc truncation.

Failure handling: < 2 successful initial summarizers → PipelineError; voter
abstentions are filtered from Borda; verifier failure → empty issue list
(refiner just returns the winning draft as final).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from src.agents import (
    DEFAULT_MAX_WORDS,
    EvidenceRetrieverAgent,
    GameTheoryVoter,
    InitialSummarizerAgent,
    RefinerOutput,
    SingleDraftRefinerAgent,
    SingleDraftVerifierAgent,
    VoterClient,
)
from src.config.loader import PipelineConfig
from src.config.settings import settings  # noqa: F401  (env loading side-effect)
from src.llm_clients import make_client
from src.llm_clients.base import LLMClient, LLMError
from src.postprocessing.length_cap import truncate_to_word_cap
from src.preprocessing.pdf_parser import parse_pdf
from src.schemas.evidence import EvidenceBundle
from src.schemas.issue import Issue
from src.schemas.paper import ParsedPaper
from src.schemas.summary import (
    FinalSummary,
    FinalSummaryMetadata,
    InitialSummary,
)
from src.schemas.vote import VotingTranscript
from src.utils.logging import get_logger


class PipelineError(RuntimeError):
    pass


class OneVisionPipeline:
    """Vote-then-augment pipeline (5 stages)."""

    def __init__(
        self,
        config: PipelineConfig,
        max_words: int = DEFAULT_MAX_WORDS,
        voting_rounds: int = 3,
        voting_seed: int = 42,
    ):
        self.config = config
        self.log = get_logger("onevision_pipeline")
        self.max_words = max_words

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

        # Stateless agents.
        self._summarizer_agents = [
            InitialSummarizerAgent(client=c, agent_id=aid)
            for aid, c in self._initial_clients
        ]
        # Voter uses the same 3 LLMs as the drafters.
        self._voter = GameTheoryVoter(
            voters=[
                VoterClient(agent_id=aid, client=c)
                for aid, c in self._initial_clients
            ],
            rounds=voting_rounds,
            seed=voting_seed,
        )
        self._verifier = SingleDraftVerifierAgent(client=self._pipeline_client)
        self._retriever = EvidenceRetrieverAgent(client=self._pipeline_client)
        self._refiner = SingleDraftRefinerAgent(
            client=self._pipeline_client, max_words=self.max_words
        )

    # --------------------------------------------------------- public API

    async def healthcheck(self) -> dict[str, bool]:
        unique: dict[str, LLMClient] = {}
        for aid, c in self._initial_clients:
            unique[c.model_id + "::" + aid] = c
        unique["pipeline::" + self._pipeline_client.model_id] = self._pipeline_client
        results: dict[str, bool] = {}
        for key, c in unique.items():
            try:
                results[key] = await c.healthcheck()
            except LLMError as e:
                self.log.warning("healthcheck_failed", client=key, err=str(e))
                results[key] = False
        return results

    async def run(self, pdf_path: Path | str) -> tuple[FinalSummary, VotingTranscript]:
        """Returns (FinalSummary, VotingTranscript) — voting transcript saved
        for post-hoc inspection of which draft won and why."""
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

        # Truncate paper if it exceeds the budget (preserves head + tail).
        paper, truncated = self._enforce_paragraph_budget(paper)

        # ---------------- Stage 1: 3 initial summarizers in parallel.
        initial_summaries, failed_agent_ids = await self._run_initial_summarizers(paper)
        if len(initial_summaries) < 2:
            raise PipelineError(
                f"Only {len(initial_summaries)} initial summary/ies succeeded; "
                f"≥ 2 required for voting."
            )
        # Apply the 1000-word cap to drafts (post-hoc safety).
        initial_summaries = [
            truncate_to_word_cap(s, self.max_words) for s in initial_summaries
        ]
        self.log.info(
            "initial_summaries_capped",
            n=len(initial_summaries),
            max_words=self.max_words,
        )

        # ---------------- Stage 2: 3-round game-theory voting.
        # Voter requires exactly 3; if one drafter failed, fall back to using
        # the first successful summary directly without voting.
        if len(initial_summaries) < 3:
            self.log.warning(
                "voter_fallback_too_few_drafts",
                n_drafts=len(initial_summaries),
            )
            winning_draft = initial_summaries[0]
            transcript: VotingTranscript = _trivial_transcript(initial_summaries)
        else:
            transcript = await self._voter.run(initial_summaries)
            winning_draft = next(
                d for d in initial_summaries if d.agent_id == transcript.winner_agent_id
            )
        self.log.info(
            "voter_complete",
            winner_agent=transcript.winner_agent_id,
            winner_label=transcript.winner_label,
            borda=transcript.per_label_borda,
        )

        # ---------------- Stage 3: single-draft verifier (FULL paragraphs).
        try:
            issues = await self._verifier.run(paper, winning_draft)
        except LLMError as e:
            self.log.warning("verifier_failed", err=str(e))
            issues = []
        self.log.info("issues_raised", count=len(issues))

        # ---------------- Stage 4: per-issue evidence retrieval, parallel.
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

        # ---------------- Stage 5: single-draft refiner.
        if not issues:
            # No verifier issues → use the winning draft as-is (still apply word cap).
            refiner_out = RefinerOutput(
                tldr=winning_draft.tldr,
                core_idea=winning_draft.core_idea,
                key_contributions=winning_draft.key_contributions,
                method=winning_draft.method,
                experiments=winning_draft.experiments,
                limitations=winning_draft.limitations,
                issues_addressed=[],
            )
        else:
            refiner_out = await self._refiner.run(
                paper=paper,
                winning_draft=winning_draft,
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
            cl.usage.prompt_tokens
            for _, cl in self._initial_clients
        ) + self._pipeline_client.usage.prompt_tokens
        usage_total_completion = sum(
            cl.usage.completion_tokens
            for _, cl in self._initial_clients
        ) + self._pipeline_client.usage.completion_tokens
        total_calls = sum(
            cl.usage.calls for _, cl in self._initial_clients
        ) + self._pipeline_client.usage.calls

        metadata = FinalSummaryMetadata(
            arxiv_id=paper.arxiv_id,
            title=paper.title,
            paper_paragraph_count=len(paper.paragraphs),
            initial_agents=[aid for aid, _ in self._initial_clients],
            pipeline_llm=f"{self.config.pipeline.pipeline_llm.provider}:{self._pipeline_client.model_id}",
            verification_mode="single_draft_onevision",
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
            consensus_breakdown={"voter_winner": transcript.winner_agent_id},
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

        # Final word-cap pass (catches refiner overshoot).
        final_capped = _truncate_final_summary(final, self.max_words)

        self.log.info(
            "pipeline_done",
            tokens_prompt=usage_total_prompt,
            tokens_completion=usage_total_completion,
            calls=total_calls,
            issues=len(issues),
            issues_addressed=len(refiner_out.issues_addressed),
            winner=transcript.winner_agent_id,
        )
        return final_capped, transcript

    # --------------------------------------------------------- helpers

    async def _run_initial_summarizers(
        self, paper: ParsedPaper
    ) -> tuple[list[InitialSummary], list[str]]:
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
        max_n = self.config.constraints.max_paragraphs_in_refiner_context
        if len(paper.paragraphs) <= max_n:
            return paper, False
        keep_head = int(max_n * 0.65)
        keep_tail = max_n - keep_head
        head = paper.paragraphs[:keep_head]
        tail = paper.paragraphs[-keep_tail:]
        kept = head + tail
        truncated_paper = paper.model_copy(update={"paragraphs": kept})
        self.log.info(
            "paper_truncated",
            original=len(paper.paragraphs),
            kept=len(kept),
        )
        return truncated_paper, True


def _trivial_transcript(drafts: list[InitialSummary]) -> VotingTranscript:
    """No-vote fallback: rank drafts in input order with rank=1."""
    return VotingTranscript(
        voter_ids=[],
        label_to_agent={f"D{i+1}": d.agent_id for i, d in enumerate(drafts)},
        rounds=[],
        winner_label="D1",
        winner_agent_id=drafts[0].agent_id,
        winner_total_borda=0.0,
        per_label_borda={f"D{i+1}": 0.0 for i in range(len(drafts))},
    )


def _truncate_final_summary(final: FinalSummary, max_words: int) -> FinalSummary:
    """Wrap the InitialSummary-shaped truncator to also handle FinalSummary."""
    # Build a temp InitialSummary with the same fields, truncate, copy back.
    tmp = InitialSummary(
        agent_id="<final>",
        tldr=final.tldr,
        core_idea=final.core_idea,
        key_contributions=final.key_contributions,
        method=final.method,
        experiments=final.experiments,
        limitations=final.limitations,
    )
    capped = truncate_to_word_cap(tmp, max_words)
    return final.model_copy(update={
        "tldr": capped.tldr,
        "core_idea": capped.core_idea,
        "key_contributions": capped.key_contributions,
        "method": capped.method,
        "experiments": capped.experiments,
        "limitations": capped.limitations,
    })
