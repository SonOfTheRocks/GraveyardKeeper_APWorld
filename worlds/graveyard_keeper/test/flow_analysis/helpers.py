from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any


def node(node_id: int | str, node_type: str, inputs: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    return {"$id": node_id, "$type": f"FlowCanvas.Nodes.{node_type}", "_inputPortValues": inputs or {}, **extra}


def wrapper(node_id: int | str, inner_type: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    return node(node_id, f"SimplexNodeWrapper`1[[FlowCanvas.Nodes.{inner_type}, Assembly-CSharp]]", inputs)


def stored(value: Any, value_type: str = "System.String") -> dict[str, Any]:
    return {"$content": value, "$type": value_type}


def edge(source: int | str, source_port: str, target: int | str, target_port: str,
         data_type: str | None = None) -> dict[str, Any]:
    connection_type = "FlowCanvas.BinderConnection"
    if data_type:
        connection_type += f"`1[[{data_type}, Assembly-CSharp]]"
    return {"$type": connection_type, "_sourceNode": {"$ref": source}, "_sourcePortName": source_port,
            "_targetNode": {"$ref": target}, "_targetPortName": target_port}


class FlowAnalysisTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory(prefix="graveyard_keeper_flow_analysis_")
        self.addCleanup(self._temporary_directory.cleanup)
        self.temporary_path = Path(self._temporary_directory.name)

    def write_graph(self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]], name: str = "fixture") -> Path:
        path = self.temporary_path / f"{name}.json"
        path.write_text(json.dumps({"nodes": nodes, "connections": edges}), encoding="utf-8")
        return path
