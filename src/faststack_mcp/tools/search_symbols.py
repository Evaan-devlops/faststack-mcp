from __future__ import annotations

from ..config import DEFAULT_SEARCH_LIMIT
from ..storage import load_project, search_symbols_fts

# Kinds where synthetic symbols (auto-generated props, model fields, etc.) are useful by default
_SYNTHETIC_VISIBLE_KINDS = {
    "pydantic_model", "model", "type", "interface",
    "config_key", "config_file", "tsconfig",
    "toml_config", "yaml_config", "ini_config",
    "json_key", "json_root", "json_config",
}


def _rank(
    name: str,
    ql: str,
    symbol_kind: str | None,
    symbol_language: str | None,
    kind: str | None,
    language: str | None,
) -> int:
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
    include_synthetic: bool | None = None,
    limit: int = DEFAULT_SEARCH_LIMIT,
) -> dict[str, object]:
    if not query:
        return {"project_id": project_id, "query": query, "symbols": [], "count": 0}

    # Context-aware synthetic default:
    # show synthetic symbols when searching model/config/type kinds
    if include_synthetic is None:
        include_synthetic = kind in _SYNTHETIC_VISIBLE_KINDS if kind else False

    # Try FTS-backed search (SQLite FTS5 or PostgreSQL tsvector)
    fts_results = search_symbols_fts(project_id, query, kind=kind, language=language, limit=limit)
    if fts_results is not None:
        payload = []
        for sym in fts_results:
            if not include_synthetic and sym.metadata.get("synthetic"):
                continue
            item = sym.model_dump()
            ql = query.strip().lower()
            nl = sym.name.lower()
            if nl == ql:
                item["score"] = 200
            elif nl.startswith(ql):
                item["score"] = 150
            elif ql in nl:
                item["score"] = 100
            else:
                item["score"] = 20
            payload.append(item)
        payload.sort(key=lambda x: x["score"], reverse=True)
        return {"project_id": project_id, "query": query, "symbols": payload[:limit], "count": len(payload[:limit])}

    # Fallback: linear scan (JSON backend or FTS failure)
    project = load_project(project_id)
    ql = query.strip().lower()
    results: list[tuple[int, dict[str, object]]] = []
    for symbol in project.symbols.values():
        if not include_synthetic and symbol.metadata.get("synthetic"):
            continue
        score = _rank(
            symbol.name,
            ql,
            symbol.kind,
            symbol.language,
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
