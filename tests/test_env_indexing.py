from pathlib import Path

from faststack_mcp.storage import load_project
from faststack_mcp.tools.index_folder import run as index_folder


def test_env_files_optional_indexing(tmp_path: Path):
    (tmp_path / ".env").write_text("SECRET=abc\n")
    (tmp_path / ".env.local").write_text("LOCAL=true\n")
    (tmp_path / ".env.example").write_text("SECRET=\n")
    (tmp_path / "public.ts").write_text("export const x=1\n")

    result_no_env = index_folder(str(tmp_path), include_env_files=False)
    project_no_env = result_no_env["project_id"]
    assert ".env" not in load_project(project_no_env).files
    assert ".env.local" not in load_project(project_no_env).files
    assert ".env.example" in load_project(project_no_env).files

    result_env = index_folder(str(tmp_path), include_env_files=True)
    project_with_env = result_env["project_id"]
    indexed_with_env = load_project(project_with_env)
    assert ".env" in indexed_with_env.files
    assert ".env.local" in indexed_with_env.files
    assert indexed_with_env.files[".env"].language == "env"
    assert indexed_with_env.files[".env.example"].metadata.get("env_template") is True
    assert indexed_with_env.files[".env.local"].metadata.get("env_file") is True
