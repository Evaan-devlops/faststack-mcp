from __future__ import annotations

from ..storage import remove_project


def run(project_id: str) -> dict[str, object]:
    removed = remove_project(project_id)
    return {"project_id": project_id, "removed": removed}
