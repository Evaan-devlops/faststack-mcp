from __future__ import annotations

import fnmatch
from pathlib import Path

from .config import (
    BINARY_CHUNK_SIZE,
    SKIP_DIRS,
    SENSITIVE_PATTERNS,
)


class SecurityError(ValueError):
    """Raised when a path or input violates read-only/local-first safety rules."""


def is_excluded_dir(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def is_sensitive_file(path: Path) -> bool:
    name = path.name.lower()
    return any(fnmatch.fnmatch(name, pattern.lower()) for pattern in SENSITIVE_PATTERNS)


def is_binary_file(path: Path) -> bool:
    if path.stat().st_size == 0:
        return False
    with path.open("rb") as handle:
        sample = handle.read(BINARY_CHUNK_SIZE)
    if b"\x00" in sample:
        return True
    text_like = all(
        (32 <= b < 127) or b in {9, 10, 13, 0}
        for b in sample
    )
    return not text_like


def read_text_safe(path: Path, max_bytes: int) -> str:
    with path.open("rb") as handle:
        sample = handle.read(max_bytes + 1)
    if len(sample) > max_bytes:
        raise SecurityError(f"File too large to read safely: {path}")
    return sample.decode("utf-8", errors="ignore")
