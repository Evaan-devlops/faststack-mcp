from __future__ import annotations

import json
import re
from pathlib import Path

from ..models import Symbol
from ..utils.offsets import build_line_offsets, line_span_to_bytes
from . import make_symbol_id

TAILWIND_KEYS = ("theme", "extend", "plugins", "content", "safelist")
CLASS_RE = re.compile(r'className\s*=\s*(["\'])(.*?)\1')


def _add_config_keys(file_path: Path, source: str, symbols: list[Symbol]) -> None:
    lower = source.lower()
    for key in TAILWIND_KEYS:
        if key in lower:
            symbols.append(
                Symbol(
                    id=make_symbol_id(file_path.as_posix(), f"tailwind_{key}", "tailwind_config"),
                    name=f"tailwind_{key}",
                    qualified_name=f"tailwind_{key}",
                    kind="tailwind_config",
                    language="config",
                    file_path=file_path.as_posix(),
                    line_start=1,
                    line_end=1,
                    byte_start=0,
                    byte_end=0,
                    signature=f"tailwind config key: {key}",
                    metadata={"file": file_path.name, "kind": "tailwind_key"},
                )
            )


def _parse_package_json(path: Path, source: str, symbols: list[Symbol]) -> None:
    try:
        data = json.loads(source)
    except json.JSONDecodeError:
        return
    deps = set()
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        payload = data.get(section)
        if isinstance(payload, dict):
            deps.update(payload.keys())
    if not deps:
        return
    for dep in sorted(deps):
        if dep in {"react", "fastapi", "typescript", "tailwindcss", "sqlalchemy", "psycopg2"}:
            symbols.append(
                Symbol(
                    id=make_symbol_id(path.as_posix(), f"package_dep_{dep}", "package_config"),
                    name=f"package_dep_{dep}",
                    qualified_name=f"package_dep_{dep}",
                    kind="package_config",
                    language="config",
                    file_path=path.as_posix(),
                    line_start=1,
                    line_end=1,
                    byte_start=0,
                    byte_end=0,
                    signature=f"dependency: {dep}",
                    metadata={"dependency": dep},
                )
            )


def _parse_classes(path: Path, source: str, symbols: list[Symbol]) -> None:
    lines = source.splitlines(keepends=True)
    offsets = build_line_offsets(source)
    for idx, line in enumerate(lines, start=1):
        for match in CLASS_RE.finditer(line):
            value = match.group(2)
            classes = [x.strip() for x in value.split() if x.strip()]
            if len(classes) < 3:
                continue
            start = idx
            byte_start, byte_end = line_span_to_bytes(offsets, idx, idx, 0, 0)
            symbols.append(
                Symbol(
                    id=make_symbol_id(
                        path.as_posix(),
                        f"TailwindClassesLine{idx}",
                        "tailwind_class_usage",
                    ),
                    name=f"TailwindClassesLine{idx}",
                    qualified_name=f"TailwindClassesLine{idx}",
                    kind="tailwind_class_usage",
                    language="typescript",
                    file_path=path.as_posix(),
                    line_start=start,
                    line_end=idx,
                    byte_start=byte_start,
                    byte_end=byte_end,
                    signature=" ".join(classes[:8]),
                    metadata={"classes": classes, "count": len(classes)},
                )
            )


def parse_file(file_path: Path, source: str) -> list[Symbol]:
    symbols: list[Symbol] = []
    name = file_path.name.lower()

    if name in {"tailwind.config.js", "tailwind.config.ts"}:
        _add_config_keys(file_path, source, symbols)
        return symbols

    if name == "package.json":
        _parse_package_json(file_path, source, symbols)
        return symbols

    if name == "pyproject.toml":
        if "fastapi" in source.lower() or "pydantic" in source.lower():
            symbols.append(
                Symbol(
                    id=make_symbol_id(file_path.as_posix(), "pyproject_python_backend", "pyproject_config"),
                    name="pyproject_python_backend",
                    qualified_name="pyproject_python_backend",
                    kind="pyproject_config",
                    language="config",
                    file_path=file_path.as_posix(),
                    line_start=1,
                    line_end=1,
                    byte_start=0,
                    byte_end=0,
                    signature="pyproject backend marker",
                    metadata={"kind": "pyproject"},
                )
            )
        return symbols

    if name == "alembic.ini":
        symbols.append(
            Symbol(
                id=make_symbol_id(file_path.as_posix(), "alembic_cfg", "alembic_config"),
                name="alembic_cfg",
                qualified_name="alembic_cfg",
                kind="alembic_config",
                language="config",
                file_path=file_path.as_posix(),
                line_start=1,
                line_end=1,
                byte_start=0,
                byte_end=0,
                signature="alembic config",
                metadata={"kind": "alembic"},
            )
        )
        return symbols

    if file_path.suffix.lower() in {".ts", ".tsx"}:
        _parse_classes(file_path, source, symbols)
    return symbols
