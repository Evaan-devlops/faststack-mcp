from pathlib import Path

from faststack_mcp.security import is_binary_file, is_sensitive_file


def test_sensitive_patterns():
    assert is_sensitive_file(Path(".env"))
    assert is_sensitive_file(Path(".env.local"))
    assert is_sensitive_file(Path("id_rsa"))
    assert not is_sensitive_file(Path("important.py"))


def test_binary_detection(tmp_path: Path):
    binary = tmp_path / "binary.bin"
    binary.write_bytes(b"\x00abc")
    assert is_binary_file(binary)
