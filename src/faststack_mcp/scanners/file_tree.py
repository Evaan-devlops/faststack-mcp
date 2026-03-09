from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Node:
    name: str
    path: str
    kind: str
    children: dict[str, "_Node"] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "name": self.name,
            "path": self.path,
            "type": self.kind,
        }
        if self.children:
            payload["children"] = [
                child.to_dict()
                for child in sorted(self.children.values(), key=lambda node: (node.kind == "file", node.name))
            ]
        return payload


def build_tree(file_paths: list[str]) -> list[dict[str, object]]:
    root: dict[str, _Node] = {}

    for path in sorted(file_paths):
        parts = [part for part in path.split("/") if part]
        current = root
        accum: list[str] = []
        for i, part in enumerate(parts):
            accum.append(part)
            node_path = "/".join(accum)
            kind = "directory" if i < len(parts) - 1 else "file"
            if part not in current:
                current[part] = _Node(name=part, path=node_path, kind=kind)
            node = current[part]
            if i < len(parts) - 1:
                if node.kind == "file":
                    node.kind = "directory"
                current = node.children
            elif node.kind != "file":
                node.kind = "file"

    return [
        node.to_dict()
        for node in sorted(root.values(), key=lambda n: (n.kind == "file", n.name))
    ]
