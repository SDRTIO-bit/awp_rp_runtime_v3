"""CardPayloadParser — parse SillyTavern V3 character card payloads."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from ..contracts.card_profile import CardProfile
from ..contracts.card_greeting import CardGreeting
from ..contracts.card_worldbook_entry import CardWorldbookEntry
from ..contracts.card_structure_hints import CardStructureHints


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _trunc(text: str, n: int = 200) -> str:
    return text[:n] + "..." if len(text) > n else text


def _str(v: Any, d="") -> str:
    return d if v is None else v if isinstance(v, str) else str(v)


def _list(v: Any) -> list:
    return [] if v is None else v if isinstance(v, list) else []


def _dict(v: Any) -> dict:
    return {} if v is None else v if isinstance(v, dict) else {}


class CardPayloadParser:

    def parse_profile(self, data: dict[str, Any]) -> CardProfile:
        d = _dict(data.get("data"))
        name = _str(d.get("name"), "Unknown")
        tags_raw = d.get("tags", [])
        tags = [t.strip() for t in tags_raw.split(",")] if isinstance(tags_raw, str) else [str(t) for t in tags_raw if t] if isinstance(tags_raw, list) else []
        ext = _dict(d.get("extensions"))
        ext_sum = {}
        for k in ("tags", "world", "talkativeness"):
            if k in ext:
                ext_sum[k] = ext[k]
        return CardProfile(
            name=name, description=_str(d.get("description")),
            personality=_str(d.get("personality")), scenario=_str(d.get("scenario")),
            mes_example=_str(d.get("mes_example")),
            creator_notes=_str(d.get("creator_notes") or d.get("creatorcomment")),
            tags=tags, extensions_summary=ext_sum,
            source_paths=["data.name", "data.description", "data.personality",
                          "data.scenario", "data.mes_example"],
        )

    def parse_greetings(self, data: dict[str, Any]) -> list[CardGreeting]:
        d = _dict(data.get("data"))
        gs: list[CardGreeting] = []
        fm = _str(d.get("first_mes"))
        if fm:
            gs.append(CardGreeting(greeting_id="g0", index=0, label="Default",
                                   safe_display_content=fm, content_hash=_sha256(fm),
                                   is_default=True, source_path="data.first_mes"))
        for i, alt in enumerate(_list(d.get("alternate_greetings"))):
            if isinstance(alt, dict):
                content = _str(alt.get("greeting") or alt.get("content") or alt.get("text", ""))
                label = _str(alt.get("label"), f"Alternate {i + 1}")
            elif isinstance(alt, str):
                content, label = alt, f"Alternate {i + 1}"
            else:
                continue
            if content:
                gs.append(CardGreeting(greeting_id=f"g{i+1}", index=i+1, label=label,
                                       safe_display_content=content, content_hash=_sha256(content),
                                       source_path=f"data.alternate_greetings[{i}]"))
        return gs

    def parse_worldbook_entries(self, data: dict[str, Any]) -> list[CardWorldbookEntry]:
        d = _dict(data.get("data"))
        book = _dict(d.get("character_book"))
        entries: list[CardWorldbookEntry] = []
        for i, raw in enumerate(_list(book.get("entries"))):
            if not isinstance(raw, dict):
                continue
            content = _str(raw.get("content"))
            if not content:
                continue
            keys_raw = raw.get("keys", [])
            keys = [k.strip() for k in keys_raw.split(",")] if isinstance(keys_raw, str) else [str(k) for k in keys_raw if k] if isinstance(keys_raw, list) else []
            sk_raw = raw.get("secondary_keys", [])
            sk = [str(k) for k in sk_raw if k] if isinstance(sk_raw, list) else []
            uid = raw.get("uid")
            try:
                uid = int(uid) if uid is not None else None
            except (ValueError, TypeError):
                uid = None
            disabled = bool(raw.get("disable", False))
            ef = raw.get("enabled", True)
            if ef is False or ef == "false":
                disabled = True
            act_raw = {}
            for k in ("position", "extensions", "display", "probability", "useProbability",
                       "scanDepth", "recursive", "delayUntilRecursion", "group",
                       "groupOverride", "groupWeight", "preventGroupRecursion",
                       "sticky", "cooldown", "delay"):
                if k in raw:
                    act_raw[k] = raw[k]
            entries.append(CardWorldbookEntry(
                entry_id=f"wb_{uid}" if uid is not None else f"wb_{i}",
                source_uid=uid,
                title=_str(raw.get("comment") or raw.get("name")),
                content=content, keys=keys, secondary_keys=sk,
                priority=int(raw.get("priority", 0) or 0),
                enabled=not disabled,
                constant=bool(raw.get("constant", False)),
                selective=bool(raw.get("selective", False)),
                activation_raw=act_raw, source_order=i,
                source_path=f"data.character_book.entries[{i}]",
                metadata={"original_disable": raw.get("disable", False), "original_enabled": raw.get("enabled", True)},
            ))
        return entries

    def parse_structure_hints(self, data: dict[str, Any]) -> CardStructureHints:
        d = _dict(data.get("data"))
        desc = _str(d.get("description"))
        pers = _str(d.get("personality"))
        ext = _dict(d.get("extensions"))
        return CardStructureHints(
            phase_hints=self._phases(desc, pers),
            event_hints=self._events(ext),
            variable_hints=self._vars(ext),
            relationship_hints=self._rels(desc, pers),
        )

    def _phases(self, desc: str, pers: str) -> list[dict[str, Any]]:
        text = f"{desc}\n{pers}"
        hints: list[dict[str, Any]] = []
        for m in re.finditer(r"(?:Phase|Stage|Arc)\s*(\d+)\s*[:\-]\s*(.+?)(?:\n|$)", text, re.I):
            hints.append({"phase_number": int(m.group(1)), "description": _trunc(m.group(2).strip(), 300), "source": "description/personality"})
        for m in re.finditer(r"阶段\s*(\d+)\s*[:\-：]\s*(.+?)(?:\n|$)", text):
            hints.append({"phase_number": int(m.group(1)), "description": _trunc(m.group(2).strip(), 300), "source": "description/personality"})
        for label, pat in [("early", r"(初期|前期|早期)"), ("mid", r"(中期|中段)"), ("late", r"(后期|晚期|末期)")]:
            for m in re.finditer(pat + r"\s*[:\-：]\s*(.+?)(?:\n|$)", text):
                hints.append({"phase_label": label, "description": _trunc(m.group(2).strip(), 300), "source": "description/personality"})
        return hints

    def _events(self, ext: dict) -> list[dict[str, Any]]:
        hints: list[dict[str, Any]] = []
        ev_kw = {"事件", "event", "触发", "trigger", "stage", "phase", "阶段", "条件"}
        for entry in _list(_dict(ext.get("worldbook")).get("entries")):
            if not isinstance(entry, dict):
                continue
            kr = entry.get("keys", entry.get("key", []))
            keys = [k.strip() for k in kr.split(",")] if isinstance(kr, str) else [str(k) for k in kr] if isinstance(kr, list) else []
            for k in keys:
                if k.lower() in ev_kw:
                    hints.append({"key": k, "content": _trunc(_str(entry.get("content")), 200), "comment": _str(entry.get("comment")), "source": "extensions.worldbook.entries"})
                    break
        return hints

    def _vars(self, ext: dict) -> list[dict[str, Any]]:
        hints: list[dict[str, Any]] = []
        for s in _list(_dict(ext.get("tavern_helper")).get("scripts")):
            if not isinstance(s, dict):
                continue
            c = _str(s.get("content") or s.get("code", ""))
            for m in re.finditer(r"registerMvuSchema\s*\(\s*\{([^}]+)\}", c, re.DOTALL):
                for fm in re.finditer(r"(\w+)\s*:\s*z\.\w+", m.group(1)):
                    hints.append({"variable_path": fm.group(1), "detection": "registerMvuSchema", "source": "extensions.tavern_helper.scripts"})
            for vm in re.finditer(r"\{\{(setvar|getvar|addvar):(\w+)", c):
                hints.append({"variable_path": vm.group(2), "detection": vm.group(1), "source": "extensions.tavern_helper.scripts"})
        return hints

    def _rels(self, desc: str, pers: str) -> list[dict[str, Any]]:
        text = f"{desc}\n{pers}"
        hints: list[dict[str, Any]] = []
        for m in re.finditer(r"(?:relationship|关系)\s*[:\-：]\s*(.+?)(?:\n|$)", text, re.I):
            hints.append({"kind": "explicit", "text": _trunc(m.group(0).strip(), 200), "source": "description/personality"})
        return hints
