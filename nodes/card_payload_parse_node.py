"""AWPV2CardPayloadParse — 解析角色卡结构."""

from __future__ import annotations
import json
from typing import Any


class AWPV2CardPayloadParse:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {"raw_payload": ("CARD_RAW_PAYLOAD",)}}

    RETURN_TYPES = ("PARSED_PROFILE", "PARSED_GREETINGS", "PARSED_WORLDBOOK", "PARSED_HINTS")
    RETURN_NAMES = ("profile", "greetings", "worldbook_entries", "structure_hints")
    FUNCTION = "execute"
    CATEGORY = "AWP/CardImport"

    def execute(self, raw_payload: str) -> tuple[dict, list, list, dict]:
        from ..runtime.card_payload_parser import CardPayloadParser
        data = json.loads(raw_payload)
        p = CardPayloadParser()
        return (p.parse_profile(data).to_dict(), [g.to_dict() for g in p.parse_greetings(data)],
                [e.to_dict() for e in p.parse_worldbook_entries(data)], p.parse_structure_hints(data).to_dict())
