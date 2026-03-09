from __future__ import annotations

import re
from pathlib import Path

from ..models import Symbol
from . import make_symbol_id

ENV_PATTERN = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
MASKED_VALUE = "***MASKED***"


def _mask_value(value: str) -> str:
    return MASKED_VALUE


def _encode_length(text: str) -> int:
    return len(text.encode("utf-8"))


def _line_offsets(raw_line: str, line_start_byte: int, match: re.Match[str]) -> tuple[int, int]:
    prefix = raw_line[: match.start(2)]
    value = raw_line[match.start(2) : match.end(2)]
    return line_start_byte + _encode_length(prefix), line_start_byte + _encode_length(prefix + value)


def parse_file(file_path: Path, source: str) -> list[Symbol]:
    symbols: list[Symbol] = []
    var_names: list[str] = []
    lines = source.splitlines(keepends=True)
    cursor = 0
    for line_no, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\r\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            cursor += _encode_length(raw_line)
            continue
        match = ENV_PATTERN.match(line)
        if not match:
            cursor += _encode_length(raw_line)
            continue
        name, value = match.group(1), match.group(2)
        if not name:
            cursor += _encode_length(raw_line)
            continue
        var_names.append(name)
        byte_start, byte_end = _line_offsets(line, cursor, match)
        cursor += _encode_length(raw_line)
        symbols.append(
            Symbol(
                id=make_symbol_id(file_path.as_posix(), f"env_{name}", "env_variable"),
                name=name,
                qualified_name=name,
                kind="env_variable",
                language="env",
                file_path=file_path.as_posix(),
                line_start=line_no,
                line_end=line_no,
                byte_start=byte_start,
                byte_end=byte_end,
                signature=f"{name}={_mask_value(value)}",
                metadata={
                    "variable": name,
                    "masked_value": _mask_value(value),
                    "masked": True,
                    "metadata_only": False,
                    "env_only": True,
                    "parser": "env_parser",
                },
            )
        )

    symbols.insert(
        0,
        Symbol(
            id=make_symbol_id(file_path.as_posix(), "env_variable_list", "env_config"),
            name="env_variable_list",
            qualified_name="env_variable_list",
            kind="env_config",
            language="env",
            file_path=file_path.as_posix(),
            line_start=1,
            line_end=1,
            byte_start=0,
            byte_end=0,
            signature="environment variable names",
            metadata={
                "variables": var_names,
                "count": len(var_names),
                "template": file_path.name.lower() == ".env.example",
                "metadata_only": True,
                "env_only": True,
                "masked": True,
                "parser": "env_parser",
            },
        ),
    )
    return symbols
