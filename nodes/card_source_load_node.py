"""AWPV2CardSourceLoad — 读取角色卡源文件."""

from __future__ import annotations
from typing import Any


class AWPV2CardSourceLoad:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {"source_path": ("STRING", {"default": ""})},
                "optional": {"source_filename": ("STRING", {"default": ""})}}

    RETURN_TYPES = ("SOURCE_SNAPSHOT", "CARD_RAW_PAYLOAD")
    RETURN_NAMES = ("source_snapshot", "raw_payload")
    FUNCTION = "execute"
    CATEGORY = "AWP/CardImport"

    def execute(self, source_path: str, source_filename: str = "") -> tuple[dict[str, Any], str]:
        from ..runtime.card_source_loader import load_card_source
        from datetime import datetime, timezone
        import json
        snap, payload = load_card_source(source_path, source_filename, datetime.now(timezone.utc).isoformat())
        return (snap.to_dict(), json.dumps(payload, ensure_ascii=False))
