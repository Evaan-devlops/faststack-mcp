from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from ..config import DEFAULT_MAX_FILE_SIZE_BYTES
from ..models import FileRecord, ProjectIndex, ProjectStats, Symbol
from ..parsers import make_symbol_id
from ..parsers.config_parser import parse_file as parse_config
from ..parsers.env_parser import parse_file as parse_env
from ..parsers.json_parser import parse_file as parse_json
from ..parsers.python_fastapi import parse_file as parse_python
from ..parsers.sql_parser import parse_file as parse_sql
from ..parsers.typescript_react import parse_file as parse_typescript
from ..scanners.filters import (
    is_binary_file,
    is_env_file,
    is_excluded_dir,
    is_explicit_config,
    is_rag_artifact,
    is_sensitive_file,
    is_supported_path,
    read_text_safe,
)
from ..scanners.project_detector import infer_languages_and_frameworks
from ..security import SecurityError
from ..storage import cache_root, load_project, save_project
from ..utils.hashing import file_hash, project_id_for_path

MAX_FILE_SIZE = DEFAULT_MAX_FILE_SIZE_BYTES

_PARSER_NAMES = {
    parse_config: "parse_config",
    parse_env: "parse_env",
    parse_json: "parse_json",
    parse_python: "parse_python",
    parse_sql: "parse_sql",
    parse_typescript: "parse_typescript",
}

_TS_FILE_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}
_JSON_EXTENSIONS = {".json", ".jsonl"}
_CONFIG_FILE_EXTENSIONS = {".toml", ".ini", ".yaml", ".yml"}
_EXPLICIT_CONFIG_JSON_FILES = {
    "package.json",
    "tsconfig.json",
    "tsconfig.app.json",
    "tsconfig.node.json",
    "vite.config.js",
    "vite.config.ts",
    "vite.config.mjs",
    "vite.config.cjs",
    "alembic.ini",
    "eslint.config.js",
    "tailwind.config.js",
    "tailwind.config.ts",
    "pyproject.toml",
}


def _language_for_path(path: Path) -> str:
    name = path.name.lower()
    if is_env_file(path):
        return "env"
    if name == "index.faiss":
        return "rag_artifact"
    if name in {"manifest.json", "chunks.jsonl"}:
        return "json"
    if name in {"vite.config.js", "vite.config.ts", "vite.config.mjs", "vite.config.cjs"}:
        return "config"
    if name in _EXPLICIT_CONFIG_JSON_FILES:
        return "config"
    if path.suffix.lower() == ".py":
        return "python"
    if path.suffix.lower() in _TS_FILE_EXTENSIONS:
        return "typescript" if path.suffix.lower() in {".ts", ".tsx"} else "javascript"
    if path.suffix.lower() == ".sql":
        return "sql"
    if path.suffix.lower() in _JSON_EXTENSIONS:
        return "json"
    if path.suffix.lower() in _CONFIG_FILE_EXTENSIONS:
        return "config"
    return "other"


def _parser_for_path(path: Path, include_env_files: bool):
    lower_name = path.name.lower()
    if is_env_file(path) and (include_env_files or lower_name == ".env.example"):
        return parse_env

    if lower_name in {"manifest.json", "chunks.jsonl"}:
        return parse_json

    if is_explicit_config(path) or lower_name in _EXPLICIT_CONFIG_JSON_FILES:
        return parse_config

    if lower_name.startswith("tsconfig") and lower_name.endswith(".json"):
        return parse_config
    if lower_name.startswith("vite.config"):
        return parse_config

    if path.suffix.lower() in _TS_FILE_EXTENSIONS:
        return parse_typescript
    if path.suffix.lower() == ".py":
        return parse_python
    if path.suffix.lower() == ".sql":
        return parse_sql
    if path.suffix.lower() in _JSON_EXTENSIONS:
        return parse_json
    if path.suffix.lower() in _CONFIG_FILE_EXTENSIONS:
        return parse_config

    return None


def _safe_child(project_root: Path, child: Path) -> None:
    try:
        child.resolve(strict=False).relative_to(project_root.resolve())
    except ValueError as exc:
        raise SecurityError(f"Path escapes project root: {child}") from exc


def _compute_signature(path: Path, include_env_files: bool) -> str:
    records = []
    for child in sorted(path.rglob("*")):
        if not child.is_file():
            continue
        if child.is_symlink():
            continue
        if is_sensitive_file(child):
            if is_env_file(child) and include_env_files:
                pass
            elif is_env_file(child):
                continue
            else:
                continue
        if not is_supported_path(child):
            continue
        try:
            st = child.stat()
            records.append(
                f"{child.relative_to(path).as_posix()}:{st.st_size}:{st.st_mtime_ns}"
            )
        except OSError:
            continue
    return "|".join(records)


def _record_file(
    rel_path: str,
    path: Path,
    language: str,
    file_size: int,
    digest: str,
    symbols: list[str],
    metadata: dict[str, object] | None = None,
    line_count: int = 0,
) -> FileRecord:
    return FileRecord(
        path=rel_path,
        language=language,
        size=file_size,
        hashed=digest,
        symbols=symbols,
        line_count=line_count,
        metadata=metadata or {},
    )


def _update_symbol_ids(parsed_symbols: list[Symbol], rel_path: str) -> tuple[list[str], list[Symbol]]:
    symbol_ids = []
    for idx, symbol in enumerate(parsed_symbols):
        symbol.file_path = rel_path
        if symbol.id.count("#") == 0:
            symbol.id = make_symbol_id(rel_path, symbol.qualified_name, symbol.kind)
        symbol_id = symbol.id
        if symbol_id in symbol_ids:
            symbol_id = f"{symbol_id}::{idx + 1}"
        symbol = symbol.model_copy(update={"id": symbol_id})
        parsed_symbols[idx] = symbol
        symbol_ids.append(symbol_id)
    return symbol_ids, parsed_symbols


def run(folder_path: str, force: bool = False, max_file_size: int | None = None, include_env_files: bool = False) -> dict[str, object]:
    root = Path(folder_path).expanduser().resolve()
    if not root.exists():
        raise SecurityError(f"Folder does not exist: {root}")
    if not root.is_dir():
        raise SecurityError(f"Expected a directory: {root}")

    project_id = project_id_for_path(root)
    max_file_size = max_file_size or MAX_FILE_SIZE
    cache_file = cache_root() / "projects" / project_id / "index.json"

    signature: str | None = None
    if cache_file.exists() and not force:
        try:
            existing = load_project(project_id)
            signature = _compute_signature(root, include_env_files)
            if existing.fingerprint == signature:
                return {
                    "project_id": existing.project_id,
                    "files_indexed": len(existing.files),
                    "symbols_indexed": len(existing.symbols),
                    "languages": existing.stats.languages,
                    "frameworks": existing.stats.frameworks,
                    "cached": True,
                    "path": existing.project_path,
                }
        except Exception:
            pass

    if signature is None:
        signature = _compute_signature(root, include_env_files)

    parser_results: dict[str, Symbol] = {}
    file_records: dict[str, FileRecord] = {}
    errors: list[str] = []

    for path, dir_names, file_names in os.walk(root):
        dir_path = Path(path)
        filtered_dirs = []
        for name in dir_names:
            candidate = dir_path / name
            if candidate.is_symlink():
                continue
            if is_excluded_dir(candidate):
                continue
            filtered_dirs.append(name)
        dir_names[:] = filtered_dirs

        for name in file_names:
            full = dir_path / name
            if full.is_symlink() or not full.is_file():
                continue

            if is_sensitive_file(full):
                if is_env_file(full) and include_env_files:
                    pass
                else:
                    continue

            try:
                _safe_child(root, full)
            except SecurityError:
                continue

            if not is_supported_path(full):
                continue

            rel_path = full.relative_to(root).as_posix()
            file_size = full.stat().st_size
            if file_size > max_file_size:
                continue

            if is_rag_artifact(full):
                rag_metadata = {
                    "artifact_type": "rag",
                    "artifact_file": full.name,
                    "indexed": False,
                    "content_indexed": False,
                    "in_rag_artifacts": "rag_artifacts" in full.parts,
                }
                if full.name == "index.faiss":
                    rag_metadata["rag_artifact_type"] = "faiss_index"
                elif full.name == "manifest.json":
                    rag_metadata["rag_artifact_type"] = "manifest"
                elif full.name == "chunks.jsonl":
                    rag_metadata["rag_artifact_type"] = "chunks_jsonl"
                else:
                    rag_metadata["rag_artifact_type"] = "generic"
                try:
                    digest = file_hash(full.read_bytes())
                except OSError:
                    continue
                file_records[rel_path] = _record_file(
                    rel_path=rel_path,
                    path=full,
                    language="rag_artifact",
                    file_size=file_size,
                    digest=digest,
                    symbols=[],
                    metadata=rag_metadata,
                )
                continue

            if is_binary_file(full):
                continue

            parser = _parser_for_path(full, include_env_files)
            if parser is None:
                continue

            try:
                content = read_text_safe(full, max_file_size)
            except SecurityError as exc:
                errors.append(f"{rel_path}: {exc}")
                continue

            try:
                parsed_symbols = parser(full, content)
            except Exception as exc:
                errors.append(f"{rel_path}: parse error: {exc}")
                continue

            line_count = len(content.splitlines())
            digest = file_hash(content.encode("utf-8"))
            symbol_ids: list[str] = []
            if parsed_symbols:
                symbol_ids, parsed_symbols = _update_symbol_ids(parsed_symbols, rel_path)
                for symbol in parsed_symbols:
                    if symbol.id in parser_results:
                        continue
                    parser_results[symbol.id] = symbol

            metadata: dict[str, object] = {
                "parser": _PARSER_NAMES.get(parser, parser.__name__),
            }
            if full.name.lower() == ".env.example":
                metadata["env_template"] = True
            elif include_env_files and is_env_file(full):
                metadata["env_file"] = True
            if parser is parse_config:
                metadata["kind"] = "config"

            file_records[rel_path] = _record_file(
                rel_path=rel_path,
                path=full,
                language=_language_for_path(full),
                file_size=file_size,
                digest=digest,
                symbols=symbol_ids,
                metadata=metadata,
                line_count=line_count,
            )

    languages, frameworks = infer_languages_and_frameworks(
        file_records,
        [item.model_dump() for item in parser_results.values()],
    )
    stats = ProjectStats(
        files_indexed=len(file_records),
        symbols_indexed=len(parser_results),
        languages=languages,
        frameworks=frameworks,
    )

    index = ProjectIndex(
        project_id=project_id,
        project_path=root.as_posix(),
        indexed_at=datetime.now(UTC).isoformat(),
        fingerprint=signature,
        files=file_records,
        symbols=parser_results,
        errors=errors,
        stats=stats,
    )
    save_project(index)
    return index.model_dump()
