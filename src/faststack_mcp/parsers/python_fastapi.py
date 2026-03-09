from __future__ import annotations

import ast
from pathlib import Path

from ..models import Symbol
from ..utils.offsets import build_line_offsets, line_span_to_bytes
from . import make_symbol_id

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


def _expr_to_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _expr_to_name(node.value)
        if prefix:
            return f"{prefix}.{node.attr}"
        return node.attr
    if isinstance(node, ast.Call):
        return _expr_to_name(node.func)
    return None


def _is_depends_expr(expr: ast.AST) -> bool:
    return _expr_to_name(expr) == "Depends"


def _get_call_name(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    return _expr_to_name(node.func)


def _is_route_decorator(node: ast.stmt) -> tuple[bool, str | None] | None:
    if not isinstance(node, ast.Call):
        return None
    func_name = _get_call_name(node)
    if not func_name:
        return None
    if "." not in func_name:
        return None
    base, attr = func_name.rsplit(".", 1)
    if attr not in HTTP_METHODS:
        return None
    if base.split(".")[-1] not in {"router", "app", "fastapi", "api_router"}:
        return None
    return True, attr.lower()


def _class_symbol_kind(class_name: str, bases: list[ast.expr]) -> str:
    base_names = {_expr_to_name(base) for base in bases}
    if any(name == "BaseModel" or str(name).endswith("BaseModel") for name in base_names):
        return "pydantic_model"
    if class_name.endswith("Service") or any("Service" in str(b) for b in base_names):
        return "service"
    if class_name.endswith("Repository") or any("Repository" in str(b) for b in base_names):
        return "repository"
    if any(str(name).endswith("Base") or "Model" in str(name) for name in base_names):
        return "model"
    return "class"


def parse_file(file_path: Path, source: str) -> list[Symbol]:
    relative_path = file_path.as_posix()
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    offsets = build_line_offsets(source)
    symbols: list[Symbol] = []
    class_stack: list[str] = []

    def append(
        name: str,
        qual: str,
        kind: str,
        node: ast.AST,
        metadata: dict | None = None,
        signature: str | None = None,
    ) -> None:
        metadata = metadata or {}
        start_line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", start_line)
        start_col = getattr(node, "col_offset", 0)
        end_col = getattr(node, "end_col_offset", 0)
        byte_start, byte_end = line_span_to_bytes(
            offsets,
            start_line=start_line,
            end_line=end_line,
            start_col=start_col,
            end_col=end_col or 0,
        )
        if end_col == 0:
            byte_end = offsets[end_line] if end_line < len(offsets) else offsets[-1]
        snippet_signature = signature
        if snippet_signature is None:
            snippet_signature = lines[start_line - 1].strip() if lines and start_line <= len(lines) else ""
        symbol = Symbol(
            id=make_symbol_id(relative_path, qual, kind),
            name=name,
            qualified_name=qual,
            kind=kind,
            language="python",
            file_path=relative_path,
            line_start=start_line,
            line_end=end_line,
            byte_start=byte_start,
            byte_end=byte_end,
            signature=snippet_signature,
            metadata=metadata,
        )
        symbols.append(symbol)

    class Visitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            qual = ".".join(class_stack + [node.name]) if class_stack else node.name
            class_stack.append(node.name)
            append(
                node.name,
                qual,
                _class_symbol_kind(node.name, node.bases),
                node,
                metadata={"bases": [ast.unparse(base) for base in node.bases]},
            )
            self.generic_visit(node)
            class_stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            is_route = False
            methods = []
            for dec in node.decorator_list:
                parsed = _is_route_decorator(dec)
                if parsed:
                    is_route = True
                    _, method = parsed
                    methods.append(method)
            metadata = {
                "decorators": [ast.unparse(dec) for dec in node.decorator_list],
                "dependencies": [
                    _expr_to_name(arg.default)
                    for arg in node.args.defaults
                    if isinstance(arg, ast.Call) and _is_depends_expr(arg)
                ],
            }
            qual = ".".join(class_stack + [node.name]) if class_stack else node.name
            kind = "route" if is_route else ("method" if class_stack else "function")
            if methods:
                metadata["route_methods"] = methods
            append(
                node.name,
                qual,
                kind,
                node,
                metadata=metadata,
                signature=ast.unparse(node),
            )
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.visit_FunctionDef(node)

    Visitor().visit(tree)
    return symbols
