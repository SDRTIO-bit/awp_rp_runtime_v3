"""PrivateTranscriptCollector — saves accepted turn text to local-only artifacts.

Only writes when:
  1. AWP_REAL_LLM_SAVE_PRIVATE_TRANSCRIPT=1
  2. TurnRecord commit succeeded
  3. Quality status = accepted

Never writes rejected, draft, or revised-away text.
Never enters CI artifacts, Git, or diagnostic API.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class PrivateTranscriptCollector:
    """Collects accepted turn text for local-only private transcript.

    Artifacts are written to: artifacts/private-real-llm/<workflowRunId>/
    This directory is .gitignored and never enters CI.
    """

    def __init__(self, workflow_run_id: str, base_dir: str | Path = "artifacts/private-real-llm"):
        self._workflow_run_id = workflow_run_id
        self._base_dir = Path(base_dir)
        self._enabled = os.environ.get("AWP_REAL_LLM_SAVE_PRIVATE_TRANSCRIPT", "0") == "1"
        self._entries: list[dict[str, Any]] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    def collect(
        self,
        turn_index: int,
        turn_id: str,
        turn_record_id: str,
        accepted_text: str,
        quality_status: str,
    ) -> bool:
        """Collect an accepted turn's text.

        Returns True if collected, False if skipped.
        Only collects when enabled AND quality_status == 'accepted'.
        """
        if not self._enabled:
            return False

        if quality_status != "accepted":
            return False

        if not accepted_text:
            return False

        entry = {
            "turn_index": turn_index,
            "turn_id": turn_id,
            "turn_record_id": turn_record_id,
            "accepted_text_hash": hashlib.sha256(accepted_text.encode("utf-8")).hexdigest(),
            "accepted_text": accepted_text,
            "quality_status": quality_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._entries.append(entry)
        return True

    def flush(self) -> Path | None:
        """Write all collected entries to disk.

        Returns the output directory path, or None if nothing to write.
        """
        if not self._entries:
            return None

        output_dir = self._base_dir / self._workflow_run_id
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / "private_transcript.json"
        output_file.write_text(
            json.dumps(self._entries, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return output_dir

    @property
    def collected_count(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> list[dict[str, Any]]:
        return list(self._entries)
