from __future__ import annotations

from ..scanners.file_tree import build_tree
from ..storage import load_project


def run(project_id: str) -> dict[str, object]:
    project = load_project(project_id)
    if not project.files:
        return {"project_id": project_id, "tree": []}
    paths = list(project.files.keys())
    return {"project_id": project_id, "tree": build_tree(paths), "file_count": len(paths)}
