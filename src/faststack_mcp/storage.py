"""Storage facade — routes to the configured backend.

Backend selection via FASTSTACK_STORAGE env var:
  sqlite   (default) — single ~/$HOME/.faststack-mcp/faststack.db, FTS5 + reference graph
  postgres           — requires DATABASE_URL, tsvector FTS + reference graph
  json               — original flat-JSON files, no FTS

All module-level functions keep the same signatures as before so existing
tool code does not need changes.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from .config import DEFAULT_CACHE_ROOT, INDEX_FILE_NAME, PROJECTS_DIR_NAME

if TYPE_CHECKING:
    from .models import ProjectIndex, Symbol


class StorageError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Backend factory
# ---------------------------------------------------------------------------

_BACKEND_CACHE: object | None = None


def _backend():
    global _BACKEND_CACHE
    if _BACKEND_CACHE is None:
        kind = os.environ.get("FASTSTACK_STORAGE", "sqlite").lower()
        if kind == "postgres":
            from .storage_pg import PostgresStorage
            _BACKEND_CACHE = PostgresStorage()
        elif kind == "json":
            from .storage_json import JsonStorage
            _BACKEND_CACHE = JsonStorage()
        else:  # default: sqlite
            from .storage_sqlite import SqliteStorage
            _BACKEND_CACHE = SqliteStorage()
    return _BACKEND_CACHE


def reset_backend() -> None:
    """Force re-creation of backend on next call (useful in tests)."""
    global _BACKEND_CACHE
    _BACKEND_CACHE = None


# ---------------------------------------------------------------------------
# Path helpers (used by index_folder and get_symbol — keep for compat)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Public API — delegate to active backend
# ---------------------------------------------------------------------------

def load_project(project_id: str) -> "ProjectIndex":
    return _backend().load_project(project_id)


def save_project(index: "ProjectIndex") -> None:
    _backend().save_project(index)


def list_projects() -> "list[ProjectIndex]":
    return _backend().list_projects()


def remove_project(project_id: str) -> bool:
    return _backend().remove_project(project_id)


def project_exists(project_id: str) -> bool:
    return _backend().project_exists(project_id)


# ---------------------------------------------------------------------------
# Enhanced operations (optional — None when backend does not support)
# ---------------------------------------------------------------------------

def search_symbols_fts(
    project_id: str,
    query: str,
    kind: str | None = None,
    language: str | None = None,
    limit: int = 10,
) -> "list[Symbol] | None":
    """FTS-powered search. Returns None to signal fallback to linear scan."""
    b = _backend()
    if not hasattr(b, "search_symbols_fts"):
        return None
    try:
        return b.search_symbols_fts(project_id, query, kind=kind, language=language, limit=limit)
    except Exception:
        return None


def get_references(project_id: str, symbol_name: str) -> "list[dict] | None":
    """Reference graph query. Returns None to signal fallback to text scan."""
    b = _backend()
    if not hasattr(b, "get_references"):
        return None
    try:
        return b.get_references(project_id, symbol_name)
    except Exception:
        return None
