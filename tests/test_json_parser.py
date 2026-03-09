from pathlib import Path

from faststack_mcp.parsers.json_parser import parse_file
from faststack_mcp.storage import load_project
from faststack_mcp.tools.index_folder import run as index_folder


def test_json_parser_extracts_manifest_like_keys():
    payload = '{"name":"my-app","short_name":"my-app","version":"1.0.0","description":"desc"}'
    symbols = parse_file(Path("manifest.json"), payload)
    kinds = {item.kind for item in symbols}
    assert "json" in kinds
    assert "json_key" in kinds
    assert any(item.metadata.get("artifact_type") == "manifest" for item in symbols)
    assert any(item.name == "manifest_metadata" for item in symbols)


def test_jsonl_chunk_parser_extracts_top_level_keys():
    lines = '{"id":1,"type":"chunk"}\n{"id":2,"metadata":{"source":"rag"}}\n'
    symbols = parse_file(Path("chunks.jsonl"), lines)
    kinds = {item.kind for item in symbols}
    assert "jsonl_chunk" in kinds
    assert any(item.name == "jsonl_chunk_1" for item in symbols)
    assert any(item.kind == "jsonl_rag_field" for item in symbols)
    assert all(item.metadata.get("artifact_type") == "rag_chunks" for item in symbols if item.kind.startswith("jsonl_"))


def test_json_root_array_is_supported():
    payload = '[{"id":1,"text":"hello"},{"id":2,"title":"doc"}]'
    symbols = parse_file(Path("data.json"), payload)
    kinds = {item.kind for item in symbols}
    assert "json" in kinds
    assert "json_key" in kinds
    assert any(item.kind == "json" and item.name == "json_root" and item.metadata.get("root_type") == "array" for item in symbols)


def test_json_parser_routing_for_config_vs_general_json(tmp_path: Path):
    (tmp_path / "manifest.json").write_text('{"name":"demo","start_url":"/"}')
    (tmp_path / "package.json").write_text('{"name":"demo","dependencies":{"react":"18"}}')
    (tmp_path / "tsconfig.json").write_text('{"compilerOptions":{"target":"ES2020"}}')
    (tmp_path / "data.jsonl").write_text('{"a":1}\n')

    result = index_folder(str(tmp_path))
    project = load_project(result["project_id"])
    files = project.files

    assert files["manifest.json"].metadata.get("parser") == "parse_json"
    assert files["package.json"].metadata.get("parser") == "parse_config"
    assert files["tsconfig.json"].metadata.get("parser") == "parse_config"
    assert files["data.jsonl"].metadata.get("parser") == "parse_json"


def test_json_parser_marks_manifest_artifact_metadata():
    payload = '{"name":"demo","start_url":"/"}'
    symbols = parse_file(Path("manifest.json"), payload)
    assert any(item.name == "manifest_metadata" for item in symbols)
