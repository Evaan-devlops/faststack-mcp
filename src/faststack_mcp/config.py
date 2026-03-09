from __future__ import annotations

from pathlib import Path


DEFAULT_CACHE_ROOT: Path = Path.home() / ".faststack-mcp"
PROJECTS_DIR_NAME = "projects"
INDEX_FILE_NAME = "index.json"

DEFAULT_MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024
DEFAULT_SEARCH_LIMIT = 50
DEFAULT_TEXT_SEARCH_LIMIT = 200
DEFAULT_TEXT_CONTEXT_LINES = 2

SUPPORTED_EXACT_FILES = {
    "tailwind.config.js",
    "tailwind.config.ts",
    "package.json",
    "pyproject.toml",
    "alembic.ini",
    "vite.config.js",
    "vite.config.ts",
    "vite.config.mjs",
    "vite.config.cjs",
    "eslint.config.js",
    "manifest.json",
    ".env.example",
    "tsconfig.json",
    "tsconfig.app.json",
    "tsconfig.node.json",
    "index.faiss",
    "chunks.jsonl",
}

SUPPORTED_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".sql",
    ".json",
    ".jsonl",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
}

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    "coverage",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".idea",
    ".vscode",
    ".claude",
}

SENSITIVE_PATTERNS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.crt",
    "*.cert",
    "*.secrets*",
    "id_rsa",
    "id_ed25519",
]

ENV_TEMPLATE_FILES = {".env.example"}

RAG_ARTIFACT_FILES = {
    "index.faiss",
}

CONFIG_FILES_WITH_PREFIX = {
    "vite.config",
    "tsconfig",
}

FRONTEND_SPECIAL_FILENAMES = {
    "manifest.json",
    "vite.config.js",
    "vite.config.ts",
    "vite.config.mjs",
    "vite.config.cjs",
}

MAX_SAMPLE_MATCH_CONTEXT = 4
BINARY_CHUNK_SIZE = 8192

FILE_READ_CHUNK = 16384
