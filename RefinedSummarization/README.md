# RefinedSummarization

> Multi-Agent Debate Summarizer for arXiv papers.
> A self-contained Python module — does NOT touch the parent TypeScript
> repo. Integrate via subprocess (CLI) or HTTP (FastAPI). See HANDOFF §13.

A Python pipeline that turns an arXiv PDF into a verified, evidence-grounded
summary by orchestrating **3 heterogeneous LLMs** in a debate-and-refine loop:

```
PDF → ParsedPaper
   ↓
[3 LLMs in parallel] → 3 draft summaries
   ↓
Verifier → issue list (factual errors, missing info, inconsistencies, ...)
   ↓
Evidence Retriever (per issue, parallel) → paragraph-level evidence
   ↓
Refiner → final merged summary (JSON + Markdown)
```

Built per `HANDOFF.md` in the parent repo.

---

## Setup (OpenRouter, open-source models — default)

```bash
# 1. Create venv and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Get an OpenRouter key:  https://openrouter.ai/keys
# 3. Wire it up
cp .env.example .env
$EDITOR .env
#   OPENAI_API_KEY=sk-or-v1-...
#   OPENAI_BASE_URL=https://openrouter.ai/api/v1
#   DEV_MODE=0
```

The default config (`config/default.yaml`) uses **three open-source models**
routed through OpenRouter — one key, three heterogeneous LLMs:

| Role                  | Model                                  | Org        |
|-----------------------|----------------------------------------|------------|
| Initial draft #1      | `meta-llama/llama-3.3-70b-instruct`    | Meta       |
| Initial draft #2      | `qwen/qwen-2.5-72b-instruct`           | Alibaba    |
| Initial draft #3      | `deepseek/deepseek-chat`               | DeepSeek   |
| Verifier / Retriever / Refiner | `meta-llama/llama-3.3-70b-instruct` | Meta (128k ctx) |
| Paragraph compressor  | `meta-llama/llama-3.1-8b-instruct`     | Meta (cheap) |

Cost per 10-page paper: ~$0.05 – $0.15. Edit `config/default.yaml` to swap
in any other OpenRouter-hosted model (full catalogue at
https://openrouter.ai/models).

### Without a key (DEV_MODE)

Set `DEV_MODE=1` in `.env`. Every module imports cleanly and the test suite
runs (mocked); real LLM calls error with `ConfigurationError` until you
flip `DEV_MODE=0` and provide a key.

### Running on Google Colab

See [`examples/colab_setup.md`](examples/colab_setup.md) — paste 6 cells,
no GPU required.

---

## Usage

### CLI

```bash
python -m src.cli --pdf path/to/paper.pdf --output-format json
```

Stdout = JSON. Stderr = structured logs. Exit codes:
`0=ok 1=config 2=pdf 3=llm 4=schema 5=other`.

### FastAPI server

```bash
uvicorn src.server:app --host 0.0.0.0 --port 8000
# POST /summarize   (multipart upload of a PDF)
# GET  /health
```

### From Python

```python
import asyncio
from src.config.loader import load_config
from src.pipeline import DebatePipeline

config = load_config("config/default.yaml")
pipeline = DebatePipeline(config)
result = asyncio.run(pipeline.run("paper.pdf"))
print(result.tldr)
```

### Demo

```bash
python examples/run_example.py tests/fixtures/sample_paper.pdf
# Writes outputs/<arxiv_id>.json and outputs/<arxiv_id>.md
```

---

## Tests

```bash
pytest tests/                # 23 unit tests + 1 mocked E2E (no API needed)
RUN_E2E=1 pytest tests/test_pipeline_e2e.py   # real LLM E2E (≈ $0.5)
```

---

## Swapping in open-source models

The OpenAI client honours `OPENAI_BASE_URL`, so any OpenAI-compatible
aggregator works without code changes. Set in `.env`:

```bash
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-v1-<your-openrouter-key>
```

then in `config/default.yaml` change the model id and (optionally) repoint
all three providers to `openai`:

```yaml
pipeline:
  initial_agents:
    - {id: agent_a, provider: openai, model: meta-llama/llama-3.3-70b-instruct, temperature: 0.7}
    - {id: agent_b, provider: openai, model: anthropic/claude-3.5-sonnet,        temperature: 0.7}
    - {id: agent_c, provider: openai, model: qwen/qwen-2.5-72b-instruct,         temperature: 0.7}
  pipeline_llm:
    {provider: openai, model: openai/gpt-4o-mini, temperature: 0.3}
```

(OpenRouter exposes Claude / Gemini / GPT *and* open-source models all
through the OpenAI-compatible endpoint, so a single key gives you
heterogeneous agents without juggling three different SDKs.)

### Cheap hosting comparison (May 2025 prices)

| Platform     | Strong open-source models                           | Pricing (per 1M in / out) | Notes                                |
|--------------|-----------------------------------------------------|---------------------------|--------------------------------------|
| **Groq**     | Llama 3.3 70B, Qwen 2.5 72B                         | ~$0.59 / $0.79            | Fastest inference; small free tier.  |
| **Together** | Llama 3.3 70B, Qwen 2.5 72B, DeepSeek V3            | ~$0.88 / $0.88            | Reliable, 128k context.              |
| **DeepInfra**| Llama 3.3 70B, Qwen 2.5 72B                         | ~$0.59 / $0.79            | Cheapest 70B-class.                  |
| **Fireworks**| Llama 3.3 70B, Mixtral, DeepSeek                    | ~$0.90 / $0.90            | Tool-calling support good.           |
| **OpenRouter** | All of the above + Claude/Gemini/GPT              | passthrough + ~5%         | One key, A/B test models trivially.  |
| OpenAI       | (closed-source) GPT-4o                              | $2.50 / $10               | Reference baseline.                  |

For this project, a typical 10-page paper costs about:

- **All-OpenAI baseline (GPT-4o everywhere):** ~$0.50 / paper.
- **OpenRouter with 70B open-source models:** ~$0.05–0.08 / paper.

**Recommendation for paper-writing experiments**: use OpenRouter so you can
A/B different model trios with one key — that's exactly the comparison
matrix you'll want for ablation studies. For production, drop down to
DeepInfra (cheapest) or Groq (fastest).

If you self-host (vLLM on a single A100 ≈ $1.50/hr): only worth it above
~30 papers/hour sustained, otherwise pay-as-you-go aggregators win.

---

## Project structure

```
RefinedSummarization/
├── HANDOFF.md          # spec (in parent repo)
├── README.md           # this file
├── pyproject.toml
├── .env / .env.example # credentials
├── config/
│   ├── default.yaml    # model & constraint config
│   └── prompts.yaml    # 4 agent prompts (Jinja2 templates)
├── src/
│   ├── cli.py          # CLI entry (stdout=JSON, stderr=logs)
│   ├── server.py       # FastAPI entry
│   ├── pipeline.py     # DebatePipeline orchestrator
│   ├── config/         # settings + YAML config loader
│   ├── agents/         # 4 agents: summarizer/verifier/retriever/refiner
│   ├── llm_clients/    # OpenAI/Anthropic/Google + abstract base
│   ├── preprocessing/  # PDF parsing + paragraph short-summary
│   ├── postprocessing/ # Markdown formatter
│   ├── schemas/        # all Pydantic models
│   └── utils/          # logging, etc.
├── scripts/
│   └── export_types.py # Pydantic → TypeScript .d.ts
├── tests/              # 23 unit + 3 E2E (mocked) + 1 real-LLM E2E
├── examples/
│   └── run_example.py
└── outputs/            # JSON / Markdown produced by runs
```

---

## What this module does **not** do

(See HANDOFF.md §10 for the full out-of-scope list.)

- ❌ Multi-round debate (single round only — refined output is final).
- ❌ Inter-agent visibility (the 3 initial agents don't see each other).
- ❌ Front-end / website rendering.
- ❌ Comparison harness vs. single-LLM baseline (separate evaluation project).
- ❌ Model fine-tuning.

## Integration with the parent TypeScript project

Two paths (handoff §13):

- **Subprocess** — `child_process.spawn("python", ["-m", "src.cli", "--pdf", ...])`
  reads stdout for the JSON. Use this for local single-shot runs.
- **HTTP** — POST a PDF to `/summarize` on the FastAPI server. Use this for
  multi-tenant / website backend.

Pydantic schemas can be exported to `.d.ts` via:

```bash
python scripts/export_types.py path/to/typescript-project/types/summarizer.d.ts
```
