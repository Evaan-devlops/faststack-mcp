from __future__ import annotations

import json
from pathlib import Path

from ..models import Symbol
from . import make_symbol_id

KNOWN_MANIFEST_KEYS = {"name", "short_name", "icons", "start_url", "scope", "display"}
KNOWN_RAG_CHUNK_KEYS = {"text", "content", "chunk_id", "doc_id", "source", "metadata", "page", "title"}
RAG_ARTIFACT_TYPES = {
    "manifest.json": "manifest",
    "chunks.jsonl": "rag_chunks",
}
MAX_LIST_KEY_SAMPLE = 25


def _artifact_type(file_path: Path) -> str | None:
    return RAG_ARTIFACT_TYPES.get(file_path.name.lower())


def _symbol_metadata(metadata: dict | None = None) -> dict[str, object]:
    payload = {"parser": "json_parser"}
    if metadata:
        payload.update(metadata)
    return payload


def _key_symbol(file_path: Path, key: str, metadata: dict | None = None) -> Symbol:
    return Symbol(
        id=make_symbol_id(file_path.as_posix(), key, "json_key"),
        name=key,
        qualified_name=key,
        kind="json_key",
        language="json",
        file_path=file_path.as_posix(),
        line_start=1,
        line_end=1,
        byte_start=0,
        byte_end=0,
        signature=f"json key: {key}",
        metadata=_symbol_metadata(metadata),
    )


def _json_root_symbol(file_path: Path, keys: list[str], metadata: dict | None = None) -> Symbol:
    return Symbol(
        id=make_symbol_id(file_path.as_posix(), "json_root", "json"),
        name="json_root",
        qualified_name="json_root",
        kind="json",
        language="json",
        file_path=file_path.as_posix(),
        line_start=1,
        line_end=1,
        byte_start=0,
        byte_end=0,
        signature="top-level json keys",
        metadata=_symbol_metadata(metadata),
    )


def _parse_manifest_metadata(file_path: Path, payload: dict[str, object], symbols: list[Symbol], artifact_type: str | None) -> None:
    symbols.append(
        Symbol(
            id=make_symbol_id(file_path.as_posix(), "manifest_metadata", "manifest_config"),
            name="manifest_metadata",
            qualified_name="manifest_metadata",
            kind="manifest_config",
            language="json",
            file_path=file_path.as_posix(),
            line_start=1,
            line_end=1,
            byte_start=0,
            byte_end=0,
            signature="manifest metadata",
            metadata=_symbol_metadata(
                {
                    "artifact_type": artifact_type,
                    "name": payload.get("name"),
                    "short_name": payload.get("short_name"),
                    "scope": payload.get("scope"),
                    "start_url": payload.get("start_url"),
                    "display": payload.get("display"),
                }
            ),
        )
    )


def _parse_json_object(file_path: Path, payload: dict[str, object]) -> list[Symbol]:
    artifact_type = _artifact_type(file_path)
    keys = [k for k in payload.keys() if isinstance(k, str)]
    root_metadata = {"top_level_keys": keys, "root_type": "object"}
    if artifact_type:
        root_metadata["artifact_type"] = artifact_type

    symbols = [_json_root_symbol(file_path, keys, root_metadata)]

    if file_path.name.lower() == "manifest.json":
        _parse_manifest_metadata(file_path, payload, symbols, artifact_type)

    for key in keys:
        if key in KNOWN_MANIFEST_KEYS:
            kind = "manifest_key"
        elif artifact_type == "manifest":
            kind = "manifest_like"
        else:
            kind = "top_level"
        symbols.append(_key_symbol(file_path, key, {"artifact_type": artifact_type, "type": kind}))

    if "chunks" in payload:
        symbols.append(
            Symbol(
                id=make_symbol_id(file_path.as_posix(), "json_chunks", "json_config"),
                name="json_chunks",
                qualified_name="json_chunks",
                kind="json_config",
                language="json",
                file_path=file_path.as_posix(),
                line_start=1,
                line_end=1,
                byte_start=0,
                byte_end=0,
                signature="json config chunks key",
                metadata=_symbol_metadata({"config_key": "chunks", "artifact_type": artifact_type}),
            )
        )
    return symbols


def _parse_json_array(file_path: Path, payload: list[object]) -> list[Symbol]:
    artifact_type = _artifact_type(file_path)
    symbols: list[Symbol] = []
    item_count = len(payload)
    item_types = sorted({type(item).__name__ for item in payload if item is not None})

    keys: list[str] = []
    for item in payload[:MAX_LIST_KEY_SAMPLE]:
        if isinstance(item, dict):
            for key in item.keys():
                if isinstance(key, str) and key not in keys:
                    keys.append(key)

    root_metadata = {
        "root_type": "array",
        "item_count": item_count,
        "item_types": item_types,
        "array_key_sample": keys,
    }
    if artifact_type:
        root_metadata["artifact_type"] = artifact_type

    symbols.append(
        _json_root_symbol(
            file_path,
            keys,
            root_metadata,
        )
    )

    for key in keys:
        symbols.append(_key_symbol(file_path, key, {"artifact_type": artifact_type, "type": "array_key"}))

    for key in KNOWN_RAG_CHUNK_KEYS:
        if key in keys and artifact_type == "rag_chunks":
            symbols.append(
                _key_symbol(
                    file_path,
                    f"rag_chunk_hint_{key}",
                    {
                        "artifact_type": artifact_type,
                        "field_type": "array_rag_hint",
                    },
                )
            )

    return symbols


def _parse_json_lines(file_path: Path, source: str) -> list[Symbol]:
    symbols: list[Symbol] = []
    artifact_type = _artifact_type(file_path)
    for line_no, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue

        keys = [k for k in payload.keys() if isinstance(k, str)]
        if not keys:
            continue

        line_metadata = {"line": line_no, "top_level_keys": keys, "entry_count": 1, "artifact_type": artifact_type}
        rag_fields = sorted(key for key in keys if key in KNOWN_RAG_CHUNK_KEYS)
        if rag_fields:
            line_metadata["rag_fields"] = rag_fields

        symbols.append(
            Symbol(
                id=make_symbol_id(file_path.as_posix(), f"jsonl_chunk_{line_no}", "jsonl_chunk"),
                name=f"jsonl_chunk_{line_no}",
                qualified_name=f"jsonl_chunk_{line_no}",
                kind="jsonl_chunk",
                language="json",
                file_path=file_path.as_posix(),
                line_start=line_no,
                line_end=line_no,
                byte_start=0,
                byte_end=0,
                signature="jsonl chunk",
                metadata=_symbol_metadata(line_metadata),
            )
        )

        for rag_field in rag_fields:
            symbols.append(
                Symbol(
                    id=make_symbol_id(file_path.as_posix(), f"jsonl_{rag_field}_{line_no}", "jsonl_rag_field"),
                    name=f"jsonl_{rag_field}_{line_no}",
                    qualified_name=f"jsonl_{rag_field}_{line_no}",
                    kind="jsonl_rag_field",
                    language="json",
                    file_path=file_path.as_posix(),
                    line_start=line_no,
                    line_end=line_no,
                    byte_start=0,
                    byte_end=0,
                    signature=f"jsonl rag field: {rag_field}",
                    metadata=_symbol_metadata(
                        {
                            "line": line_no,
                            "rag_field": rag_field,
                            "artifact_type": artifact_type,
                        }
                    ),
                )
            )

    return symbols


def parse_file(file_path: Path, source: str) -> list[Symbol]:
    if file_path.suffix.lower() == ".jsonl":
        return _parse_json_lines(file_path, source)

    try:
        payload = json.loads(source)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        return _parse_json_object(file_path, payload)
    if isinstance(payload, list):
        return _parse_json_array(file_path, payload)
    return []
