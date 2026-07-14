import pytest

from awp_rp_runtime_v3.runtime.novel_agent_runtime import (
    PiNovelAgentRuntime,
    create_novel_agent_runtime,
)
from awp_rp_runtime_v3.runtime.novel_brain import BrainCallbacks


class FakePiBridge:
    def __init__(self, *args, **kwargs):
        self.closed = False

    def handle_message(self, text):
        return text

    def reset(self):
        return None

    def abort(self):
        return None

    def close(self):
        self.closed = True


def test_pi_is_default(monkeypatch, tmp_path):
    monkeypatch.delenv("NOVEL_AGENT_RUNTIME", raising=False)

    runtime = create_novel_agent_runtime(
        object(), BrainCallbacks(), tmp_path, "p1", bridge_factory=FakePiBridge
    )

    assert isinstance(runtime, PiNovelAgentRuntime)
    assert runtime.runtime_name == "Pi"


def test_legacy_requires_explicit_switch(monkeypatch, tmp_path):
    monkeypatch.setenv("NOVEL_AGENT_RUNTIME", "legacy")

    runtime = create_novel_agent_runtime(
        None, BrainCallbacks(), tmp_path, "p1", bridge_factory=FakePiBridge
    )

    assert runtime.runtime_name == "Legacy"


def test_unknown_runtime_never_falls_back(monkeypatch, tmp_path):
    monkeypatch.setenv("NOVEL_AGENT_RUNTIME", "other")

    with pytest.raises(ValueError, match="NOVEL_AGENT_RUNTIME"):
        create_novel_agent_runtime(
            object(), BrainCallbacks(), tmp_path, "p1", bridge_factory=FakePiBridge
        )
