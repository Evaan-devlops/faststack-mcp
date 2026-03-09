from __future__ import annotations

import configparser
import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

from ..models import Symbol
from . import make_symbol_id

KNOWN_JS_CONFIG_KEYS = {
    "scripts",
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
    "lint",
    "test",
}

VITE_KEYS = {
    "plugins",
    "build",
    "server",
    "resolve",
    "root",
    "base",
}

TAILWIND_KEYS = {
    "content",
    "theme",
    "plugins",
    "safelist",
    "presets",
}

ESLINT_KEYS = {
    "env",
    "extends",
    "plugins",
    "rules",
    "parserOptions",
}


def _symbol_for_key(file_path: Path, name: str, kind: str, signature: str, metadata: dict | None = None) -> Symbol:
    merged_metadata = {"parser": "config_parser"}
    if metadata:
        merged_metadata.update(metadata)
    return Symbol(
        id=make_symbol_id(file_path.as_posix(), name, kind),
        name=name,
        qualified_name=name,
        kind=kind,
        language="config",
        file_path=file_path.as_posix(),
        line_start=1,
        line_end=1,
        byte_start=0,
        byte_end=0,
        signature=signature,
        metadata=merged_metadata,
    )


def _package_dependencies(path: Path, payload: dict[str, object]) -> list[Symbol]:
    symbols: list[Symbol] = []
    deps = set()
    for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        values = payload.get(section)
        if isinstance(values, dict):
            deps.update(values.keys())
    for dep in sorted(deps):
        if dep == "":
            continue
        symbol = _symbol_for_key(
            path,
            f"package_dep_{dep}",
            "package_dependency",
            f"package dependency: {dep}",
            {"dependency": dep, "kind": "dependency"},
        )
        symbols.append(symbol)
    scripts = payload.get("scripts")
    if isinstance(scripts, dict):
        for script in sorted(scripts):
            symbols.append(
                _symbol_for_key(
                    path,
                    f"npm_script_{script}",
                    "package_script",
                    f"package script: {script}",
                    {"script": script},
                )
            )
    return symbols


def _pyproject_dependency_names(payload: dict[str, object]) -> list[str]:
    names: list[str] = []
    project = payload.get("project")
    if isinstance(project, dict):
        project_dependencies = project.get("dependencies")
        if isinstance(project_dependencies, list):
            for item in project_dependencies:
                if isinstance(item, str):
                    names.append(item.split(",", 1)[0].strip())
        if isinstance(project_dependencies, dict):
            names.extend(project_dependencies.keys())

    tool = payload.get("tool")
    if isinstance(tool, dict):
        poetry = tool.get("poetry")
        if isinstance(poetry, dict):
            deps = poetry.get("dependencies")
            if isinstance(deps, dict):
                names.extend(deps.keys())
            dev_deps = poetry.get("group")
            if isinstance(dev_deps, dict):
                for group in dev_deps.values():
                    if isinstance(group, dict):
                        deps = group.get("dependencies")
                        if isinstance(deps, dict):
                            names.extend(deps.keys())
    return sorted(set(name for name in names if name and not name.startswith("python")))


def _parse_json_config_root(path: Path, payload: dict[str, object], symbols: list[Symbol], marker: str) -> None:
    symbol = _symbol_for_key(
        path,
        marker,
        "config_root",
        "configuration file root keys",
        {
            "keys": sorted(k for k in payload.keys() if isinstance(k, str)),
            "type": "json",
            "marker": marker,
        },
    )
    symbols.append(symbol)

    for key in KNOWN_JS_CONFIG_KEYS:
        if key in payload:
            symbols.append(
                _symbol_for_key(
                    path,
                    f"config_{marker}_{key}",
                    "config_key",
                    f"configuration key: {key}",
                    {"config_key": key, "type": marker},
                )
            )


def _parse_vite(path: Path, source: str, symbols: list[Symbol]) -> None:
    lower = source.lower()
    if "defineconfig" in lower:
        symbols.append(
            _symbol_for_key(
                path,
                "vite_define_config",
                "vite_config",
                "vite config entrypoint",
                {"config_type": "vite"},
            )
        )
    for key in VITE_KEYS:
        if key in lower:
            symbols.append(
                _symbol_for_key(
                    path,
                    f"vite_{key}",
                    "vite_config",
                    f"vite config key: {key}",
                    {"config_key": key},
                )
            )


def _parse_eslint(path: Path, source: str, symbols: list[Symbol]) -> None:
    lower = source.lower()
    if "export default" in lower or "module.exports" in lower:
        symbols.append(
            _symbol_for_key(
                path,
                "eslint_config_entry",
                "eslint_config",
                "eslint config entrypoint",
                {"config_type": "eslint"},
            )
        )
    for key in ESLINT_KEYS:
        if key in lower:
            symbols.append(
                _symbol_for_key(
                    path,
                    f"eslint_{key}",
                    "eslint_config",
                    f"eslint config key: {key}",
                    {"config_key": key},
                )
            )


def _parse_tailwind(path: Path, source: str, symbols: list[Symbol]) -> None:
    lower = source.lower()
    symbols.append(
        _symbol_for_key(
            path,
            "tailwind_config",
            "tailwind_config",
            "tailwind config",
            {"config_type": "tailwind"},
        )
    )
    for key in TAILWIND_KEYS:
        if key in lower:
            symbols.append(
                _symbol_for_key(
                    path,
                    f"tailwind_{key}",
                    "tailwind_config",
                    f"tailwind key: {key}",
                    {"config_key": key},
                )
            )


def _parse_toml(path: Path, source: str, symbols: list[Symbol]) -> None:
    if tomllib is None:
        return
    try:
        payload = tomllib.loads(source)
    except Exception:
        return
    if not isinstance(payload, dict):
        return
    symbols.append(
        _symbol_for_key(
            path,
            "toml_root",
            "toml_config",
            "toml root keys",
            {"keys": sorted(payload.keys())},
        )
    )
    for key in payload:
        if isinstance(key, str):
            symbols.append(_symbol_for_key(path, f"toml_key_{key}", "config_key", f"toml key: {key}", {"key": key}))

    if path.name.lower() == "pyproject.toml":
        for dep in _pyproject_dependency_names(payload):
            symbols.append(
                _symbol_for_key(
                    path,
                    f"pyproject_dep_{dep}",
                    "pyproject_dependency",
                    f"dependency: {dep}",
                    {"dependency": dep, "kind": "pyproject"},
                )
            )


def _parse_ini(path: Path, source: str, symbols: list[Symbol]) -> None:
    parser = configparser.ConfigParser()
    try:
        parser.read_string(source)
    except Exception:
        return
    sections = parser.sections()
    symbols.append(_symbol_for_key(path, "ini_sections", "ini_config", "ini sections", {"sections": sections}))
    for section in sections:
        for key in parser[section]:
            symbols.append(_symbol_for_key(path, f"ini_{section}_{key}", "ini_key", f"ini key: {section}.{key}", {"section": section, "key": key}))


def _parse_yaml(path: Path, source: str, symbols: list[Symbol]) -> None:
    top: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(("#", "-", "{")) and ":" in stripped:
            key = stripped.split(":", 1)[0].strip()
            if key and key not in top:
                top.append(key)
    if top:
        symbols.append(_symbol_for_key(path, "yaml_root", "yaml_config", "yaml top-level keys", {"keys": top}))
        for key in top:
            symbols.append(_symbol_for_key(path, f"yaml_key_{key}", "config_key", f"yaml key: {key}", {"key": key}))


def parse_file(file_path: Path, source: str) -> list[Symbol]:
    name = file_path.name.lower()
    symbols: list[Symbol] = []

    if name == "manifest.json":
        return symbols

    if name == "package.json":
        try:
            payload = json.loads(source)
        except json.JSONDecodeError:
            return symbols
        if isinstance(payload, dict):
            _parse_json_config_root(file_path, payload, symbols, "package")
            symbols.extend(_package_dependencies(file_path, payload))
        return symbols

    if name in {"tailwind.config.js", "tailwind.config.ts"}:
        _parse_tailwind(file_path, source, symbols)
        return symbols

    if name == "pyproject.toml":
        _parse_toml(file_path, source, symbols)
        return symbols

    if name == "vite.config.js" or name.startswith("vite.config"):
        _parse_vite(file_path, source, symbols)
        return symbols

    if name == "eslint.config.js":
        _parse_eslint(file_path, source, symbols)
        return symbols

    if name == "alembic.ini":
        _parse_ini(file_path, source, symbols)
        return symbols

    if name.startswith("tsconfig") and name.endswith(".json"):
        try:
            payload = json.loads(source)
            if isinstance(payload, dict):
                _parse_json_config_root(file_path, payload, symbols, "tsconfig")
                if "compilerOptions" in payload:
                    symbols.append(
                        _symbol_for_key(
                            file_path,
                            "tsconfig_compiler_options",
                            "tsconfig",
                            "tsconfig compiler options",
                            {"compiler_option_count": len(payload.get("compilerOptions", {}))},
                        )
                    )
        except json.JSONDecodeError:
            pass
        return symbols

    suffix = file_path.suffix.lower()
    if suffix == ".toml":
        _parse_toml(file_path, source, symbols)
        return symbols
    if suffix in {".ini"}:
        _parse_ini(file_path, source, symbols)
        return symbols
    if suffix in {".yaml", ".yml"}:
        _parse_yaml(file_path, source, symbols)
        return symbols

    return symbols
