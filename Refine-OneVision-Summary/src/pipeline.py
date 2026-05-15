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
    ClaimGroundingVoter,
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
    """Vote-then-augment pipeline (5 stages, optionally iterative)."""

    def __init__(
        self,
        config: PipelineConfig,
        max_words: int | None = None,
    ):
        self.config = config
        self.log = get_logger("onevision_pipeline")
        # max_words: prefer caller arg, else config, else default.
        self.max_words = (
            max_words
            if max_words is not None
            else (
                getattr(config.pipeline, "max_summary_words", None)
                or DEFAULT_MAX_WORDS
            )
        )
        # Refinement loop config.
        ref = getattr(config.pipeline, "refinement", None)
        self.refinement_rounds = ref.rounds if ref is not None else 1
        self.use_winner_as_refiner = (
            ref.use_winner_as_refiner if ref is not None else False
        )

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
        # Verifier (always built; reused by Stage 3 and, in claim_grounding
        # mode, also by Stage 2).
        self._verifier = SingleDraftVerifierAgent(client=self._pipeline_client)
        self._retriever = EvidenceRetrieverAgent(client=self._pipeline_client)

        # Stage 2 voter — pick by config.voting.method.
        voting_cfg = getattr(config.pipeline, "voting", None)
        self._voting_method = (voting_cfg.method if voting_cfg else "claim_grounding").lower()
        if self._voting_method == "borda":
            self._borda_voter: GameTheoryVoter | None = GameTheoryVoter(
                voters=[
                    VoterClient(agent_id=aid, client=c)
                    for aid, c in self._initial_clients
                ],
                rounds=voting_cfg.rounds if voting_cfg else 3,
                seed=voting_cfg.seed if voting_cfg else 42,
            )
            self._claim_voter: ClaimGroundingVoter | None = None
        elif self._voting_method == "claim_grounding":
            self._borda_voter = None
            self._claim_voter = ClaimGroundingVoter(
                verifier=self._verifier,
                seed=voting_cfg.seed if voting_cfg else 42,
            )
        else:
            raise ValueError(
                f"Unknown voting.method: {self._voting_method!r}; "
                f"expected 'borda' or 'claim_grounding'."
            )
        # Default refiner uses pipeline_llm; the run() method may swap it
        # for the winning agent's client per-paper if use_winner_as_refiner.
        self._default_refiner = SingleDraftRefinerAgent(
            client=self._pipeline_client, max_words=self.max_words
        )

    def _refiner_for_winner(self, winner_agent_id: str) -> SingleDraftRefinerAgent:
        """Return a refiner that uses the winning agent's client, OR the
        default pipeline_llm refiner if use_winner_as_refiner is off / the
        winner has no matching initial client."""
        if not self.use_winner_as_refiner:
            return self._default_refiner
        for aid, client in self._initial_clients:
            if aid == winner_agent_id:
                return SingleDraftRefinerAgent(client=client, max_words=self.max_words)
        # Winner not found → fall back.
        self.log.warning(
            "winner_client_not_found_fallback_default_refiner",
            winner=winner_agent_id,
        )
        return self._default_refiner

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

        # ---------------- Stage 2: voting (method dispatched by config).
        # Both methods require exactly 3 drafts; if one drafter failed, fall
        # back to using the first successful summary directly without voting.
        if len(initial_summaries) < 3:
            self.log.warning(
                "voter_fallback_too_few_drafts",
                n_drafts=len(initial_summaries),
            )
            winning_draft = initial_summaries[0]
            transcript: VotingTranscript = _trivial_transcript(initial_summaries)
        elif self._voting_method == "claim_grounding":
            assert self._claim_voter is not None
            transcript = await self._claim_voter.run(paper, initial_summaries)
            winning_draft = next(
                d for d in initial_summaries if d.agent_id == transcript.winner_agent_id
            )
        else:  # borda
            assert self._borda_voter is not None
            transcript = await self._borda_voter.run(initial_summaries)
            winning_draft = next(
                d for d in initial_summaries if d.agent_id == transcript.winner_agent_id
            )
        self.log.info(
            "voter_complete",
            method=self._voting_method,
            winner_agent=transcript.winner_agent_id,
            winner_label=transcript.winner_label,
            borda=transcript.per_label_borda,
        )

        # ---------------- Stages 3-5: iterative refine loop.
        # current_draft starts as the winning draft. Each round runs
        # verify → retrieve → refine on the current_draft, and the
        # refiner output becomes the next round's current_draft.
        # The refiner used here is dynamic: if use_winner_as_refiner is
        # set, it's the winning agent's client; otherwise the static
        # pipeline_llm refiner.
        refiner = self._refiner_for_winner(transcript.winner_agent_id)
        self.log.info(
            "refiner_selected",
            winner_agent=transcript.winner_agent_id,
            winner_refines=self.use_winner_as_refiner,
            refinement_rounds=self.refinement_rounds,
        )

        current_draft: InitialSummary = winning_draft
        all_issues: list[Issue] = []
        all_evidence: list[EvidenceBundle] = []
        issues_addressed_total: list[str] = []

        # In claim_grounding mode, Stage 2's voter already ran the verifier
        # on the winning draft. Reuse those issues for round 1 to avoid the
        # duplicate verifier call. Subsequent refinement rounds (if any)
        # still re-run the verifier on the refined output.
        prefetched_round1_issues: list[Issue] | None = (
            list(transcript.precomputed_winner_issues)
            if transcript.precomputed_winner_issues is not None
            else None
        )

        for round_idx in range(1, self.refinement_rounds + 1):
            if round_idx == 1 and prefetched_round1_issues is not None:
                issues = prefetched_round1_issues
                self.log.info(
                    "issues_reused_from_voter",
                    round=round_idx,
                    count=len(issues),
                )
            else:
                try:
                    issues = await self._verifier.run(paper, current_draft)
                except Exception as e:
                    self.log.warning(
                        "verifier_failed",
                        round=round_idx,
                        err=str(e)[:300],
                        err_type=type(e).__name__,
                    )
                    issues = []
                self.log.info(
                    "issues_raised",
                    round=round_idx,
                    count=len(issues),
                )

            if not issues:
                # Nothing to fix this round; further rounds also won't have
                # anything to fix on the same paper, so short-circuit.
                self.log.info("refine_loop_short_circuit_no_issues", round=round_idx)
                break

            evidence_bundles = await asyncio.gather(
                *[self._retriever.run(issue, paper) for issue in issues]
            )
            self.log.info(
                "evidence_collected",
                round=round_idx,
                issues_with_evidence=sum(1 for b in evidence_bundles if b.evidence),
            )

            try:
                refiner_out_round = await refiner.run(
                    paper=paper,
                    winning_draft=current_draft,
                    issues=issues,
                    evidence_bundles=evidence_bundles,
                )
                # Hard-cap the round output so the next round sees ≤ max_words.
                current_draft = InitialSummary(
                    agent_id=current_draft.agent_id,
                    tldr=refiner_out_round.tldr,
                    core_idea=refiner_out_round.core_idea,
                    key_contributions=refiner_out_round.key_contributions,
                    method=refiner_out_round.method,
                    experiments=refiner_out_round.experiments,
                    limitations=refiner_out_round.limitations,
                )
                current_draft = truncate_to_word_cap(current_draft, self.max_words)
                issues_addressed_total.extend(refiner_out_round.issues_addressed)
                self.log.info(
                    "refine_round_complete",
                    round=round_idx,
                    n_issues=len(issues),
                    n_addressed=len(refiner_out_round.issues_addressed),
                )
            except Exception as e:
                self.log.warning(
                    "refiner_failed_keeping_current_draft",
                    round=round_idx,
                    err=str(e)[:300],
                    err_type=type(e).__name__,
                )
                # current_draft is unchanged for next round.
                break

            all_issues.extend(issues)
            all_evidence.extend(evidence_bundles)

        # Construct a RefinerOutput-shaped record for downstream metadata code.
        refiner_out = RefinerOutput(
            tldr=current_draft.tldr,
            core_idea=current_draft.core_idea,
            key_contributions=current_draft.key_contributions,
            method=current_draft.method,
            experiments=current_draft.experiments,
            limitations=current_draft.limitations,
            issues_addressed=issues_addressed_total,
        )
        # Re-bind names used by the metadata-assembly code below.
        issues = all_issues
        evidence_bundles = all_evidence

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
            # Voter info lives in the separate VotingTranscript returned alongside.
            # consensus_breakdown's schema is dict[str, int] so we cannot store
            # the agent_id string here without changing the FinalSummaryMetadata
            # schema. Leave empty.
            consensus_breakdown={},
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
            except (LLMError, Exception) as e:
                # Catch broadly: open-source models on OpenRouter sometimes
                # return malformed JSON that pydantic can't validate, which
                # raises ValidationError (NOT LLMError). Treat any failure
                # as a soft drop — the voter and rest of pipeline can run
                # with 2 of 3 drafts (falls back to trivial transcript).
                self.log.warning(
                    "initial_summarizer_failed",
                    agent=agent.agent_id,
                    err=str(e)[:300],
                    err_type=type(e).__name__,
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
        method="trivial_fallback",
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
