from __future__ import annotations

from ..config import DEFAULT_SEARCH_LIMIT
from ..storage import load_project


def _rank(name: str, ql: str, symbol_kind: str | None, symbol_language: str | None, kind: str | None, language: str | None) -> int:
    name_l = name.lower()
    if kind and symbol_kind != kind:
        return -1
    if language and symbol_language != language:
        return -1
    score = 0
    if name_l == ql:
        score += 200
    elif name_l.startswith(ql):
        score += 150
    elif ql in name_l:
        score += 100
    return score


def run(
    project_id: str,
    query: str,
    kind: str | None = None,
    language: str | None = None,
    include_synthetic: bool = False,
    limit: int = DEFAULT_SEARCH_LIMIT,
) -> dict[str, object]:
    if not query:
        return {"project_id": project_id, "query": query, "symbols": []}
    project = load_project(project_id)
    ql = query.strip().lower()
    results: list[tuple[int, dict[str, object]]] = []
    for symbol in project.symbols.values():
        symbol_kind = symbol.kind
        if not include_synthetic and symbol.metadata.get("synthetic"):
            continue
        symbol_language = symbol.language
        score = _rank(
            symbol.name,
            ql,
            symbol_kind,
            symbol_language,
            kind.lower() if kind else None,
            language.lower() if language else None,
        )
        if score < 0:
            continue
        if ql in symbol.name.lower() or ql in symbol.qualified_name.lower() or (
            symbol.signature and ql in symbol.signature.lower()
        ):
            if score == 0:
                score = 20
            item = symbol.model_dump()
            item["score"] = score
            results.append((score, item))
    results.sort(reverse=True, key=lambda item: item[0])
    payload = [item for _, item in results[:limit]]
    return {"project_id": project_id, "query": query, "symbols": payload, "count": len(payload)}
