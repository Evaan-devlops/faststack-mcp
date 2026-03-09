from __future__ import annotations

import json
import shutil
from pathlib import Path

import orjson

from .config import DEFAULT_CACHE_ROOT, INDEX_FILE_NAME, PROJECTS_DIR_NAME
from .models import ProjectIndex


class StorageError(RuntimeError):
    pass


def cache_root() -> Path:
    root = DEFAULT_CACHE_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def project_dir(project_id: str) -> Path:
    return cache_root() / PROJECTS_DIR_NAME / project_id


def index_path(project_id: str) -> Path:
    return project_dir(project_id) / INDEX_FILE_NAME


def project_index_path(project_id: str) -> Path:
    return index_path(project_id)


def load_project(project_id: str) -> ProjectIndex:
    path = project_index_path(project_id)
    if not path.exists():
        raise StorageError(f"Project not found: {project_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ProjectIndex.model_validate(payload)


def save_project(index: ProjectIndex) -> None:
    path = project_index_path(index.project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = orjson.dumps(index.model_dump(), option=orjson.OPT_INDENT_2)
    temp = path.with_suffix(".tmp")
    temp.write_bytes(data)
    temp.replace(path)


def list_projects() -> list[ProjectIndex]:
    projects_dir = cache_root() / PROJECTS_DIR_NAME
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
            result.append(load_project(entry.name))
        except Exception:
            continue
    return result


def remove_project(project_id: str) -> bool:
    path = project_dir(project_id)
    if not path.exists():
        return False
    shutil.rmtree(path)
    return True


def project_exists(project_id: str) -> bool:
    return project_index_path(project_id).exists()
