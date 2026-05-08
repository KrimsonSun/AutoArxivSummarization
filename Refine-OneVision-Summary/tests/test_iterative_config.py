"""Smoke tests for the iterative refinement config + dynamic-refiner logic."""
from __future__ import annotations

import pytest

from src.config.loader import load_config
from src.pipeline import OneVisionPipeline


def test_default_config_is_single_pass_static_refiner():
    c = load_config("config/default.yaml")
    assert c.pipeline.refinement.rounds == 1
    assert c.pipeline.refinement.use_winner_as_refiner is False


def test_iterative_config_loaded():
    c = load_config("config/iterative.yaml")
    assert c.pipeline.refinement.rounds == 3
    assert c.pipeline.refinement.use_winner_as_refiner is True
    assert c.pipeline.max_summary_words == 1000


def test_pipeline_picks_winner_client_when_use_winner_true(monkeypatch):
    """When use_winner_as_refiner is true and the winner agent_id matches one
    of the initial clients, _refiner_for_winner returns a refiner whose
    client is the matched initial client (not pipeline_llm)."""
    c = load_config("config/iterative.yaml")
    p = OneVisionPipeline(c)
    refiner_qwen = p._refiner_for_winner("agent_qwen")
    qwen_client = next(cl for aid, cl in p._initial_clients if aid == "agent_qwen")
    assert refiner_qwen.client is qwen_client

    refiner_llama = p._refiner_for_winner("agent_llama")
    llama_client = next(cl for aid, cl in p._initial_clients if aid == "agent_llama")
    assert refiner_llama.client is llama_client


def test_pipeline_falls_back_when_winner_unknown():
    """Unknown winner agent_id → fall back to default (pipeline_llm) refiner."""
    c = load_config("config/iterative.yaml")
    p = OneVisionPipeline(c)
    refiner = p._refiner_for_winner("agent_does_not_exist")
    assert refiner is p._default_refiner


def test_default_config_uses_static_refiner_regardless_of_winner():
    """Even with a known winner, default config should not swap the refiner."""
    c = load_config("config/default.yaml")
    p = OneVisionPipeline(c)
    refiner = p._refiner_for_winner("agent_qwen")
    assert refiner is p._default_refiner
