"""Tests for project-scoped LLM snapshot injection into the Pi role runtime."""

from __future__ import annotations

from awp_rp_runtime_v3.runtime.novel_llm_factory import NovelLLMFactory
from awp_rp_runtime_v3.runtime.novel_role_runtime import create_novel_role_runtime


def test_role_runtime_resolver_uses_injected_snapshot(monkeypatch):
    """A role runtime built with a snapshot must resolve from the snapshot,
    not the global singleton, even after the singleton is mutated."""
    monkeypatch.delenv("NOVEL_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("NOVEL_LLM_MODEL", raising=False)

    factory = NovelLLMFactory.get_instance()
    factory.reset()

    snap_a = NovelLLMFactory.for_project(
        "proj-a", {"writer": {"model": "role-model-a", "max_tokens": 7777}}
    )
    runtime = create_novel_role_runtime(snapshot=snap_a)

    resolver = runtime._override_connection_resolver
    connection = resolver("writer")
    assert connection["model"] == "role-model-a"
    assert connection["max_tokens"] == 7777

    # Singleton receives project B's overrides
    factory.set_project_overrides(
        {"writer": {"model": "role-model-b", "max_tokens": 1111}}
    )

    # Resolver must still resolve project A's snapshot
    connection_after = resolver("writer")
    assert connection_after["model"] == "role-model-a"
    assert connection_after["max_tokens"] == 7777

    factory.reset()


def test_role_runtime_resolver_defaults_to_singleton_without_snapshot(monkeypatch):
    """Without an injected snapshot, the resolver must read the singleton
    (preserving legacy/default behavior)."""
    monkeypatch.delenv("NOVEL_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("NOVEL_LLM_MODEL", raising=False)

    factory = NovelLLMFactory.get_instance()
    factory.reset()
    factory.set_project_overrides(
        {"writer": {"model": "default-model", "max_tokens": 3333}}
    )

    runtime = create_novel_role_runtime()
    resolver = runtime._override_connection_resolver
    connection = resolver("writer")
    assert connection["model"] == "default-model"
    assert connection["max_tokens"] == 3333

    factory.reset()