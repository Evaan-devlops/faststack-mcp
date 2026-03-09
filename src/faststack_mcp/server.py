from __future__ import annotations

from mcp.server.fastmcp import FastMCP

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
        return index_folder(
            path,
            force=force,
            max_file_size=max_file_size,
            include_env_files=include_env_files,
        )

    @mcp.tool(name="list_projects")
    def list_projects_tool() -> dict:
        return list_projects()

    @mcp.tool(name="get_file_tree")
    def get_file_tree_tool(project_id: str) -> dict:
        return get_file_tree(project_id)

    @mcp.tool(name="get_file_outline")
    def get_file_outline_tool(project_id: str, file_path: str) -> dict:
        return get_file_outline(project_id, file_path)

    @mcp.tool(name="search_symbols")
    def search_symbols_tool(
        project_id: str, query: str, kind: str | None = None, language: str | None = None
    ) -> dict:
        return search_symbols(project_id, query=query, kind=kind, language=language)

    @mcp.tool(name="get_symbol")
    def get_symbol_tool(project_id: str, symbol_id: str) -> dict:
        return get_symbol(project_id, symbol_id)

    @mcp.tool(name="search_text")
    def search_text_tool(project_id: str, query: str, limit: int = 200) -> dict:
        return search_text(project_id, query, limit=limit)

    @mcp.tool(name="get_project_outline")
    def get_project_outline_tool(project_id: str) -> dict:
        return get_project_outline(project_id)

    @mcp.tool(name="invalidate_cache")
    def invalidate_cache_tool(project_id: str) -> dict:
        return invalidate_cache(project_id)

    return mcp


def run_server() -> None:
    mcp = create_server()
    mcp.run()
