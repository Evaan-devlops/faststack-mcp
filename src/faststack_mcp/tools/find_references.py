"""find_references: show where a symbol is imported or used across the project."""
from __future__ import annotations

import re
from pathlib import Path

from ..storage import load_project
from ..utils.pathing import is_within_root


def run(project_id: str, symbol_name: str, limit: int = 50) -> dict:
    if not symbol_name or not symbol_name.strip():
        return {"symbol_name": symbol_name, "references": [], "total_usages": 0, "files_found": 0}

    project = load_project(project_id)
    name_lower = symbol_name.strip().lower()
    seen: set[str] = set()
    results: list[dict] = []

    # 1. Reference graph built during indexing (import-level granularity)
    for entry in project.references_graph.get(name_lower, []):
        if entry not in seen:
            seen.add(entry)
            parts = entry.rsplit(":", 1)
            results.append({
                "file_path": parts[0],
                "line": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0,
                "context": "",
                "source": "import_graph",
            })

    # 2. Whole-word text search as fallback / supplement
    pattern = re.compile(rf"\b{re.escape(symbol_name.strip())}\b")
    root = Path(project.project_path)

    for rel_path, file_record in project.files.items():
        if len(results) >= limit:
            break
        if file_record.language in {"env", "rag_artifact"}:
            continue
        full = root / rel_path
        if not full.is_file():
            continue
        if not is_within_root(root, full):
            continue
        try:
            content = full.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(content.splitlines(), 1):
            if len(results) >= limit:
                break
            if pattern.search(line):
                key = f"{rel_path}:{lineno}"
                if key not in seen:
                    seen.add(key)
                    results.append({
                        "file_path": rel_path,
                        "line": lineno,
                        "context": line.strip()[:120],
                        "source": "text_search",
                    })

    # Group by file for readability
    by_file: dict[str, list[dict]] = {}
    for r in results:
        by_file.setdefault(r["file_path"], []).append(r)

    summary = [
        {
            "file_path": fp,
            "usages": sorted(refs, key=lambda x: x["line"]),
        }
        for fp, refs in sorted(by_file.items())
    ]

    return {
        "symbol_name": symbol_name,
        "references": summary,
        "total_usages": len(results),
        "files_found": len(summary),
    }
