"""
Cross-reference extractor: builds import-graph data from Python and TypeScript files.
Returns {symbol_name_lower: ["rel_path:lineno", ...]} for all imported names.
Only import declarations are tracked (not call sites) for performance.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_TS_NAMED_IMPORT = re.compile(
    r'^\s*import\s+(?:type\s+)?\{\s*([^}]+)\}\s+from\s+["\'][^"\']+["\']',
    re.MULTILINE,
)
_TS_DEFAULT_IMPORT = re.compile(
    r'^\s*import\s+(?:type\s+)?(\w+)\s+from\s+["\'][^"\']+["\']',
    re.MULTILINE,
)
_TS_SIDE_EFFECT = re.compile(
    r'^\s*import\s+["\'][^"\']+["\']',
    re.MULTILINE,
)


def _extract_python(source: str, rel_path: str) -> dict[str, list[str]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    result: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = (alias.asname or alias.name).split(".")[0].lower()
                result.setdefault(name, []).append(f"{rel_path}:{node.lineno}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = (alias.asname or alias.name.split(".")[0]).lower()
                result.setdefault(name, []).append(f"{rel_path}:{node.lineno}")
    return result


def _extract_ts(source: str, rel_path: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    lines = source.splitlines()
    for lineno, line in enumerate(lines, 1):
        if _TS_SIDE_EFFECT.match(line):
            continue
        m = _TS_NAMED_IMPORT.match(line)
        if m:
            for part in m.group(1).split(","):
                raw = part.strip()
                if not raw:
                    continue
                name = raw.split(" as ")[-1].strip().lower()
                if name:
                    result.setdefault(name, []).append(f"{rel_path}:{lineno}")
            continue
        m = _TS_DEFAULT_IMPORT.match(line)
        if m:
            name = m.group(1).lower()
            result.setdefault(name, []).append(f"{rel_path}:{lineno}")
    return result


def extract_references(file_path: Path, source: str, rel_path: str) -> dict[str, list[str]]:
    ext = file_path.suffix.lower()
    if ext == ".py":
        return _extract_python(source, rel_path)
    if ext in {".ts", ".tsx", ".js", ".jsx"}:
        return _extract_ts(source, rel_path)
    return {}


def merge_references(
    base: dict[str, list[str]],
    incoming: dict[str, list[str]],
) -> dict[str, list[str]]:
    result = {k: list(v) for k, v in base.items()}
    for name, entries in incoming.items():
        existing = result.setdefault(name, [])
        seen = set(existing)
        for e in entries:
            if e not in seen:
                existing.append(e)
                seen.add(e)
    return result
