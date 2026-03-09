from pathlib import Path

from faststack_mcp.storage import load_project
from faststack_mcp.tools.get_project_outline import _ALL_SECTIONS, run as get_project_outline
from faststack_mcp.tools.index_folder import run as index_folder


def _all_outline(project_id: str) -> dict:
    return get_project_outline(project_id, sections=list(_ALL_SECTIONS))["outline"]


def _write_files(base: Path) -> None:
    (base / "src" / "app").mkdir(parents=True, exist_ok=True)
    (base / "src" / "components").mkdir(parents=True, exist_ok=True)
    (base / "src" / "store").mkdir(parents=True, exist_ok=True)
    (base / "src" / "hooks").mkdir(parents=True, exist_ok=True)
    (base / "backend").mkdir(parents=True, exist_ok=True)

    (base / "src/app/layout.tsx").write_text("export default function RootLayout() { return <div/> }")
    (base / "src/components/Hello.tsx").write_text("export const Hello = () => <div/>\n")
    (base / "src/store/state.ts").write_text("export const createStore = () => ({})\n")
    (base / "src/hooks/useTheme.ts").write_text("export const useTheme = () => 'dark'\n")
    (base / "backend/main.py").write_text("from fastapi import APIRouter\nrouter=APIRouter()\n@router.get('/ping')\ndef ping():\n    return {'ok': True}\n")
    (base / "package.json").write_text('{"name":"demo","dependencies":{"react":"18"}}')
    (base / ".env.example").write_text("API_KEY=placeholder\n")
    (base / "index.faiss").write_bytes(b"faiss-binary")


def test_outline_groups_frontend_backend_env_and_artifacts(tmp_path: Path):
    _write_files(tmp_path)
    result = index_folder(str(tmp_path), include_env_files=True)

    groups = _all_outline(result["project_id"])

    assert "backend_routes" in groups
    assert "frontend_components" in groups
    assert "frontend_store" in groups
    assert "frontend_hooks" in groups
    assert "config_files" in groups
    assert "rag_artifacts" in groups
    assert "env_config_templates" in groups

    assert groups["rag_artifacts"]
    assert groups["env_config_templates"]
    assert any(item["kind"] == "rag_artifact" for item in groups["rag_artifacts"])


def test_outline_fallback_frontend_path_bucketing(tmp_path: Path):
    project = tmp_path
    (project / "src/hooks").mkdir(parents=True, exist_ok=True)
    (project / "src/store").mkdir(parents=True, exist_ok=True)
    (project / "src/features/users/api").mkdir(parents=True, exist_ok=True)
    (project / "src/types").mkdir(parents=True, exist_ok=True)
    (project / "src/lib/http").mkdir(parents=True, exist_ok=True)

    (project / "src/hooks/legacy.ts").write_text("const legacy = 1\n")
    (project / "src/store/session.ts").write_text("const session = { id: 1 }\n")
    (project / "src/features/users/api/endpoint.ts").write_text("const payload = 1\n")
    (project / "src/types/schema.ts").write_text("const schema = 1\n")
    (project / "src/lib/http/client.ts").write_text("const http = 1\n")

    result = index_folder(str(project))
    groups = _all_outline(result["project_id"])

    assert any(item["file_path"] == "src/hooks/legacy.ts" for item in groups["frontend_hooks"])
    assert any(item["file_path"] == "src/store/session.ts" for item in groups["frontend_store"])
    assert any(item["file_path"] == "src/features/users/api/endpoint.ts" for item in groups["frontend_api"])
    assert any(item["file_path"] == "src/types/schema.ts" for item in groups["frontend_types"])
    assert any(item["file_path"] == "src/lib/http/client.ts" for item in groups["frontend_api"])


def test_rag_artifact_outline_classification(tmp_path: Path):
    project = tmp_path / "project"
    rag = project / "backend" / "rag_artifacts"
    rag.mkdir(parents=True, exist_ok=True)
    (project / "backend").mkdir(exist_ok=True)
    (project / "backend/main.py").write_text("print('ok')\n")
    (rag / "index.faiss").write_bytes(b"faiss-binary")
    (rag / "chunks.jsonl").write_text('{"id":1,"metadata":{"source":"rag"}}\n')
    (rag / "manifest.json").write_text('{"name":"demo","start_url":"/"}\n')

    result = index_folder(str(project), include_env_files=False)
    project_record = load_project(result["project_id"])
    groups = _all_outline(result["project_id"])

    assert sorted(item["metadata"]["rag_artifact_type"] for item in groups["rag_artifacts"]) == [
        "chunks_jsonl",
        "faiss_index",
        "manifest",
    ]
    assert all(item["metadata"]["content_indexed"] is False for item in groups["rag_artifacts"])
    assert all(item["kind"] == "rag_artifact" for item in groups["rag_artifacts"])
    assert project_record.files["backend/rag_artifacts/index.faiss"].metadata.get("artifact_type") == "rag"
    assert project_record.files["backend/rag_artifacts/chunks.jsonl"].language == "rag_artifact"
    assert project_record.files["backend/rag_artifacts/manifest.json"].language == "rag_artifact"
