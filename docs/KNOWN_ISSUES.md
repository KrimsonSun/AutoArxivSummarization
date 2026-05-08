# KNOWN_ISSUES — environment / install / config / API / cache gotchas

Append-only list of operational pitfalls. Each entry has an ID (`K1`,
`K2`, …) and a `symptom → cause → workaround` structure where applicable.
Entries here are environment-class only — algorithm / architecture
issues belong in `docs/LESSONS.md`.

---

## K1 — Three-provider `.env` setup

- **Symptom.** A run fails with `ConfigurationError: OPENAI_API_KEY is
  empty and DEV_MODE is off` or similar.
- **Cause.** `Evaluation/`, `RefinedSummarization/`, and
  `Refine-OneVision-Summary/` each have their own `pydantic-settings`
  loader. They expect `OPENAI_API_KEY` and `OPENAI_BASE_URL` (used as
  the OpenRouter endpoint) at minimum; `ANTHROPIC_API_KEY` and
  `GOOGLE_API_KEY` are also recognised but unused in the current
  pipelines.
- **Workaround.** Each settings.py walks up to the nearest `.git`
  ancestor and reads `<repo-root>/.env` first, then the project-local
  `.env` overrides. So you can put one `.env` at the repo root with
  `OPENAI_API_KEY=sk-or-v1-...` + `OPENAI_BASE_URL=https://openrouter.ai/api/v1`
  and all three subprojects pick it up.
- **Don't.** Don't put live keys in any `.env` file you intend to push.
  All `.env` paths are `.gitignore`d.

---

## K2 — `structlog` must write to stderr, not stdout

- **Symptom.** TS frontend (the main `AutoArxivSummarization` Next.js
  app) calls `python -m src.cli` as a subprocess and `JSON.parse` on
  the captured stdout. Parse failure with "unexpected token" early in
  the output.
- **Cause.** Default `structlog` config writes to stdout, contaminating
  the JSON-only stdout contract. Any log line at any level breaks
  the parser.
- **Workaround.** Both `RefinedSummarization/src/utils/logging.py` and
  `Refine-OneVision-Summary/src/utils/logging.py` configure structlog
  with `stream=sys.stderr`. Verify any new logger config preserves this.
- **Don't.** Don't `print(...)` anywhere in the pipeline path. Use the
  configured logger only; it goes to stderr by design.

---

## K3 — TS↔Python exit code contract

- **Symptom.** TS frontend reports vague "subprocess failed" on what
  was actually a config error.
- **Cause.** The CLI uses specific exit codes the TS side switches on.
- **Workaround.** Convention (per `RefinedSummarization/src/cli.py`):
  - `0` — success (FinalSummary JSON on stdout).
  - `1` — generic failure / unexpected exception.
  - `2` — config error (bad YAML, missing key, etc.).
  - `3` — PDF parse / file error (PDF unreadable, missing path).
  - `4` — LLM error (rate-limit, network, API key invalid, etc.).
  - 5+ — reserved.
- **Don't.** Don't `sys.exit(1)` on a config error — use the right
  exit code so the TS side renders the right toast.

---

## K4 — arXiv ingestion runs on a GCE VM, not Cloud Run

- **Symptom.** The arXiv-bulk-ingest job appears to silently die after
  ~24 hours when run on Cloud Run.
- **Cause.** Cloud Run has a hard 24-hour task timeout. Bulk
  ingestion of arXiv (millions of papers) takes several days.
- **Workaround.** Run on a long-lived GCE VM. See `docs/gcp-startup.sh`
  for the bootstrap; `docs/gcp-cloudrun-job.md` covers the *short* eval
  jobs that fit in 24 h, while `docs/gcp-docling-deployment.md` covers
  the long ingest.

---

## K5 — OpenRouter model checkpoint rotation

- **Symptom.** Re-running an experiment 3 weeks later gives different
  numbers despite identical config.
- **Cause.** OpenRouter rotates the underlying model checkpoint /
  serving instance for some open-source models (`meta-llama/llama-3.3-70b-instruct`,
  `qwen/qwen-2.5-72b-instruct`, `deepseek/deepseek-chat` all observed).
  The model identifier stays the same; the actual weights / sampling
  may not.
- **Workaround.** When you record an experiment in `EXPERIMENTS.json`,
  also record the date you ran it. For paper-grade reproducibility,
  cite the model snapshot (e.g., "queried 2026-05-06 via OpenRouter")
  in the paper's Setup section.
- **Don't.** Don't claim "exactly reproducible" for OpenRouter-routed
  experiments. Claim "reproducible up to OpenRouter routing rotation".

---

## K6 — Llama-3.3-70B rate-limit / fallback

- **Symptom.** A specific paper's F1 comes out anomalously low
  (e.g., < 0.10) for one method on one paper, while neighbours look
  normal.
- **Cause.** OpenRouter sometimes routes a single Llama-70B request
  to a slower / fallback instance under load, or rate-limits the
  request to a degraded model. The eventual response may be truncated
  or low-quality.
- **Workaround.** Before drawing any per-paper conclusion from a
  single F1 outlier, check `outputs/experiment/<id>/run.log` for
  `429` / `Retrying` / `Connection error` messages. Re-run that one
  paper alone if suspicious.
- **Don't.** Don't quote a per-paper F1 in the paper / case study
  without a sanity check that the underlying API call wasn't degraded.

---

## K7 — Paired bootstrap CI must use paired (per-paper) sampling

- **Symptom.** A reviewer queries why your CI is so wide.
- **Cause.** Across-paper variance dwarfs within-method variance. If
  you bootstrap two methods independently and subtract their means,
  the CI is much wider than warranted because cross-paper noise enters
  twice.
- **Workaround.** Always bootstrap on the per-paper paired difference
  vector. The shared canonical implementation is in
  `Evaluation/experiment/compare_*.py` (any of `compare_v1_v2`,
  `compare_2x2`, `compare_onevision`). 10000 iterations, 95 % quantile.
- **Don't.** Don't compare two pre-aggregated method means without a
  paired sub-routine — the variance estimate is wrong.

---

## K8 — OneVision iterative-refine wall-clock blowup on long papers

- **Symptom.** The OneVision v2 (K=3 refine + winner-as-refiner) run
  on n=29 stalled on 5 papers (FlashAttention 2205.14135, CoT
  2203.15556, ReAct 2210.03629, DPO 2305.18290, Mistral-7B
  2310.06825). Subprocesses live for 1–6+ hours per paper without
  completing; killing them is the only escape.
- **Cause.** (a) The Refine-OneVision-Summary CLI does **not**
  configure an `asyncio.wait_for` timeout on LLM calls — they hang
  indefinitely on flaky OpenRouter responses for long papers. (b) The
  K=3 refine loop multiplies the per-paper LLM-call count by ~3, and
  Qwen-72B (which wins voting 93 % of the time and so is also the
  refiner under `use_winner_as_refiner=true`) is rate-limit-prone
  under sustained load. (c) Long papers (60+ paragraphs) feed a
  ~10–20k-token prompt to the refiner per round.
- **Workaround.** Set `EXPERIMENT_CONCURRENCY=1` (instead of 2) and
  add `asyncio.wait_for(call, timeout=600)` around each LLM call in
  `Refine-OneVision-Summary/src/llm_clients/openai_client.py`.
- **Don't.** Don't run iterative-refine variants on n=29 in a
  single shot without a timeout — kill the process and lose all 5
  long papers (which is exactly what happened in this session).

---

## K9 — `experiment.run` re-runs ALL baselines when only one is pending (fixed but worth noting)

- **Symptom.** After a config / code change adds a new baseline (e.g.
  B6), running `python -m experiment.run` re-issues all 6 baseline
  LLM calls per paper instead of just the one new baseline.
- **Cause.** The original `run_baselines_for_paper` called
  `run_all_baselines(paper_text, title)` unconditionally, which
  iterates the entire `BASELINES` list. The cache check at write time
  prevented overwrite, but the LLM calls were already made (cost
  burned).
- **Workaround.** This was fixed in commit `155e95b` (PR #2 era):
  `run_all_baselines` now takes an `only=[<names>]` filter, and
  `run_baselines_for_paper` passes `only=pending`. Verify any new
  baseline addition doesn't regress this.

---

## K10 — `Evaluation/strict_reeval.py` evaluates `.voting.json` files as if they were summaries

- **Symptom.** `[12:01:23] Ours_onevision.voting FAILED: ValueError:
  Unrecognised JSON summary shape …` rows in the evaluation log.
- **Cause.** `experiment.strict_reeval` iterates *every* file in
  `summaries/<id>/` and tries to evaluate each. The voting transcript
  files (`Ours_onevision.voting.json`) sit in the same directory and
  are picked up. They have a different shape, so eval fails and writes
  an error stub.
- **Workaround.** Currently harmless (just noise in the log + an
  error stub written to `evals_*/` that compare scripts skip). To
  silence: change `strict_reeval.py` to filter file names ending in
  `.voting.json`. Low priority.

---

## K11 — DeBERTa NLI thresholds were never calibrated on this data

- **Symptom.** Reviewer asks: "Why 0.70 / 0.30 / 0.50 for DeBERTa
  thresholds?"
- **Cause.** The thresholds in
  `Evaluation/config/deberta.yaml` (`nli_entailment_supported: 0.70`,
  `nli_entailment_partial: 0.30`, `nli_contradiction_strong: 0.50`)
  are SummaC / FacTool literature defaults, never calibrated on this
  paper-summarisation distribution.
- **Workaround.** A reviewer-grade fix would do label gold annotation
  on ~50 (claim, paragraph) pairs and tune the thresholds for
  precision/recall sweet spot. This is on the camera-ready TODO,
  not blocking.
- **Don't.** Don't claim DeBERTa thresholds are "tuned" — call them
  "literature-default values applied without recalibration".

---

*Append new known issues below this line. Format: `## K<N> — <title>`
followed by `symptom / cause / workaround / don't` paragraphs.*
