"""AWPV2CardDefinitionFixtureLoad — loads a ready CardDefinition from a JSON fixture.

Test-only node for real Comfy API acceptance scenarios.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any


class AWPV2CardDefinitionFixtureLoad:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "fixture_path": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("CARD_DEFINITION",)
    RETURN_NAMES = ("card_definition",)
    FUNCTION = "execute"
    CATEGORY = "AWP/CardSession"

    def execute(self, fixture_path: str) -> tuple[dict]:
        # Resolve relative to project root
        p = Path(fixture_path)
        if not p.is_absolute():
            # Try relative to project root
            project_root = Path(__file__).parent.parent
            p = project_root / fixture_path
        if not p.exists():
            raise FileNotFoundError(f"Fixture not found: {p}")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (data,)
