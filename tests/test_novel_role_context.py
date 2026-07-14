import pytest

from awp_rp_runtime_v3.runtime.novel_role_context import (
    NovelRoleContextError,
    get_novel_role_context,
    novel_role_scope,
)


def test_role_scope_exposes_project_bound_context_and_restores_outer_scope():
    outer_registry = object()
    inner_registry = object()

    with novel_role_scope(
        registry=outer_registry,
        project_id="outer",
        chapter_index=2,
        revision=1,
        phase="plan",
    ):
        assert get_novel_role_context().project_id == "outer"
        with novel_role_scope(
            registry=inner_registry,
            project_id="inner",
            chapter_index=3,
            revision=2,
            phase="beat:1",
        ):
            context = get_novel_role_context()
            assert context.registry is inner_registry
            assert context.project_id == "inner"
            assert context.chapter_index == 3
            assert context.revision == 2
            assert context.phase == "beat:1"
        assert get_novel_role_context().registry is outer_registry


def test_get_role_context_fails_outside_engine_scope():
    with pytest.raises(NovelRoleContextError, match="not active"):
        get_novel_role_context()

