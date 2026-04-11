from __future__ import annotations

from pathlib import Path

from ..config import DEFAULT_TEXT_CONTEXT_LINES, DEFAULT_TEXT_SEARCH_LIMIT
from ..security import read_text_safe
from ..storage import load_project
from ..utils.pathing import is_within_root


def _score_match(terms: list[str], phrase: str, line_lower: str, context_lower: str) -> float:
    score = 2.0 if phrase in context_lower else 0.0
    for term in terms:
        score += context_lower.count(term) * 0.5
        if term in line_lower:
            score += 1.0
    return score


def run(project_id: str, query: str, limit: int = DEFAULT_TEXT_SEARCH_LIMIT) -> dict[str, object]:
    if not query:
        return {"project_id": project_id, "query": query, "matches": []}
    project = load_project(project_id)
    terms = [t for t in query.lower().split() if t]
    phrase = query.lower()
    candidates: list[dict[str, object]] = []

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
            line_lower = line.lower()
            if not all(t in line_lower or t in source[max(0, source.find(line) - 200):source.find(line) + 200].lower() for t in terms):
                if not any(t in line_lower for t in terms):
                    continue
            start = max(0, idx - 1 - DEFAULT_TEXT_CONTEXT_LINES)
            end = min(len(lines), idx + DEFAULT_TEXT_CONTEXT_LINES)
            context = "".join(lines[start:end]).strip()
            context_lower = context.lower()
            if not all(t in context_lower for t in terms):
                continue
            score = _score_match(terms, phrase, line_lower, context_lower)
            candidates.append(
                {
                    "file_path": file_record.path,
                    "line": idx,
                    "line_text": line.rstrip(),
                    "context": context,
                    "score": score,
                }
            )

    candidates.sort(key=lambda m: m["score"], reverse=True)
    matches = [{k: v for k, v in m.items() if k != "score"} for m in candidates[:limit]]
    return {"project_id": project_id, "query": query, "matches": matches, "count": len(matches)}
