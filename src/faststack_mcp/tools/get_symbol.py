from __future__ import annotations

from pathlib import Path

from ..security import SecurityError, read_text_safe
from ..storage import load_project
from ..utils.pathing import is_within_root

DEFAULT_MAX_SYMBOL_BYTES = 10 * 1024 * 1024


def run(project_id: str, symbol_id: str) -> dict[str, object]:
    project = load_project(project_id)
    symbol = project.symbols.get(symbol_id)
    if symbol is None:
        raise KeyError(f"symbol not found: {symbol_id}")
    root = Path(project.project_path).resolve()
    file_path = (root / symbol.file_path).resolve()
    if not is_within_root(root, file_path):
        raise SecurityError(f"Unsafe symbol file path: {symbol.file_path}")
    data = read_text_safe(file_path, DEFAULT_MAX_SYMBOL_BYTES)
    if symbol.byte_start < 0:
        snippet = ""
    else:
        snippet = data.encode("utf-8")[symbol.byte_start : symbol.byte_end].decode("utf-8", errors="ignore")
    if symbol.language == "env":
        if "=" in snippet:
            key = snippet.split("=", 1)[0].strip()
            snippet = f"{key}=***"
        elif snippet:
            snippet = "***"
    payload = symbol.model_dump()
    payload["snippet"] = snippet
    return payload
