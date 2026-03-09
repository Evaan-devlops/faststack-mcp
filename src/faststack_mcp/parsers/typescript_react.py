from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..models import Symbol
from ..utils.offsets import build_line_offsets, line_span_to_bytes
from . import make_symbol_id

ARROW_HOOK_RE = re.compile(r"(?m)^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*[:=]")
CLASS_USAGE = {
    "page.tsx",
    "page.ts",
    "page.jsx",
    "page.js",
    "layout.tsx",
    "layout.ts",
    "layout.jsx",
    "layout.js",
    "route.tsx",
    "route.ts",
    "route.jsx",
    "route.js",
    "index.tsx",
    "index.ts",
    "index.jsx",
    "index.js",
}

JSX_TYPES = {
    "jsx_element",
    "jsx_self_closing_element",
    "jsx_fragment",
    "jsx_expression",
}


def _is_pascal_case(name: str) -> bool:
    return bool(re.match(r"^[A-Z][A-Za-z0-9_]*$", name))


def _is_hook_name(name: str) -> bool:
    return bool(re.match(r"^use[A-Z].*", name))


def _node_text(node: Any, source: str) -> str:
    if not node:
        return ""
    return source[node.start_byte : node.end_byte]


def _line_numbers(node: Any) -> tuple[int, int]:
    start_line = getattr(node, "start_point", (0, 0))[0] + 1
    end_line = getattr(node, "end_point", (start_line, 0))[0] + 1
    return start_line, end_line


def _byte_range(node: Any, source: str, offsets: list[int]) -> tuple[int, int]:
    start_line, end_line = _line_numbers(node)
    start_col = getattr(node, "start_point", (0, 0))[1]
    end_col = getattr(node, "end_point", (start_col, 0))[1]
    return line_span_to_bytes(
        offsets,
        start_line=start_line,
        end_line=end_line,
        start_col=start_col,
        end_col=end_col,
    )


def _first_identifier(node: Any, source: str) -> str | None:
    for child_name in ("name", "declaration", "type"):
        child = node.child_by_field_name(child_name)
        if child and child.type in {"identifier", "type_identifier", "property_identifier"}:
            return _node_text(child, source)
    for child in node.children:
        if child.type in {"identifier", "type_identifier", "property_identifier", "private_property_identifier"}:
            return _node_text(child, source)
    return None


def _contains_jsx(node: Any) -> bool:
    if node is None:
        return False
    if node.type in JSX_TYPES:
        return True
    for child in node.children:
        if _contains_jsx(child):
            return True
    return False


def _arrow_or_function_returns_jsx(node: Any) -> bool:
    if node is None:
        return False
    body = node.child_by_field_name("body") if node.type in {"function", "function_expression", "arrow_function"} else node
    if body is None:
        return False
    if body.type == "statement_block":
        for child in body.children:
            if child.type == "return_statement" and _contains_jsx(child):
                return True
        return False
    return _contains_jsx(body)


def _infer_frontend_category(path: Path) -> str | None:
    parts = [part.lower() for part in path.as_posix().split("/") if part]
    if "src" in parts:
        parts = parts[parts.index("src") + 1 :]

    if "app" in parts:
        return "app"
    if "pages" in parts:
        return "pages"
    if "components" in parts:
        return "components"
    if "hooks" in parts:
        return "hooks"
    if "features" in parts:
        feature_idx = parts.index("features")
        remaining = parts[feature_idx + 1 :]
        if "api" in remaining or any(p.split(".")[0] == "api" for p in remaining):
            return "api"
        return "features"
    if "store" in parts or "stores" in parts:
        return "store"
    if "utils" in parts:
        return "utils"
    if "types" in parts:
        return "types"
    if "api" in parts:
        return "api"
    if "lib" in parts and "http" in parts:
        return "api"
    if "lib" in parts:
        return "utils"
    return None


def _resolve_kind(base_kind: str, name: str, category: str | None, has_jsx: bool) -> str:
    if base_kind in {"type", "interface", "class"}:
        return base_kind

    if category == "components" and (_is_pascal_case(name) or has_jsx):
        return "component"

    if has_jsx and _is_pascal_case(name):
        return "component"

    if category == "hooks" and _is_hook_name(name):
        return "hook"
    if _is_hook_name(name):
        return "hook"

    if category == "store":
        return "store"
    if category == "api":
        return "api"
    if category == "utils":
        return "utils"
    if category == "types":
        return "types"
    if base_kind in {"function", "exported_function"}:
        if has_jsx and _is_pascal_case(name):
            return "component"
        return "function"
    return base_kind


def _to_symbol(
    file_path: Path,
    name: str,
    kind: str,
    node: Any,
    source: str,
    offsets: list[int],
    metadata: dict[str, Any] | None = None,
    signature: str | None = None,
    file_category: str | None = None,
    parser_name: str | None = None,
    synthetic: bool = False,
    qualified_name: str | None = None,
) -> Symbol:
    start_line, end_line = _line_numbers(node)
    byte_start, byte_end = _byte_range(node, source, offsets)
    lines = source.splitlines()
    if not signature:
        signature = lines[start_line - 1].strip() if lines and start_line <= len(lines) else ""
    symbol_metadata = dict(metadata or {})
    symbol_metadata.setdefault("frontend_category", file_category)
    if parser_name is not None:
        symbol_metadata.setdefault("parser", parser_name)
    if synthetic:
        symbol_metadata["synthetic"] = True
    language = "typescript"
    suffix = file_path.suffix.lower()
    if suffix in {".js", ".jsx"}:
        language = "javascript"

    return Symbol(
        id=make_symbol_id(file_path.as_posix(), name, kind),
        name=name,
        qualified_name=qualified_name if qualified_name is not None else name,
        kind=kind,
        language=language,
        file_path=file_path.as_posix(),
        line_start=start_line,
        line_end=end_line,
        byte_start=byte_start,
        byte_end=byte_end,
        signature=signature,
        metadata=symbol_metadata,
    )


def _add_route_or_page_symbols(
    file_path: Path,
    source: str,
    symbols: list[Symbol],
    category: str | None,
    parser_name: str,
) -> None:
    if file_path.name not in CLASS_USAGE:
        return
    if "export default" not in source:
        return
    source_name = file_path.stem.replace("-", "_").replace(" ", "_")
    source_name = source_name[:1].upper() + source_name[1:] if source_name else "Route"
    kind = "frontend_app" if category == "app" else "frontend_page"
    symbol_id = make_symbol_id(file_path.as_posix(), f"{source_name}Route", kind)
    symbols.append(
        Symbol(
            id=symbol_id,
            name=f"{source_name}Route",
            qualified_name=f"{source_name}Route",
            kind=kind,
            language="typescript",
            file_path=file_path.as_posix(),
            line_start=1,
            line_end=1,
            byte_start=0,
            byte_end=0,
            signature=f"route/page module {file_path.name}",
            metadata={
                "kind": "route_or_page",
                "frontend_category": category or "page",
                "parser": parser_name,
            },
        )
    )


def _add_file_scope_symbol(
    file_path: Path,
    symbols: list[Symbol],
    category: str | None,
    parser_name: str,
) -> None:
    if category is None:
        return
    kind_map = {
        "app": "frontend_app",
        "pages": "frontend_page",
        "components": "frontend_component",
        "features": "frontend_feature",
        "hooks": "frontend_hook",
        "store": "store",
        "api": "api",
        "utils": "utils",
        "types": "types",
    }
    mapped = kind_map.get(category)
    if mapped is None:
        return
    short_kind = mapped.replace("frontend_", "")
    symbols.append(
        _to_symbol(
            file_path=file_path,
            name=f"{file_path.stem}_{mapped}",
            qualified_name=f"{file_path.stem}_{short_kind}",
            kind=mapped,
            node=_make_fake_node(file_path),
            source="",
            offsets=[0],
            signature=f"frontend module: {file_path.name}",
            metadata={"frontend_category": category, "scope": "file"},
            parser_name=parser_name,
            synthetic=True,
        )
    )


def _make_fake_node(file_path: Path):
    class _FakeNode:
        start_byte = 0
        end_byte = 0
        start_point = (0, 0)
        end_point = (1, 0)

    return _FakeNode()


def _resolve_language_object(language: Any) -> Any:
    if callable(language):
        try:
            return language()
        except TypeError:
            return language
    return language


def _set_parser_language(parser: Any, language: Any) -> bool:
    lang_obj = _resolve_language_object(language)
    if lang_obj is None:
        return False

    set_language = getattr(parser, "set_language", None)
    if callable(set_language):
        try:
            set_language(lang_obj)
            return True
        except Exception:
            pass

    try:
        parser.language = lang_obj
        return True
    except Exception:
        return False


def _load_tree_sitter_parser(file_ext: str):
    try:
        from tree_sitter import Parser  # type: ignore
    except Exception:
        return None, None
    try:
        from tree_sitter_typescript import language as ts_language  # type: ignore

        language = ts_language("tsx" if file_ext in {".tsx", ".jsx"} else "typescript")
        return Parser, language
    except Exception:
        pass
    try:
        import tree_sitter_typescript as ts_pkg  # type: ignore

        preferred = ("tsx", "typescript") if file_ext in {".tsx", ".jsx"} else ("typescript", "tsx")
        for mod_name in preferred:
            mod = getattr(ts_pkg, mod_name, None)
            if mod is None:
                continue
            language_attr = getattr(mod, "language", None)
            if language_attr is not None:
                return Parser, language_attr

        for fn_name in ("language_tsx", "tsx_language", "language_typescript", "typescript_language"):
            fn = getattr(ts_pkg, fn_name, None)
            if callable(fn):
                if ("tsx" in fn_name and file_ext in {".tsx", ".jsx"}) or (
                    "typescript" in fn_name and file_ext not in {".tsx", ".jsx"}
                ):
                    return Parser, fn
    except Exception:
        pass
    return None, None


def _extract_from_tree_sitter(
    file_path: Path,
    source: str,
    offsets: list[int],
) -> list[Symbol]:
    Parser, language = _load_tree_sitter_parser(file_path.suffix.lower())
    if Parser is None or language is None:
        return []

    parser = Parser()
    if not _set_parser_language(parser, language):
        raise RuntimeError("tree-sitter language adapter unavailable")

    tree = parser.parse(source.encode("utf-8"))
    root = tree.root_node
    symbols: list[Symbol] = []
    category = _infer_frontend_category(file_path)

    def parse_var_or_binding(node: Any) -> None:
        for declarator in node.children:
            if declarator.type != "variable_declarator":
                continue
            name = _first_identifier(declarator, source)
            if not name:
                continue
            value = declarator.child_by_field_name("value")
            if value is None:
                continue
            if value.type not in {"arrow_function", "function", "function_expression", "parenthesized_expression"}:
                continue
            func_node = value
            kind = _resolve_kind("function", name, category, _arrow_or_function_returns_jsx(func_node))
            symbols.append(
                _to_symbol(
                    file_path=file_path,
                    name=name,
                    kind=kind,
                    node=declarator,
                    source=source,
                    offsets=offsets,
                    file_category=category,
                    parser_name="treesitter",
                )
            )

    def parse_node(node: Any) -> None:
        if node.type == "function_declaration":
            name = _first_identifier(node, source)
            if not name:
                return
            return_type = node.child_by_field_name("body")
            kind = _resolve_kind("function", name, category, _arrow_or_function_returns_jsx(return_type))
            symbols.append(
                _to_symbol(
                    file_path=file_path,
                    name=name,
                    kind=kind,
                    node=node,
                    source=source,
                    offsets=offsets,
                    metadata={"frontend_category": category or "backend", "kind": "route_or_method"},
                    file_category=category,
                    parser_name="treesitter",
                )
            )
            return

        if node.type in {"type_alias_declaration"}:
            name = _first_identifier(node, source)
            if not name:
                return
            symbols.append(
                _to_symbol(
                    file_path=file_path,
                    name=name,
                    kind="type",
                    node=node,
                    source=source,
                    offsets=offsets,
                    metadata={"frontend_category": category},
                    file_category=category,
                    parser_name="treesitter",
                )
            )
            return

        if node.type == "interface_declaration":
            name = _first_identifier(node, source)
            if not name:
                return
            symbols.append(
                _to_symbol(
                    file_path=file_path,
                    name=name,
                    kind="interface",
                    node=node,
                    source=source,
                    offsets=offsets,
                    metadata={"frontend_category": category},
                    file_category=category,
                    parser_name="treesitter",
                )
            )
            return

        if node.type in {"class_declaration"}:
            name = _first_identifier(node, source)
            if not name:
                return
            kind = "types" if category == "types" else "class"
            symbols.append(
                _to_symbol(
                    file_path=file_path,
                    name=name,
                    kind=kind,
                    node=node,
                    source=source,
                    offsets=offsets,
                    metadata={"frontend_category": category},
                    file_category=category,
                    parser_name="treesitter",
                )
            )
            return

        if node.type in {"lexical_declaration", "variable_statement", "variable_declaration"}:
            parse_var_or_binding(node)
            return

        if node.type == "export_statement":
            declaration = node.child_by_field_name("declaration")
            if declaration is not None:
                parse_node(declaration)
            return

    for child in root.children:
        parse_node(child)

    for symbol in symbols:
        if symbol.language in {"javascript", "typescript"} and symbol.kind in {"function", "component", "frontend_hook", "hook"}:
            symbol.metadata.setdefault("category", "frontend")

    return symbols


def _regex_parse(file_path: Path, source: str, offsets: list[int]) -> list[Symbol]:
    symbols: list[Symbol] = []
    lines = source.splitlines(keepends=True)
    category = _infer_frontend_category(file_path)
    component_signature_re = re.compile(
        r"(?m)^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:\([^)]*\)|[^=\n;]+?)\s*=>"
    )

    for match in re.finditer(r"(?m)^export\s+function\s+([A-Za-z_$][\w$]*)\s*\(", source):
        name = match.group(1)
        start_line = source[:match.start(1)].count("\n") + 1
        signature = lines[start_line - 1].strip() if lines and start_line <= len(lines) else ""
        kind = _resolve_kind("function", name, category, False)
        if kind == "function" and _is_hook_name(name):
            kind = "hook"
        byte_start, byte_end = line_span_to_bytes(offsets, start_line=start_line, end_line=start_line, end_col=0)
        symbols.append(
            Symbol(
                id=make_symbol_id(file_path.as_posix(), name, kind),
                name=name,
                qualified_name=name,
                kind=kind,
                language="javascript" if file_path.suffix.lower() in {".js", ".jsx"} else "typescript",
                file_path=file_path.as_posix(),
                line_start=start_line,
                line_end=start_line,
                byte_start=byte_start,
                byte_end=byte_end,
                signature=signature,
                metadata={
                    "frontend_category": category or "frontend",
                    "parser": "regex",
                },
            )
        )

    for match in component_signature_re.finditer(source):
        name = match.group(1)
        if any(item.name == name for item in symbols):
            continue
        start_line = source[:match.start(1)].count("\n") + 1
        signature = lines[start_line - 1] if lines else ""
        end_line = source.count("\n", 0, match.end()) + 1
        kind = _resolve_kind("function", name, category, True)
        byte_start, byte_end = line_span_to_bytes(offsets, start_line=start_line, end_line=end_line, end_col=0)
        symbols.append(
            Symbol(
                id=make_symbol_id(file_path.as_posix(), name, kind),
                name=name,
                qualified_name=name,
                kind=kind,
                language="javascript" if file_path.suffix.lower() in {".js", ".jsx"} else "typescript",
                file_path=file_path.as_posix(),
                line_start=start_line,
                line_end=end_line,
                byte_start=byte_start,
                byte_end=byte_end,
                signature=signature.strip(),
                metadata={"frontend_category": category, "parser": "regex"},
            )
        )

    for match in re.finditer(r"(?m)^export\s+type\s+([A-Za-z_$][\w$]*)\s*\[?[^\n;]*", source):
        name = match.group(1)
        if any(item.name == name and item.kind == "type" for item in symbols):
            continue
        line_no = source[:match.start(1)].count("\n") + 1
        signature = lines[line_no - 1].strip() if lines and line_no <= len(lines) else ""
        byte_start, byte_end = line_span_to_bytes(offsets, start_line=line_no, end_line=line_no, end_col=0)
        symbols.append(
            Symbol(
                id=make_symbol_id(file_path.as_posix(), name, "type"),
                name=name,
                qualified_name=name,
                kind="type",
                language="javascript" if file_path.suffix.lower() in {".js", ".jsx"} else "typescript",
                file_path=file_path.as_posix(),
                line_start=line_no,
                line_end=line_no,
                byte_start=byte_start,
                byte_end=byte_end,
                signature=signature,
                metadata={"frontend_category": category, "parser": "regex"},
            )
        )

    for match in re.finditer(r"(?m)^export\s+interface\s+([A-Za-z_$][\w$]*)\s*", source):
        name = match.group(1)
        if any(item.name == name and item.kind == "interface" for item in symbols):
            continue
        line_no = source[:match.start(1)].count("\n") + 1
        signature = lines[line_no - 1].strip() if lines and line_no <= len(lines) else ""
        byte_start, byte_end = line_span_to_bytes(offsets, start_line=line_no, end_line=line_no, end_col=0)
        symbols.append(
            Symbol(
                id=make_symbol_id(file_path.as_posix(), name, "interface"),
                name=name,
                qualified_name=name,
                kind="interface",
                language="javascript" if file_path.suffix.lower() in {".js", ".jsx"} else "typescript",
                file_path=file_path.as_posix(),
                line_start=line_no,
                line_end=line_no,
                byte_start=byte_start,
                byte_end=byte_end,
                signature=signature,
                metadata={"frontend_category": category, "parser": "regex"},
            )
        )

    for match in ARROW_HOOK_RE.finditer(source):
        name = match.group(1)
        if not _is_hook_name(name):
            continue
        if any(item.name == name for item in symbols):
            continue
        line_no = source[:match.start(1)].count("\n") + 1
        signature = lines[line_no - 1].strip() if lines and line_no <= len(lines) else ""
        byte_start, byte_end = line_span_to_bytes(offsets, start_line=line_no, end_line=line_no, end_col=0)
        symbols.append(
            Symbol(
                id=make_symbol_id(file_path.as_posix(), name, "hook"),
                name=name,
                qualified_name=name,
                kind="hook",
                language="javascript" if file_path.suffix.lower() in {".js", ".jsx"} else "typescript",
                file_path=file_path.as_posix(),
                line_start=line_no,
                line_end=line_no,
                byte_start=byte_start,
                byte_end=byte_end,
                signature=signature,
                metadata={"frontend_category": category, "parser": "regex"},
            )
        )

    return symbols


def parse_file(file_path: Path, source: str) -> list[Symbol]:
    path = file_path
    offsets = build_line_offsets(source)
    category = _infer_frontend_category(file_path)
    symbols: list[Symbol] = []
    used_parser = "regex"

    if _load_tree_sitter_parser(file_path.suffix.lower())[0] is not None:
        try:
            symbols.extend(_extract_from_tree_sitter(path, source, offsets))
            used_parser = "treesitter"
        except Exception:
            symbols = []
            used_parser = "regex"

    if not symbols:
        symbols.extend(_regex_parse(path, source, offsets))
        if symbols:
            used_parser = "regex"

    if not symbols:
        _add_file_scope_symbol(path, symbols, category, parser_name=used_parser)

    _add_route_or_page_symbols(path, source, symbols, category, parser_name=used_parser)

    for symbol in symbols:
        if symbol.metadata is not None:
            symbol.metadata.setdefault("frontend_category", category)

    return symbols
