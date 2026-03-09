from pathlib import Path

from faststack_mcp.tools.index_folder import run as index_folder
from faststack_mcp.tools.search_symbols import run as search_symbols


def test_synthetic_symbols_are_hidden_from_default_search(tmp_path: Path):
    (tmp_path / "src" / "hooks").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src/hooks/legacy.ts").write_text("const legacy = 1\n")

    result = index_folder(str(tmp_path))
    project_id = result["project_id"]
    # synthetic file-scope symbol should be present but hidden by default
    default_search = search_symbols(project_id, "legacy_hook")
    assert default_search["symbols"] == []

    explicit_search = search_symbols(project_id, "legacy_hook", include_synthetic=True)
    assert any(item["name"] == "legacy_frontend_hook" for item in explicit_search["symbols"])
