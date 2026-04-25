"""get_file_context: read lines around a specific line in a project file."""
from __future__ import annotations

from pathlib import Path

from ..security import SecurityError
from ..storage import load_project
from ..utils.pathing import is_within_root


def run(
    project_id: str,
    file_path: str,
    around_line: int,
    radius: int = 40,
) -> dict:
    if around_line < 1:
        raise ValueError(f"around_line must be >= 1, got {around_line}")
    if radius < 0:
        raise ValueError(f"radius must be >= 0, got {radius}")

    project = load_project(project_id)
    root = Path(project.project_path)
    full = (root / file_path).resolve()

    if not is_within_root(root, full):
        raise SecurityError(f"Path escapes project root: {file_path}")
    if not full.is_file():
        raise FileNotFoundError(f"File not found in project: {file_path}")

    content = full.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()
    total = len(lines)

    start = max(0, around_line - 1 - radius)
    end = min(total, around_line - 1 + radius + 1)

    snippet_lines: list[str] = []
    for i in range(start, end):
        marker = ">>>" if (i + 1) == around_line else "   "
        snippet_lines.append(f"{i + 1:5d} {marker} {lines[i]}")

    return {
        "file_path": file_path,
        "around_line": around_line,
        "radius": radius,
        "total_lines": total,
        "start_line": start + 1,
        "end_line": end,
        "content": "\n".join(snippet_lines),
    }
