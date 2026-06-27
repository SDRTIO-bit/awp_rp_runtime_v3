"""CardSourceLoader — load raw card source from JSON or PNG files."""

from __future__ import annotations

import base64
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from ..contracts.card_source_snapshot import CardSourceSnapshot

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PREFERRED_KEYS = ("chara", "ccv3", "card", "character")


class CardSourceLoadError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


def _try_parse_json(raw: bytes) -> dict[str, Any] | None:
    try:
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _try_parse_base64_json(raw: bytes) -> dict[str, Any] | None:
    try:
        decoded = base64.b64decode(raw.decode("utf-8"))
        data = json.loads(decoded)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _is_valid_card(data: dict[str, Any]) -> bool:
    return "spec" in data or "data" in data


def _extract_png_text_chunks(path: Path) -> list[tuple[str, bytes]]:
    chunks: list[tuple[str, bytes]] = []
    with open(path, "rb") as f:
        sig = f.read(8)
        if sig != _PNG_SIGNATURE:
            raise CardSourceLoadError("invalid_png", "Not a valid PNG file")
        while True:
            len_bytes = f.read(4)
            if len(len_bytes) < 4:
                break
            length = struct.unpack(">I", len_bytes)[0]
            ctype = f.read(4)
            if len(ctype) < 4:
                break
            data = f.read(length)
            if len(data) < length:
                break
            f.read(4)  # CRC
            if ctype == b"IEND":
                break
            if ctype == b"tEXt":
                try:
                    idx = data.index(b"\0")
                    kw = data[:idx].decode("latin-1")
                    chunks.append((kw, data[idx + 1:]))
                except Exception:
                    pass
            elif ctype == b"zTXt":
                try:
                    import zlib
                    idx = data.index(b"\0")
                    kw = data[:idx].decode("latin-1")
                    chunks.append((kw, zlib.decompress(data[idx + 2:])))
                except Exception:
                    pass
            elif ctype == b"iTXt":
                try:
                    parts = data.split(b"\0", 5)
                    if len(parts) >= 6:
                        kw = parts[0].decode("latin-1")
                        flag = parts[1][0] if parts[1] else 0
                        txt = parts[5] if flag == 0 else __import__("zlib").decompress(parts[5])
                        chunks.append((kw, txt))
                except Exception:
                    pass
    return chunks


def load_card_source(
    source_path: str, source_filename: str = "", imported_at: str = "",
) -> tuple[CardSourceSnapshot, dict[str, Any]]:
    path = Path(source_path)
    if not path.exists():
        raise CardSourceLoadError("file_not_found", f"Not found: {source_path}")
    if not source_filename:
        source_filename = path.name
    suffix = path.suffix.lower()

    if suffix == ".json":
        raw = path.read_bytes()
        data = _try_parse_json(raw)
        if data is None:
            raise CardSourceLoadError("invalid_json", "Not valid JSON")
        if not _is_valid_card(data):
            raise CardSourceLoadError("unsupported_payload_shape", "Missing 'spec' or 'data'")
        source_format = "json"
    elif suffix == ".png":
        text_chunks = _extract_png_text_chunks(path)
        if not text_chunks:
            raise CardSourceLoadError("unsupported_png_metadata", "No text chunks found")
        data = None
        raw = b""
        for preferred in _PREFERRED_KEYS:
            for kw, txt in text_chunks:
                if kw.lower() == preferred:
                    d = _try_parse_json(txt) or _try_parse_base64_json(txt)
                    if d and _is_valid_card(d):
                        data, raw = d, txt
                        break
            if data:
                break
        if not data:
            for kw, txt in text_chunks:
                d = _try_parse_json(txt) or _try_parse_base64_json(txt)
                if d and _is_valid_card(d):
                    data, raw = d, txt
                    break
        if not data:
            raise CardSourceLoadError("unsupported_png_metadata", "No valid card data in PNG")
        source_format = "png"
    else:
        raise CardSourceLoadError("unsupported_format", f"Unsupported: {suffix}")

    h = hashlib.sha256(raw).hexdigest()
    snapshot = CardSourceSnapshot(
        source_id=f"src_{h[:16]}", source_hash=h,
        source_filename=source_filename, source_format=source_format,
        source_size_bytes=len(raw), imported_at=imported_at,
        spec=data.get("spec", "") if isinstance(data.get("spec"), str) else str(data.get("spec", "")),
        raw_payload_ref=f"src_{h[:16]}",
    )
    return snapshot, data
