"""ComfyUI API Client — thin HTTP/WS client for test automation.

Connects to a local ComfyUI instance to submit API workflows,
collect execution events, and query history.

Only used by comfy-api-e2e suite.
Never calls real models — uses Fake Adapters and test stores.
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
from typing import Any


class ComfyAPIClient:
    """Thin client for ComfyUI HTTP + WebSocket API."""

    def __init__(self, base_url: str = "http://127.0.0.1:8188") -> None:
        self.base_url = base_url.rstrip("/")
        self._client_id = None

    def set_client_id(self, client_id: str) -> None:
        self._client_id = client_id

    def is_available(self) -> bool:
        """Check if ComfyUI is reachable."""
        try:
            req = urllib.request.Request(f"{self.base_url}/system_stats", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def get_system_stats(self) -> dict[str, Any] | None:
        """Get ComfyUI system stats."""
        try:
            req = urllib.request.Request(f"{self.base_url}/system_stats", method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError):
            return None

    def queue_prompt(self, prompt_workflow: dict[str, Any]) -> dict[str, Any] | None:
        """Submit a prompt workflow to ComfyUI.

        Args:
            prompt_workflow: The API workflow dict (prompt format).

        Returns:
            {"prompt_id": "...", "number": N} or None on failure.
        """
        payload = json.dumps({
            "prompt": prompt_workflow,
            "client_id": self._client_id or "awp-test-runner",
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/prompt",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError) as exc:
            raise EnvironmentError(f"Failed to queue prompt: {exc}") from exc

    def get_history(self, prompt_id: str) -> dict[str, Any] | None:
        """Get execution history for a prompt_id."""
        try:
            req = urllib.request.Request(
                f"{self.base_url}/history/{prompt_id}", method="GET"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError):
            return None

    def get_queue(self) -> dict[str, Any] | None:
        """Get current execution queue."""
        try:
            req = urllib.request.Request(f"{self.base_url}/queue", method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, OSError):
            return None

    def interrupt(self) -> bool:
        """Interrupt current execution."""
        try:
            payload = json.dumps({}).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/interrupt",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def wait_for_completion(
        self,
        prompt_id: str,
        timeout_seconds: float = 120.0,
        poll_interval: float = 1.0,
    ) -> dict[str, Any] | None:
        """Poll history until prompt completes or timeout.

        Returns:
            History entry for the prompt, or None on timeout.
        """
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            history = self.get_history(prompt_id)
            if history and prompt_id in history:
                return history[prompt_id]
            time.sleep(poll_interval)
        return None
