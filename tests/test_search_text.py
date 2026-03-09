from pathlib import Path

from faststack_mcp.tools.index_folder import run as index_folder
from faststack_mcp.tools.search_text import run as search_text


def test_search_text_skips_env_files(tmp_path: Path):
    (tmp_path / "app.ts").write_text("export const app = 1\n")
    (tmp_path / ".env").write_text("SECRET=supersecret\n")

    result = index_folder(str(tmp_path), include_env_files=True)
    output = search_text(result["project_id"], "SECRET")

    assert output["matches"] == []
