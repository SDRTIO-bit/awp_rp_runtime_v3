"""AWPV2CardNormalize — 规范化角色卡数据."""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any


class AWPV2CardNormalize:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {
            "source_snapshot": ("SOURCE_SNAPSHOT",), "profile": ("PARSED_PROFILE",),
            "greetings": ("PARSED_GREETINGS",), "worldbook_entries": ("PARSED_WORLDBOOK",),
            "structure_hints": ("PARSED_HINTS",), "quarantine_records": ("QUARANTINE_RECORDS",),
        }}

    RETURN_TYPES = ("CARD_DEFINITION",)
    RETURN_NAMES = ("card_definition",)
    FUNCTION = "execute"
    CATEGORY = "AWP/CardImport"

    def execute(self, source_snapshot: dict, profile: dict, greetings: list,
                worldbook_entries: list, structure_hints: dict, quarantine_records: list) -> tuple[dict]:
        from ..runtime.card_greeting_sanitizer import sanitize_greeting_content
        from ..runtime.card_worldbook_chunk_builder import build_all_chunks
        from ..contracts.card_definition import CardDefinition, CardDefinitionStatus
        from ..contracts.card_greeting import CardGreeting
        from ..contracts.card_worldbook_entry import CardWorldbookEntry

        sh = source_snapshot.get("source_hash", "")
        card_id = f"card_{sh[:16]}"
        now = datetime.now(timezone.utc).isoformat()
        san_g, all_q = [], list(quarantine_records)
        for g in greetings:
            gobj = CardGreeting.from_dict(g)
            safe, gq = sanitize_greeting_content(gobj.safe_display_content, gobj.greeting_id, gobj.source_path)
            all_q.extend([r.to_dict() for r in gq])
            san_g.append({**g, "safe_display_content": safe, "quarantine_refs": [r.record_id for r in gq]})
        entries, chunks = build_all_chunks([CardWorldbookEntry.from_dict(e) for e in worldbook_entries])
        kc: dict[str, int] = {}
        for q in all_q:
            k = q.get("kind", "") if isinstance(q, dict) else ""
            kc[k] = kc.get(k, 0) + 1
        defn = CardDefinition(card_id=card_id, card_version=1, source_id=source_snapshot.get("source_id", ""),
                              source_hash=sh, name=profile.get("name", "Unknown"), display_name=profile.get("name", "Unknown"),
                              status=CardDefinitionStatus.STAGED, profile=profile, greetings=san_g,
                              worldbook_catalog=[e.to_dict() for e in entries],
                              worldbook_chunks=[c.to_dict() for c in chunks],
                              structure_hints=structure_hints,
                              quarantine_summary={"total": len(all_q), "by_kind": kc},
                              created_at=now, updated_at=now)
        return (defn.to_dict(),)
