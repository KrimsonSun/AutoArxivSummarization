# Self-host on Colab — when to switch and how

The default config uses OpenRouter (managed API) because Phase 1
(RefinedSummarization + Evaluation) does NOT need token-level logits.
Switch to self-hosted vLLM only when you're ready to add SpecEM-style
scoring (Phase 2), which requires `prompt_logprobs` — a feature the
OpenAI chat-completions API spec does not include.

## Decision matrix

| You need to… | Use OpenRouter | Self-host vLLM |
|---|:---:|:---:|
| Run RefinedSummarization (verifier/retriever/refiner) | ✅ default | ✅ works |
| Run Evaluation (claim → BM25 → NLI) | ✅ default | ✅ works |
| Score arbitrary text with `prompt_logprobs` (SpecEM) | ❌ unsupported | ✅ required |
| Pin exact inference engine + quantization for paper | ⚠️ doc as caveat | ✅ full control |
| 30 papers, no rush | ~$5–15 total | ~$50/month Colab Pro+ |
| 1000+ papers, regular runs | rate limit pain | wins on cost |

## Architecture: NO code changes needed

All LLM calls go through the OpenAI-compatible client. Switching to
self-host is a one-line config change:

```bash
# Before (OpenRouter):
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-v1-...

# After (self-hosted vLLM via ngrok):
OPENAI_BASE_URL=https://abc123.ngrok.app/v1
OPENAI_API_KEY=any-string-vllm-doesnt-check
```

That's it. `config/default.yaml` model IDs stay the same as long as you
load the same models into vLLM.

## Colab setup (one notebook, ~3–5 cells)

### Cell 1 — install vLLM + ngrok

```python
!pip install -q vllm pyngrok
```

### Cell 2 — start vLLM as a background server

vLLM exposes an OpenAI-compatible endpoint at `:8000/v1`. With the
`--enable-prefix-caching` flag, identical prompt prefixes (which we
have a lot of in the verifier stage) are cached.

```python
import subprocess, time

# A100 (Colab Pro+) can fit Llama 3.3 70B at 4-bit AWQ.
# T4 (free) can only fit ~7B models at 4-bit.
MODEL = "meta-llama/Llama-3.3-70B-Instruct"      # or "TheBloke/Llama-3.3-70B-AWQ"
QUANT = "awq"                                     # or "bitsandbytes" / None for fp16

cmd = (
    f"python -m vllm.entrypoints.openai.api_server "
    f"--model {MODEL} "
    f"--quantization {QUANT} "
    f"--max-model-len 16384 "
    f"--enable-prefix-caching "
    f"--port 8000"
)
proc = subprocess.Popen(cmd.split())
time.sleep(180)  # weights take 5–15 minutes to load on first run
print("vLLM ready at http://localhost:8000/v1")
```

### Cell 3 — expose via ngrok (so this notebook isn't the consumer)

If you want to run RefinedSummarization / Evaluation FROM A DIFFERENT
notebook (or your laptop), expose the vLLM endpoint:

```python
from pyngrok import ngrok
ngrok.set_auth_token("YOUR_NGROK_TOKEN")     # https://dashboard.ngrok.com/get-started/your-authtoken
public_url = ngrok.connect(8000).public_url
print(f"vLLM accessible at: {public_url}/v1")
# Copy this URL into OPENAI_BASE_URL in your other notebook's .env
```

### Cell 4 — OR run RefinedSummarization in the SAME notebook

Skip ngrok and just point to localhost:

```python
import os
os.environ["OPENAI_BASE_URL"] = "http://localhost:8000/v1"
os.environ["OPENAI_API_KEY"]  = "EMPTY"   # vLLM doesn't validate
os.environ["DEV_MODE"]        = "0"

%cd /content/AutoArxiv/RefinedSummarization
!python -m src.cli --pdf /tmp/paper.pdf --save
```

## SpecEM-specific: enabling prompt_logprobs

The OpenAI chat-completions schema doesn't carry `prompt_logprobs`.
For SpecEM scoring you'll either:

1. **Use vLLM's native completion endpoint** (`/v1/completions`, not
   chat) which DOES accept `prompt_logprobs=N` and returns logprobs
   for every token in the supplied prompt+continuation. The current
   LLMClient hits chat completions; for SpecEM you'd add a parallel
   `score()` method that hits `/v1/completions` directly.

2. **Use vLLM's Python API directly** (skip HTTP entirely) for
   scoring-only calls:

   ```python
   from vllm import LLM, SamplingParams
   llm = LLM(model=MODEL, quantization=QUANT)
   sp = SamplingParams(temperature=0.0, max_tokens=1, prompt_logprobs=1)
   outputs = llm.generate([prompt + candidate], sp)
   token_logprobs = outputs[0].prompt_logprobs   # list[dict[token_id -> Logprob]]
   avg = sum(lp.logprob for d in token_logprobs[len(prompt_ids):] for lp in d.values()) / N
   ```

   This is what SpecEM's "average logits over candidate tokens" maps to.

## When to invest the time

**Stay on OpenRouter** until at least ONE of these is true:

- [ ] Phase 1 numbers are too close to baseline → need SpecEM upgrade
- [ ] Reviewer pushed back on API reproducibility caveat → need pinned env
- [ ] Running 1000+ paper experiment → API cost overtakes Colab Pro+
- [ ] Want to inspect attention / hidden states for analysis (Phase 3)

**Don't pre-optimize**. Phase 1 with OpenRouter on 30 papers will tell
you everything you need to decide whether Phase 2 is worth $50/month
and the operational complexity.

## Cost / time comparison for a 30-paper run

| Path | Wall-clock | Money | Operational complexity |
|---|---|---|---|
| OpenRouter (current default) | ~30–60 min | $5–15 | minimal |
| Colab Pro+ A100 + vLLM (70B int4) | ~4–8 hours | $50/mo flat | medium |
| Colab Free T4 + vLLM (7B int4) | ~6–12 hours | $0 | medium, weaker quality |
| AWS A100 hourly + vLLM | ~3–6 hours | $20–40 | high |

For Phase 1 paper-grade numbers, **OpenRouter wins**. Self-host's value
unlocks at Phase 2 (SpecEM) or at scale (>500 papers).
