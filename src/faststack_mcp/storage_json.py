"""JSON-backed storage backend (original implementation as a class)."""
from __future__ import annotations

import shutil
from pathlib import Path

import orjson

from .config import DEFAULT_CACHE_ROOT, INDEX_FILE_NAME, PROJECTS_DIR_NAME
from .models import ProjectIndex, ProjectStats


class JsonStorage:
    def cache_root(self) -> Path:
        root = DEFAULT_CACHE_ROOT
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _project_dir(self, project_id: str) -> Path:
        return self.cache_root() / PROJECTS_DIR_NAME / project_id

    def _index_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / INDEX_FILE_NAME

    def project_exists(self, project_id: str) -> bool:
        return self._index_path(project_id).exists()

    def load_project(self, project_id: str) -> ProjectIndex:
        path = self._index_path(project_id)
        if not path.exists():
            raise RuntimeError(f"Project not found: {project_id}")
        return ProjectIndex.model_validate(orjson.loads(path.read_bytes()))

    def save_project(self, index: ProjectIndex) -> None:
        path = self._index_path(index.project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = orjson.dumps(index.model_dump(), option=orjson.OPT_INDENT_2)
        temp = path.with_suffix(".tmp")
        temp.write_bytes(data)
        temp.replace(path)

    def list_projects(self) -> list[ProjectIndex]:
        projects_dir = self.cache_root() / PROJECTS_DIR_NAME
        result: list[ProjectIndex] = []
        if not projects_dir.exists():
            return result
        for entry in projects_dir.iterdir():
            if not entry.is_dir():
                continue
            idx = entry / INDEX_FILE_NAME
            if not idx.exists():
                continue
            try:
                data = orjson.loads(idx.read_bytes())
                stats_data = data.get("stats", {})
                proj = ProjectIndex.model_construct(
                    project_id=data["project_id"],
                    project_path=data["project_path"],
                    indexed_at=data.get("indexed_at", ""),
                    fingerprint=data.get("fingerprint", ""),
                    files={},
                    symbols={},
                    errors=[],
                    references_graph={},
                    stats=ProjectStats(
                        files_indexed=stats_data.get("files_indexed", 0),
                        symbols_indexed=stats_data.get("symbols_indexed", 0),
                        languages=stats_data.get("languages", []),
                        frameworks=stats_data.get("frameworks", []),
                    ),
                )
                result.append(proj)
            except Exception:
                continue
        return result

    def remove_project(self, project_id: str) -> bool:
        path = self._project_dir(project_id)
        if not path.exists():
            return False
        shutil.rmtree(path)
        return True
