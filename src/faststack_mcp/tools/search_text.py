from __future__ import annotations

from pathlib import Path

from ..config import DEFAULT_TEXT_CONTEXT_LINES, DEFAULT_TEXT_SEARCH_LIMIT
from ..security import read_text_safe
from ..storage import load_project
from ..utils.pathing import is_within_root


def run(project_id: str, query: str, limit: int = DEFAULT_TEXT_SEARCH_LIMIT) -> dict[str, object]:
    if not query:
        return {"project_id": project_id, "query": query, "matches": []}
    project = load_project(project_id)
    q = query.lower()
    matches: list[dict[str, object]] = []
    for file_record in project.files.values():
        metadata = file_record.metadata or {}
        if metadata.get("artifact_type") == "rag" or file_record.language == "rag_artifact":
            continue
        file_name = Path(file_record.path).name.lower()
        if metadata.get("env_template") or file_name.startswith(".env"):
            continue
        path = Path(project.project_path) / file_record.path
        if not is_within_root(Path(project.project_path), path):
            continue
        if not path.exists():
            continue
        try:
            source = read_text_safe(path, 10 * 1024 * 1024)
        except Exception:
            continue
        lines = source.splitlines(keepends=True)
        for idx, line in enumerate(lines, start=1):
            if q in line.lower():
                start = max(0, idx - 1 - DEFAULT_TEXT_CONTEXT_LINES)
                end = min(len(lines), idx + DEFAULT_TEXT_CONTEXT_LINES)
                context = "".join(lines[start:end]).strip()
                matches.append(
                    {
                        "file_path": file_record.path,
                        "line": idx,
                        "line_text": line.rstrip(),
                        "context": context,
                    }
                )
                if len(matches) >= limit:
                    return {
                        "project_id": project_id,
                        "query": query,
                        "matches": matches,
                        "count": len(matches),
                    }
    return {"project_id": project_id, "query": query, "matches": matches, "count": len(matches)}
