from pathlib import Path

from faststack_mcp.parsers.env_parser import parse_file


def test_env_parser_masks_values():
    source = """API_URL=https://example.com\nSECRET=supersecret\nexport PUBLIC_KEY=abc123\n"""
    symbols = parse_file(Path(".env.example"), source)
    assert any(item.kind == "env_config" for item in symbols)
    env_vars = [item for item in symbols if item.kind == "env_variable"]
    assert {item.name for item in env_vars} == {"API_URL", "SECRET", "PUBLIC_KEY"}
    assert all(item.signature.endswith("=***MASKED***") for item in env_vars)
    # ensure original values are not returned in signatures
    assert all("supersecret" not in item.signature for item in env_vars)
    assert all("https://example.com" not in item.signature for item in env_vars)
    assert all(item.metadata.get("masked") is True for item in env_vars)
    assert all(item.metadata.get("parser") == "env_parser" for item in env_vars)
    assert symbols[0].metadata.get("metadata_only") is True
