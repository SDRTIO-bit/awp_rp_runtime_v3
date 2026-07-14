"""Selectable novel-agent runtime adapters for the Textual novel UI."""

from __future__ import annotations

import os
from pathlib import Path

from .novel_brain import NovelBrain
from .novel_pi_bridge import NovelPiBridge


class PiNovelAgentRuntime:
    runtime_name = "Pi"
    supports_legacy_commands = False
    mode = "pi"
    web_search_enabled = False
    dl_server_url = ""
    dl_output_dir = ""
    _compress_count = 0

    def __init__(self, registry, callbacks, project_dir: Path, project_id: str, *, bridge_factory=NovelPiBridge):
        self._bridge = bridge_factory(
            registry,
            callbacks,
            project_dir=project_dir,
            project_id=project_id,
        )

    def handle_message(self, text: str) -> str:
        return self._bridge.handle_message(text)

    def reset(self) -> None:
        self._bridge.reset()

    def abort(self) -> None:
        self._bridge.abort()

    def close(self) -> None:
        self._bridge.close()


class LegacyNovelAgentRuntime:
    runtime_name = "Legacy"
    supports_legacy_commands = True

    def __init__(self, registry, callbacks, project_dir: Path, project_id: str):
        self._brain = NovelBrain(
            registry,
            callbacks=callbacks,
            db_path=str(project_dir / "novel.db"),
            novels_root=str(project_dir.parent),
            dl_output_dir=str(project_dir.parent.parent / "downloads"),
        )

    def __getattr__(self, name: str):
        return getattr(self._brain, name)

    def handle_message(self, text: str) -> str:
        return self._brain.handle_message(text)

    def reset(self) -> None:
        self._brain.reset()

    def abort(self) -> None:
        raise RuntimeError("Legacy NovelBrain does not support cancellation")

    def close(self) -> None:
        return None


def create_novel_agent_runtime(
    registry,
    callbacks,
    project_dir: Path,
    project_id: str,
    *,
    bridge_factory=NovelPiBridge,
):
    """Create the selected runtime without silently changing agent behavior."""

    runtime = os.environ.get("NOVEL_AGENT_RUNTIME", "pi").lower()
    if runtime == "pi":
        return PiNovelAgentRuntime(
            registry,
            callbacks,
            project_dir,
            project_id,
            bridge_factory=bridge_factory,
        )
    if runtime == "legacy":
        return LegacyNovelAgentRuntime(registry, callbacks, project_dir, project_id)
    raise ValueError(f"Unsupported NOVEL_AGENT_RUNTIME: {runtime}")
