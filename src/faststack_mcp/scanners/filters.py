from __future__ import annotations

import fnmatch
from pathlib import Path

from ..config import (
    BINARY_CHUNK_SIZE,
    ENV_TEMPLATE_FILES,
    RAG_ARTIFACT_FILES,
    SKIP_DIRS,
    SUPPORTED_EXACT_FILES,
    SENSITIVE_PATTERNS,
    SUPPORTED_EXTENSIONS,
)
from ..security import SecurityError


def is_supported_path(path: Path) -> bool:
    lower_name = path.name.lower()
    if lower_name in SUPPORTED_EXACT_FILES:
        return True
    if lower_name == ".env" or lower_name.startswith(".env."):
        return True
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def is_excluded_dir(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def is_sensitive_file(path: Path) -> bool:
    name = path.name.lower()
    if name in ENV_TEMPLATE_FILES:
        return False
    return any(fnmatch.fnmatch(name, pattern.lower()) for pattern in SENSITIVE_PATTERNS)


def is_env_file(path: Path) -> bool:
    name = path.name.lower()
    return name == ".env" or name.startswith(".env.")


def is_explicit_config(path: Path) -> bool:
    return path.name.lower() in SUPPORTED_EXACT_FILES


def is_rag_artifact(path: Path) -> bool:
    name = path.name.lower()
    if name in RAG_ARTIFACT_FILES or name.endswith(".faiss"):
        return True
    if "rag_artifacts" in {part.lower() for part in path.parts} and name in {"chunks.jsonl", "manifest.json"}:
        return True
    return False


def is_binary_file(path: Path) -> bool:
    if path.stat().st_size == 0:
        return False
    with path.open("rb") as handle:
        sample = handle.read(BINARY_CHUNK_SIZE)
    if b"\x00" in sample:
        return True
    try:
        sample.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def read_text_safe(path: Path, max_bytes: int) -> str:
    with path.open("rb") as handle:
        sample = handle.read(max_bytes + 1)
    if len(sample) > max_bytes:
        raise SecurityError(f"File too large to read safely: {path}")
    return sample.decode("utf-8", errors="ignore")
