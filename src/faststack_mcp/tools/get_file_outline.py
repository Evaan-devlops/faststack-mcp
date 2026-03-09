from __future__ import annotations

from ..models import ProjectIndex
from ..storage import load_project


def run(project_id: str, file_path: str) -> dict[str, object]:
    project = load_project(project_id)
    if file_path not in project.files:
        raise FileNotFoundError(f"file not indexed: {file_path}")
    file_record = project.files[file_path]
    symbols = [
        project.symbols[sym_id].model_dump()
        for sym_id in file_record.symbols
        if sym_id in project.symbols
    ]
    symbols.sort(key=lambda item: (item["line_start"], item["kind"]))
    return {
        "project_id": project_id,
        "file_path": file_path,
        "symbols": symbols,
        "symbol_count": len(symbols),
    }
