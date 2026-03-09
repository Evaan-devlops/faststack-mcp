from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_hex(value: str | bytes) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def project_id_for_path(path: Path) -> str:
    return sha256_hex(path.resolve().as_posix())[:16]


def file_hash(data: bytes) -> str:
    return sha256_hex(data)
