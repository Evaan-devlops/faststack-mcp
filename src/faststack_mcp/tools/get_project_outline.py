from __future__ import annotations

from collections import defaultdict

from ..storage import load_project

# Cache keyed by project_id -> (fingerprint, result)
# Avoids recomputing the outline when the project hasn't changed.
_cache: dict[str, tuple[str, dict]] = {}


def _normalize_path(file_path: str) -> str:
    return file_path.replace("\\", "/").lower()


def _append(bucket: dict[str, list[dict[str, object]]], group: str, item: dict[str, object]) -> None:
    bucket[group].append(item)


def _symbol_entry(symbol) -> dict[str, object]:
    return {
        "name": symbol.name,
        "kind": symbol.kind,
        "file_path": symbol.file_path,
        "line_start": symbol.line_start,
    }


def _file_entry(file_path: str, kind: str, metadata: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "file_path": file_path,
        "kind": kind,
        "line_start": 1,
    }
    # only RAG artifacts carry metadata in the outline — all other entries omit it
    # to keep the outline compact (metadata is available via get_symbol if needed)
    if metadata and kind == "rag_artifact":
        payload["metadata"] = metadata
    return payload


def _frontend_bucket_from_path(file_path: str) -> str | None:
    path = _normalize_path(file_path)
    parts = [part for part in path.split("/") if part]

    if "/src/app/" in path or path.startswith("src/app/") or path == "src/app":
        return "frontend_app"
    if "/src/pages/" in path or "/pages/" in path:
        return "frontend_pages"
    if "/src/components/" in path or "/components/" in path:
        return "frontend_components"
    if "/src/hooks/" in path or "/hooks/" in path:
        return "frontend_hooks"
    if "/src/store/" in path or "/store/" in path:
        return "frontend_store"
    if "/src/types/" in path or "/types/" in path:
        return "frontend_types"
    if "/lib/http/" in path or path.endswith("/lib/http"):
        return "frontend_api"
    if "features" in parts:
        feature_index = parts.index("features")
        if "api" in parts[feature_index + 1 :]:
            return "frontend_api"
    if "/api/" in path:
        return "frontend_api"
    return None


def _symbol_bucket(kind: str) -> str | None:
    if kind in {"route", "frontend_app", "app_shell"}:
        return "frontend_app"
    if kind in {"frontend_page", "route_module", "page_module"}:
        return "frontend_pages"
    if kind in {"component", "frontend_component"}:
        return "frontend_components"
    if kind in {"frontend_hook", "hook"}:
        return "frontend_hooks"
    if kind == "store":
        return "frontend_store"
    if kind in {"api", "api_client", "frontend_api"}:
        return "frontend_api"
    if kind in {"utils", "utility", "frontend_utils"}:
        return "frontend_utils"
    if kind in {"type", "interface", "frontend_type", "types"}:
        return "frontend_types"
    return None


_ALL_SECTIONS = {
    "backend_routes",
    "backend_models_services_repos",
    "frontend_app",
    "frontend_pages",
    "frontend_components",
    "frontend_hooks",
    "frontend_store",
    "frontend_api",
    "frontend_utils",
    "frontend_types",
    "database_migrations",
    "config_files",
    "rag_artifacts",
    "env_config_templates",
}


def run(project_id: str, sections: list[str] | None = None) -> dict[str, object]:
    """Build (and cache) the full groups, then slice to only what was requested.

    sections=None  → summary only: counts + languages + frameworks (~17 tokens).
    sections=[...]  → counts + full symbol data for the named sections only.
    """
    project = load_project(project_id)

    # Return from cache when fingerprint matches
    cached = _cache.get(project_id)
    if not (cached and cached[0] == project.fingerprint):
        # --- build full groups ---
        _build_and_cache(project_id, project)

    cached = _cache[project_id]
    counts: dict[str, int] = cached[1]["counts"]
    groups: dict[str, list] = cached[1]["groups"]
    base = {
        "project_id": project_id,
        "project_path": project.project_path,
        "languages": project.stats.languages,
        "frameworks": project.stats.frameworks,
        "counts": counts,
    }

    if sections is None:
        # Cheap path: orientation only — no symbol data returned
        return base

    # Validate requested sections
    valid = [s for s in sections if s in _ALL_SECTIONS]
    outline = {s: groups.get(s, []) for s in valid}
    return {**base, "outline": outline}


def _build_and_cache(project_id: str, project) -> None:
    groups: dict[str, list[dict[str, object]]] = {
        "backend_routes": [],
        "backend_models_services_repos": [],
        "frontend_app": [],
        "frontend_pages": [],
        "frontend_components": [],
        "frontend_hooks": [],
        "frontend_store": [],
        "frontend_api": [],
        "frontend_utils": [],
        "frontend_types": [],
        "database_migrations": [],
        "config_files": [],
        "rag_artifacts": [],
        "env_config_templates": [],
    }

    file_concrete_buckets: dict[str, set[str]] = defaultdict(set)
    for file_record in project.files.values():
        metadata = file_record.metadata or {}
        if metadata.get("artifact_type") == "rag" or file_record.language == "rag_artifact":
            _append(groups, "rag_artifacts", _file_entry(file_record.path, "rag_artifact", metadata))
            continue
        if metadata.get("env_template") or metadata.get("env_file") or file_record.path.endswith(".env.example"):
            _append(groups, "env_config_templates", _file_entry(file_record.path, "env_template", metadata))
            continue
        if metadata.get("kind") in {"config"}:
            _append(groups, "config_files", _file_entry(file_record.path, "config_file", metadata))
            continue

    for symbol in project.symbols.values():
        if symbol.metadata.get("synthetic"):
            continue
        kind = symbol.kind
        bucket = _symbol_bucket(kind)
        metadata = symbol.metadata or {}

        if kind == "route":
            _append(groups, "backend_routes", _symbol_entry(symbol))
        elif kind in {"pydantic_model", "model", "service", "repository", "class", "method"}:
            _append(groups, "backend_models_services_repos", _symbol_entry(symbol))

        elif bucket in {
            "frontend_app",
            "frontend_pages",
            "frontend_components",
            "frontend_hooks",
            "frontend_store",
            "frontend_api",
            "frontend_utils",
            "frontend_types",
        }:
            _append(groups, bucket, _symbol_entry(symbol))
            file_concrete_buckets[symbol.file_path].add(bucket)

        elif kind in {"table", "alter_table", "index", "view", "migration", "insert"}:
            _append(groups, "database_migrations", _symbol_entry(symbol))
        elif kind in {
            "tailwind_config",
            "package_config",
            "package_dependency",
            "package_script",
            "pyproject_config",
            "vite_config",
            "tsconfig",
            "eslint_config",
            "json",
            "json_key",
            "json_config",
            "jsonl_chunk",
            "config_root",
            "toml_config",
            "ini_config",
            "yaml_config",
            "env_config",
            "manifest_config",
            "pyproject_dependency",
            "config_file",
            "config_json",
            "config_key",
            "jsonl_chunks",
        }:
            _append(groups, "config_files", _symbol_entry(symbol))
        elif kind in {"env_variable", "env_config"}:
            _append(groups, "env_config_templates", _symbol_entry(symbol))

    for file_record in project.files.values():
        bucket = _frontend_bucket_from_path(file_record.path)
        if not bucket:
            continue
        already = file_concrete_buckets.get(file_record.path, set())
        if bucket in already:
            continue
        metadata = file_record.metadata or {}
        if metadata.get("artifact_type") == "rag" or file_record.language == "rag_artifact":
            continue
        if metadata.get("env_template") or metadata.get("env_file") or file_record.path.endswith(".env.example"):
            continue
        if metadata.get("kind") in {"config"}:
            continue

        _append(groups, bucket, _file_entry(file_record.path, "frontend_file", metadata))

    counts = {section: len(items) for section, items in groups.items() if items}
    compact_groups = {k: v for k, v in groups.items() if v}
    _cache[project_id] = (project.fingerprint, {"counts": counts, "groups": compact_groups})
