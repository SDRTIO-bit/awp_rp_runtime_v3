"""Prompt loader — loads agent system prompts from external .md files."""

from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

_cache: dict[str, str] = {}


def load_prompt(name: str) -> str:
    """Load a prompt from prompts/{name}.md. Cached after first read."""
    if name not in _cache:
        path = _PROMPTS_DIR / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        _cache[name] = path.read_text(encoding="utf-8").strip()
    return _cache[name]


def reload_prompt(name: str) -> str:
    """Force reload a prompt (for hot-reload during development)."""
    _cache.pop(name, None)
    return load_prompt(name)
