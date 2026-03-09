from pathlib import Path

from faststack_mcp.parsers.config_parser import parse_file


def test_config_parser_reads_package_json_dependencies():
    source = '{"name":"app","dependencies":{"react":"18","fastapi":"0.115"},"scripts":{"start":"vite"}}'
    symbols = parse_file(Path("package.json"), source)
    kinds = {item.kind for item in symbols}
    assert "package_dependency" in kinds
    assert "package_script" in kinds
    assert any(item.name == "package_dep_react" for item in symbols)


def test_config_parser_reads_tsconfig_and_vite():
    tsconfig = '{"compilerOptions":{"target":"ES2020","moduleResolution":"Node"}}'
    ts_symbols = parse_file(Path("tsconfig.app.json"), tsconfig)
    assert any(item.kind == "config_root" for item in ts_symbols)
    vite = """import { defineConfig } from 'vite'
export default defineConfig({ plugins: [] , server: { port: 3000 } })
"""
    vite_symbols = parse_file(Path("vite.config.ts"), vite)
    assert any(item.kind == "vite_config" for item in vite_symbols)
    assert any("server" in item.name for item in vite_symbols)


def test_config_parser_does_not_parse_manifest_json():
    payload = '{"name":"demo","start_url":"/"}'
    symbols = parse_file(Path("manifest.json"), payload)
    assert symbols == []
