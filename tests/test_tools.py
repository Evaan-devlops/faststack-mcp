from pathlib import Path

from faststack_mcp.tools.index_folder import run as index_folder
from faststack_mcp.tools.list_projects import run as list_projects


def test_tools_basic_index_and_list(tmp_path: Path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "main.py").write_text("print('ok')")
    (project_dir / "api.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.get('/health')\n"
        "def health():\n    return {'ok': True}\n"
    )
    result = index_folder(str(project_dir))
    assert "project_id" in result
    listed = list_projects()
    assert any(item["project_id"] == result["project_id"] for item in listed["projects"])
