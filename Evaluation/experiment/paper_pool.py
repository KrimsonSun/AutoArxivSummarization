"""Curated pool of ~30 recent cs.LG / cs.AI / cs.CL arXiv papers.

We sample N papers from this pool with a fixed random seed for reproducibility.
The pool spans different sub-areas (NLP architecture, RL, fine-tuning,
quantization, agents, multimodal, etc.) so the experiment isn't biased
toward any one sub-field.

Each entry is just an arXiv ID — we download the PDF on demand from
``https://arxiv.org/pdf/<id>``.
"""
from __future__ import annotations

import random

# 30 well-known papers from 2017–2024, diverse subfields.
PAPER_POOL: list[str] = [
    # --- NLP / Transformers ---
    "1706.03762",  # Attention Is All You Need
    "1810.04805",  # BERT
    "2005.14165",  # GPT-3
    "2104.08691",  # The Power of Scale for Parameter-Efficient Prompt Tuning
    "2106.09685",  # LoRA
    "2310.06825",  # Mistral 7B
    "2402.17764",  # The Era of 1-bit LLMs
    # --- Pretraining / Scaling ---
    "2305.10403",  # PaLM 2 Technical Report
    "2204.02311",  # PaLM
    "2203.15556",  # Chinchilla (Training Compute-Optimal LLMs)
    "2001.08361",  # Scaling Laws for Neural Language Models
    # --- Alignment / RLHF ---
    "2203.02155",  # InstructGPT
    "2305.18290",  # DPO
    "2204.05862",  # Constitutional AI
    # --- Reasoning / Agents ---
    "2201.11903",  # Chain-of-Thought
    "2210.03629",  # ReAct
    "2305.10601",  # Tree of Thoughts
    "2308.08155",  # AutoGen
    # --- Vision / Multimodal ---
    "2010.11929",  # ViT
    "2103.00020",  # CLIP
    "2204.06125",  # DALL-E 2 (unCLIP)
    "2304.02643",  # Segment Anything
    # --- Diffusion ---
    "2006.11239",  # DDPM
    "2112.10752",  # Latent Diffusion / Stable Diffusion
    # --- RL ---
    "1707.06347",  # PPO
    "2305.14233",  # RLAIF
    # --- Retrieval / RAG ---
    "2005.11401",  # RAG (Retrieval-Augmented Generation)
    "2004.04906",  # DPR (Dense Passage Retrieval)
    # --- Efficiency ---
    "2106.04561",  # FlashAttention's predecessor (Linformer)
    "2205.14135",  # FlashAttention
]


def sample(n: int = 7, seed: int = 42) -> list[str]:
    """Reproducible random sample. Same seed → same papers always."""
    rng = random.Random(seed)
    return rng.sample(PAPER_POOL, n)
