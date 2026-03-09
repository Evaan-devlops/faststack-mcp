from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .config import DEFAULT_SEARCH_LIMIT, DEFAULT_TEXT_SEARCH_LIMIT
from .tools.get_file_outline import run as get_file_outline
from .tools.get_file_tree import run as get_file_tree
from .tools.get_project_outline import run as get_project_outline
from .tools.get_symbol import run as get_symbol
from .tools.index_folder import run as index_folder
from .tools.invalidate_cache import run as invalidate_cache
from .tools.list_projects import run as list_projects
from .tools.search_symbols import run as search_symbols
from .tools.search_text import run as search_text


def create_server() -> FastMCP:
    mcp = FastMCP("faststack")

    @mcp.tool(name="index_folder")
    def index_folder_tool(
        path: str,
        force: bool = False,
        max_file_size: int = 2 * 1024 * 1024,
        include_env_files: bool = False,
    ) -> dict:
        """Index a project folder and cache the result. Safe to call on every agent turn —
        warm cache hits return in ~50ms. Use force=True only when you suspect the cache is stale."""
        return index_folder(
            path,
            force=force,
            max_file_size=max_file_size,
            include_env_files=include_env_files,
        )

    @mcp.tool(name="list_projects")
    def list_projects_tool() -> dict:
        """List all indexed projects with their stats (file count, languages, frameworks).
        Does not load symbol data — lightweight metadata only."""
        return list_projects()

    @mcp.tool(name="search_symbols")
    def search_symbols_tool(
        project_id: str,
        query: str,
        kind: str | None = None,
        language: str | None = None,
        limit: int = DEFAULT_SEARCH_LIMIT,
    ) -> dict:
        """PRIMARY TOOL for navigating code. Search for functions, classes, routes, hooks, models
        by name. Use specific 1-3 word queries (e.g. 'UserService', 'create_user', 'useAuth').
        Broad queries return many low-value results — keep queries targeted.
        After finding a symbol, call get_symbol with its symbol_id to read the actual code.
        Prefer this over reading full files."""
        return search_symbols(project_id, query=query, kind=kind, language=language, limit=limit)

    @mcp.tool(name="get_symbol")
    def get_symbol_tool(project_id: str, symbol_id: str) -> dict:
        """Get the full source code snippet for a specific symbol by its symbol_id.
        Use after search_symbols to read the actual implementation.
        This is the most token-efficient way to read code — returns only the relevant function/class,
        not the entire file."""
        return get_symbol(project_id, symbol_id)

    @mcp.tool(name="search_text")
    def search_text_tool(
        project_id: str,
        query: str,
        limit: int = DEFAULT_TEXT_SEARCH_LIMIT,
    ) -> dict:
        """Full-text search across all indexed source files. Best for finding where a string,
        pattern, or dependency is used (e.g. 'HTTPException', 'embeddings', 'OPENAI_API_KEY').
        Keep limit low (10-20) for targeted lookups. Env files are excluded for security."""
        return search_text(project_id, query, limit=limit)

    @mcp.tool(name="get_project_outline")
    def get_project_outline_tool(project_id: str) -> dict:
        """Get a high-level structural overview of the project grouped by layer
        (routes, models, components, hooks, store, migrations, config).
        Use ONCE per session to orient yourself — result is cached per project fingerprint.
        Do NOT call repeatedly; use search_symbols for subsequent lookups."""
        return get_project_outline(project_id)

    @mcp.tool(name="get_file_tree")
    def get_file_tree_tool(project_id: str) -> dict:
        """Get the full directory tree of indexed files. Use to understand project structure
        when get_project_outline is not enough. Prefer get_project_outline or search_symbols
        for finding specific code."""
        return get_file_tree(project_id)

    @mcp.tool(name="get_file_outline")
    def get_file_outline_tool(project_id: str, file_path: str) -> dict:
        """List all symbols (functions, classes, routes) in a specific file.
        Use when you need to understand a single file's full contents without reading it.
        For a single symbol, prefer search_symbols + get_symbol instead."""
        return get_file_outline(project_id, file_path)

    @mcp.tool(name="invalidate_cache")
    def invalidate_cache_tool(project_id: str) -> dict:
        """Force-remove the cached index for a project. Use when the project has changed
        significantly and index_folder with force=True is not enough."""
        return invalidate_cache(project_id)

    return mcp


def run_server() -> None:
    mcp = create_server()
    mcp.run()
