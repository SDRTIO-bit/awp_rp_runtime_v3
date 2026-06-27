"""CardWorldbookChunkBuilder — deterministic worldbook entry chunking."""

from __future__ import annotations

import hashlib
import re

from ..contracts.card_worldbook_entry import CardWorldbookEntry
from ..contracts.card_worldbook_chunk import CardWorldbookChunk

CHUNK_SIZE = 1000
OVERLAP = 100
MIN_CHUNK = 100


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _keywords(text: str, n: int = 10) -> list[str]:
    words = re.findall(r"\b\w{4,}\b", text.lower())
    seen: set[str] = set()
    out: list[str] = []
    for w in words:
        if w not in seen:
            seen.add(w)
            out.append(w)
            if len(out) >= n:
                break
    return out


def build_chunks_for_entry(
    entry: CardWorldbookEntry, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP,
) -> list[CardWorldbookChunk]:
    content = entry.content
    if len(content) <= chunk_size:
        return []
    chunks: list[CardWorldbookChunk] = []
    offset, ordinal = 0, 0
    while offset < len(content):
        end = min(offset + chunk_size, len(content))
        if end < len(content):
            bs = max(offset + int(chunk_size * 0.8), offset)
            for i in range(end - 1, bs - 1, -1):
                if content[i] in ".。!！?？\n":
                    end = i + 1
                    break
        txt = content[offset:end]
        if len(txt) < MIN_CHUNK and ordinal > 0 and chunks:
            prev = chunks[-1]
            merged = prev.content + txt
            chunks[-1] = CardWorldbookChunk(
                chunk_id=prev.chunk_id, parent_entry_id=prev.parent_entry_id,
                ordinal=prev.ordinal, content=merged,
                start_offset=prev.start_offset, end_offset=end,
                keywords=_keywords(merged), source_hash=_sha(merged),
            )
            break
        chunks.append(CardWorldbookChunk(
            chunk_id=f"{entry.entry_id}_c{ordinal}", parent_entry_id=entry.entry_id,
            ordinal=ordinal, content=txt, start_offset=offset, end_offset=end,
            keywords=_keywords(txt), source_hash=_sha(txt),
        ))
        offset = end - overlap if end < len(content) else end
        if offset <= chunks[-1].start_offset:
            offset = end
        ordinal += 1
    return chunks


def build_all_chunks(
    entries: list[CardWorldbookEntry], chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP,
) -> tuple[list[CardWorldbookEntry], list[CardWorldbookChunk]]:
    all_chunks: list[CardWorldbookChunk] = []
    updated: list[CardWorldbookEntry] = []
    for entry in entries:
        chs = build_chunks_for_entry(entry, chunk_size, overlap)
        if chs:
            all_chunks.extend(chs)
            updated.append(CardWorldbookEntry(
                schema_id=entry.schema_id, schema_version=entry.schema_version,
                entry_id=entry.entry_id, source_uid=entry.source_uid,
                title=entry.title, content=entry.content,
                keys=list(entry.keys), secondary_keys=list(entry.secondary_keys),
                priority=entry.priority, enabled=entry.enabled,
                constant=entry.constant, selective=entry.selective,
                activation_raw=dict(entry.activation_raw),
                source_order=entry.source_order, source_path=entry.source_path,
                metadata=dict(entry.metadata), quarantine_refs=list(entry.quarantine_refs),
                has_chunks=True,
            ))
        else:
            updated.append(entry)
    return updated, all_chunks
