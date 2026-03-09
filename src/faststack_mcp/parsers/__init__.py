from __future__ import annotations


def make_symbol_id(file_path: str, qualified_name: str, kind: str) -> str:
    safe_name = qualified_name.replace(" ", "_")
    return f"{file_path}::{safe_name}#{kind}"
