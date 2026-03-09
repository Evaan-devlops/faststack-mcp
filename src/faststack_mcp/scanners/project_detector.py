from __future__ import annotations

from collections import Counter

from ..models import FileRecord


def infer_languages_and_frameworks(
    file_records: dict[str, FileRecord],
    symbols: list[dict[str, object]],
) -> tuple[list[str], list[str]]:
    languages: Counter[str] = Counter()
    frameworks: set[str] = set()

    for rec in file_records.values():
        languages[rec.language] += 1
        path = rec.path.lower()
        if "alembic" in path or "migrations" in path:
            frameworks.add("PostgreSQL")
        if rec.metadata.get("artifact_type") == "rag" or rec.language == "rag_artifact":
            frameworks.add("RAG")
        if rec.metadata.get("env_template") or rec.metadata.get("env_file") or path.endswith(".env.example"):
            frameworks.add("Environment")

    detected_languages = sorted(languages)

    if "python" in detected_languages:
        frameworks.add("FastAPI")
        frameworks.add("Python")

    for symbol in symbols:
        kind = str(symbol.get("kind", ""))
        if kind in {"route", "pydantic_model"}:
            frameworks.add("FastAPI")
        if kind in {
            "component",
            "hook",
            "api_client",
            "store",
            "api",
            "utils",
            "types",
            "app_shell",
            "frontend_page",
            "frontend_component",
            "frontend_api",
            "frontend_store",
            "frontend_utils",
            "frontend_type",
            "frontend_hook",
        }:
            frameworks.add("React")
            frameworks.add("TypeScript")
            frameworks.add("JavaScript")
        if kind in {"table", "view", "index", "migration", "alter_table"}:
            frameworks.add("PostgreSQL")
        if kind in {"tailwind_config", "tailwind_class_usage"}:
            frameworks.add("Tailwind CSS")
        if kind in {
            "package_config",
            "pyproject_config",
            "vite_config",
            "eslint_config",
            "env_variable",
            "config_json",
            "json_key",
            "jsonl_chunk",
        }:
            frameworks.add("Configuration")

    return detected_languages, sorted(frameworks)
