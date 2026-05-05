# Colab quickstart

Open a fresh Colab notebook and paste the following into successive cells.
No GPU needed — every LLM call goes to OpenRouter.

## Cell 1 — clone + install

```python
!git clone <your-fork-url> RefinedSummarization  # or upload zip
%cd RefinedSummarization
!pip install -e ".[dev]" -q
```

## Cell 2 — set credentials

```python
import os
os.environ["OPENAI_API_KEY"]  = "sk-or-v1-xxxxxxxxxxxxxxxxxxxxxx"   # OpenRouter key
os.environ["OPENAI_BASE_URL"] = "https://openrouter.ai/api/v1"
os.environ["DEV_MODE"]        = "0"
```

## Cell 3 — sanity check

```python
!python -m pytest tests/ -q       # 23 unit + mocked-E2E tests, all should pass
```

## Cell 4 — pull a paper

```python
!mkdir -p tests/fixtures
!curl -sSL https://arxiv.org/pdf/1706.03762 -o tests/fixtures/sample_paper.pdf
```

## Cell 5 — run the pipeline

```python
!python -m src.cli \
    --pdf tests/fixtures/sample_paper.pdf \
    --output-format markdown \
    --save
```

Stdout = the rendered Markdown summary (or `--output-format json` for the
machine-readable form). Stderr = structured logs. The `--save` flag also
drops `outputs/<arxiv_id>.json` and `outputs/<arxiv_id>.md` next to the
project root.

## Cell 6 — try a different paper / config

```python
# Different arxiv id:
!curl -sSL https://arxiv.org/pdf/2305.10403 -o tests/fixtures/palm2.pdf
!python -m src.cli --pdf tests/fixtures/palm2.pdf --output-format markdown --save

# Switch to mutual peer review (3 LLMs each critique all 3 drafts):
import yaml, pathlib
cfg = pathlib.Path("config/default.yaml")
data = yaml.safe_load(cfg.read_text())
data["pipeline"]["verification_mode"] = "mutual_peer_review"
cfg.write_text(yaml.safe_dump(data))
!python -m src.cli --pdf tests/fixtures/palm2.pdf --output-format json --save
```

## Cost guardrail

Per 10-page paper on OpenRouter (Llama 3.3 70B + Qwen 2.5 72B + DeepSeek V3,
single-judge mode): expect **\~$0.05 – $0.15**. Mutual peer review mode
adds 2 extra verifier passes → **\~$0.10 – $0.25**. Set OpenRouter spending
caps at https://openrouter.ai/settings/credits before running batches.
