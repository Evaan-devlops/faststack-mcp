from pathlib import Path

from faststack_mcp.parsers.typescript_react import parse_file


def test_typescript_component_and_hook_symbols():
    sample = (
        "import React from 'react'\n\n"
        "export const MyComponent = () => {\n"
        "  return <div>Hello</div>\n"
        "}\n\n"
        "export function useUsers() {\n"
        "  return []\n"
        "}\n\n"
        "export type User = { id: number }\n\n"
        "export interface ApiResp { ok: boolean }\n\n"
    )
    symbols = parse_file(Path("src/index.tsx"), sample)
    kinds = {s.kind for s in symbols}
    assert "component" in kinds
    assert "hook" in kinds
    assert "type" in kinds
    assert "interface" in kinds


def test_javascript_files_supported_in_react_parser():
    sample = (
        "export const Widget = () => <div>Widget</div>;\n"
        "export function useWidgetData() { return 123; }\n"
    )
    symbols = parse_file(Path("src/utils/widget.js"), sample)
    kinds = {item.kind for item in symbols}
    assert "component" in kinds
    assert "hook" in kinds
    assert all(item.language == "javascript" for item in symbols if item.name in {"Widget", "useWidgetData"})


def test_folder_classification_adds_store_and_api_symbols():
    store_sample = "export const createStore = () => ({})"
    store_symbols = parse_file(Path("src/store/user.ts"), store_sample)
    assert any(item.kind == "store" for item in store_symbols)

    api_sample = "export function fetchUsers() { return [] }"
    api_symbols = parse_file(Path("src/features/users/api.ts"), api_sample)
    assert any(item.kind == "api" for item in api_symbols)
