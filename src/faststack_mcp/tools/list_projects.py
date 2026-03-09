from __future__ import annotations

from ..storage import list_projects


def run() -> dict[str, object]:
    projects = [
        {
            "project_id": p.project_id,
            "project_path": p.project_path,
            "files_indexed": p.stats.files_indexed,
            "symbols_indexed": p.stats.symbols_indexed,
            "languages": p.stats.languages,
            "frameworks": p.stats.frameworks,
            "indexed_at": p.indexed_at,
        }
        for p in list_projects()
    ]
    return {"projects": projects, "count": len(projects)}
