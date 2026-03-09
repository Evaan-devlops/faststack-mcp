from __future__ import annotations

import re
from pathlib import Path

from ..models import Symbol
from ..utils.offsets import build_line_offsets, line_span_to_bytes
from . import make_symbol_id


PATTERNS = [
    ("table", re.compile(r"(?is)\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w.\"`'\[]+)")),
    ("alter_table", re.compile(r"(?is)\bALTER\s+TABLE\s+([\w.\"`'\[]+)")),
    ("index", re.compile(r"(?is)\bCREATE\s+INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w.\"`'\[]+)")),
    ("view", re.compile(r"(?is)\bCREATE\s+VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w.\"`'\[]+)")),
    ("insert", re.compile(r"(?is)\bINSERT\s+INTO\s+([\w.\"`'\[]+)")),
]


def _object_name(raw: str) -> str:
    return raw.strip().strip('"`[]').strip()


def parse_file(file_path: Path, source: str) -> list[Symbol]:
    offsets = build_line_offsets(source)
    symbols: list[Symbol] = []
    for kind, pattern in PATTERNS:
        for match in pattern.finditer(source):
            name = _object_name(match.group(1))
            if not name:
                continue
            statement_start = match.start()
            semicolon = source.find(";", match.end())
            if semicolon < 0:
                semicolon = len(source)
            line_start = source[:statement_start].count("\n") + 1
            line_end = source[: semicolon + 1].count("\n") + 1
            signature = " ".join(source[match.start() : semicolon + 1].splitlines()[0:1])
            byte_start, byte_end = line_span_to_bytes(
                offsets,
                start_line=line_start,
                end_line=line_end,
                end_col=0,
            )
            symbol = Symbol(
                id=make_symbol_id(file_path.as_posix(), name, kind),
                name=name,
                qualified_name=name,
                kind=kind,
                language="sql",
                file_path=file_path.as_posix(),
                line_start=line_start,
                line_end=line_end,
                byte_start=byte_start,
                byte_end=byte_end,
                signature=signature.strip(),
                metadata={"source": file_path.name},
            )
            symbols.append(symbol)
    return symbols
