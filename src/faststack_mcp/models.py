from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class Symbol(BaseModel):
    id: str
    name: str
    qualified_name: str
    kind: str
    language: str
    file_path: str
    line_start: int
    line_end: int
    byte_start: int
    byte_end: int
    signature: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FileRecord(BaseModel):
    path: str
    language: str
    size: int
    hashed: str
    symbols: list[str] = Field(default_factory=list)
    line_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    indexed_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class ProjectStats(BaseModel):
    files_indexed: int = 0
    symbols_indexed: int = 0
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)


class ProjectIndex(BaseModel):
    project_id: str
    project_path: str
    indexed_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    fingerprint: str = ""
    files: dict[str, FileRecord] = Field(default_factory=dict)
    symbols: dict[str, Symbol] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    stats: ProjectStats = Field(default_factory=ProjectStats)
