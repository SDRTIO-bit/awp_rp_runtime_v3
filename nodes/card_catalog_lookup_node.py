"""AWPV2CardCatalogLookup — 查询 CardDefinition 目录."""

from __future__ import annotations
from typing import Any


class AWPV2CardCatalogLookup:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {"card_id": ("STRING", {"default": ""})},
                "optional": {"card_version": ("INT", {"default": 0}), "status_filter": ("STRING", {"default": ""})}}

    RETURN_TYPES = ("CARD_DEFINITION", "INT")
    RETURN_NAMES = ("card_definition", "found_count")
    FUNCTION = "execute"
    CATEGORY = "AWP/CardImport"

    def execute(self, card_id: str, card_version: int = 0, status_filter: str = "") -> tuple[dict, int]:
        return ({}, 0)
