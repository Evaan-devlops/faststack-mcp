from __future__ import annotations

from pathlib import Path


def to_posix(path: Path) -> str:
    return path.as_posix()


def is_within_root(root: Path, candidate: Path) -> bool:
    root_resolved = root.resolve(strict=False)
    candidate_resolved = candidate.resolve(strict=False)
    try:
        candidate_resolved.relative_to(root_resolved)
        return True
    except ValueError:
        return False


def normalize_path(root: Path, rel_or_abs: str | Path) -> Path:
    candidate = Path(rel_or_abs)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve(strict=False)


def safe_child_path(root: Path, rel_path: str) -> Path:
    candidate = root / rel_path
    candidate = candidate.resolve(strict=False)
    if not is_within_root(root, candidate):
        raise ValueError(f"Access denied outside root: {rel_path}")
    return candidate
