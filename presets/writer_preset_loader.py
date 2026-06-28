"""Writer Preset Loader — loads writer presets from presets/writer/ directory.

Presets are plain text files containing writing guidelines, style constraints,
banned word lists, and other writer instructions. They are injected into the
Writer's system prompt at generation time.

Format:
  presets/writer/<name>.txt — plain text, UTF-8, no template markers.

Usage:
  loader = WriterPresetLoader()
  preset_text = loader.load("kedai_heavy_v1")
  # preset_text is prepended to the Writer's system prompt
"""

from __future__ import annotations

from pathlib import Path


class WriterPresetLoader:
    """Load writer preset files from the presets/writer directory."""

    def __init__(self, presets_dir: str | Path | None = None) -> None:
        if presets_dir is None:
            presets_dir = Path(__file__).resolve().parent / "writer"
        self.presets_dir = Path(presets_dir)

    def load(self, preset_name: str) -> str:
        """Load a preset by name (without .txt extension).

        Returns the preset text, or empty string if preset not found.
        """
        if not preset_name:
            return ""

        path = self.presets_dir / f"{preset_name}.txt"
        if not path.exists():
            # Try the raw name
            path = self.presets_dir / preset_name
            if not path.exists():
                return ""  # Silent fallback: preset not found

        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()

    def list_presets(self) -> list[str]:
        """List all available preset names."""
        if not self.presets_dir.exists():
            return []
        return sorted([
            f.stem for f in self.presets_dir.glob("*.txt")
        ])

    def get_preset_path(self, preset_name: str) -> str:
        """Get the full path to a preset file (for node INPUT_TYPES validation)."""
        if not preset_name:
            return ""
        path = self.presets_dir / f"{preset_name}.txt"
        if path.exists():
            return str(path)
        alt = self.presets_dir / preset_name
        return str(alt) if alt.exists() else ""


# Singleton for convenience
_loader: WriterPresetLoader | None = None


def load_writer_preset(preset_name: str) -> str:
    """Convenience function to load a writer preset."""
    global _loader
    if _loader is None:
        _loader = WriterPresetLoader()
    return _loader.load(preset_name)
