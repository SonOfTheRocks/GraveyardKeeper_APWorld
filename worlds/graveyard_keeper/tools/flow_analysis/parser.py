from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .model import Edge, Graph, Node


class FlowGraphParseError(ValueError):
    pass


_GENERIC_TYPE = re.compile(r"`\d+\[\[([^,\]]+)")


def normalize_type(raw_type: str | None) -> str:
    raw_type = raw_type or "Unknown"
    match = _GENERIC_TYPE.search(raw_type)
    selected = match.group(1) if match else raw_type
    return selected.rsplit(".", 1)[-1]


def unwrap_content(value: Any) -> Any:
    if isinstance(value, dict) and "$content" in value:
        return value["$content"]
    return value


def _ref(value: Any) -> str | None:
    if isinstance(value, dict) and value.get("$ref") is not None:
        return str(value["$ref"])
    return None


def parse_graph(path: str | Path) -> Graph:
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise FlowGraphParseError(f"{source}: {error}") from error
    compatibility_diagnostic: str | None = None
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        if "Invalid control character" not in error.msg:
            raise FlowGraphParseError(f"{source}: {error}") from error
        try:
            # Unity's exporter emits literal control characters inside a few string
            # fields. strict=False preserves those characters; unlike the old HTML
            # script, this does not delete or alter arbitrary bytes before parsing.
            raw = json.loads(text, strict=False)
        except json.JSONDecodeError as compatibility_error:
            raise FlowGraphParseError(f"{source}: {compatibility_error}") from compatibility_error
        controls = sorted({ord(character) for character in text if ord(character) < 0x20 and character not in "\r\n\t"})
        compatibility_diagnostic = (
            "accepted unescaped control characters inside JSON strings "
            f"({', '.join(f'U+{value:04X}' for value in controls) or 'unknown code point'})"
        )
    if not isinstance(raw, dict):
        raise FlowGraphParseError(f"{source}: top-level JSON value must be an object")

    diagnostics: list[str] = [compatibility_diagnostic] if compatibility_diagnostic else []
    nodes: dict[str, Node] = {}
    for raw_node in raw.get("nodes", []):
        if not isinstance(raw_node, dict) or raw_node.get("$id") is None:
            diagnostics.append("node without $id ignored")
            continue
        node_id = str(raw_node["$id"])
        if node_id in nodes:
            diagnostics.append(f"duplicate node id {node_id}; later node ignored")
            continue
        raw_type = str(raw_node.get("$type", "Unknown"))
        inputs = raw_node.get("_inputPortValues")
        nodes[node_id] = Node(
            id=node_id,
            type_name=normalize_type(raw_type),
            raw_type=raw_type,
            inputs=inputs if isinstance(inputs, dict) else {},
            raw=raw_node,
        )

    edges: list[Edge] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    duplicates = 0
    for raw_edge in raw.get("connections", []):
        if not isinstance(raw_edge, dict):
            diagnostics.append("non-object connection ignored")
            continue
        source_id = _ref(raw_edge.get("_sourceNode"))
        target_id = _ref(raw_edge.get("_targetNode"))
        if source_id is None or target_id is None:
            diagnostics.append("connection without source/target $ref ignored")
            continue
        raw_type = str(raw_edge.get("$type", ""))
        edge = Edge(
            source=source_id,
            source_port=str(raw_edge.get("_sourcePortName") or ""),
            target=target_id,
            target_port=str(raw_edge.get("_targetPortName") or ""),
            raw_type=raw_type,
            kind="data" if "BinderConnection`" in raw_type else "flow",
        )
        if edge.key in seen:
            duplicates += 1
            continue
        seen.add(edge.key)
        if source_id not in nodes or target_id not in nodes:
            diagnostics.append(
                f"connection {source_id}.{edge.source_port} -> {target_id}.{edge.target_port} has invalid $ref"
            )
            continue
        edges.append(edge)

    # FlowCanvas serializes local custom-function calls by UID rather than as ordinary
    # connections. Materialize only the call edge. The summary path evaluator interprets
    # Return with a call stack; adding global Return edges here would mix different callers.
    uid_targets = {
        str(node.raw["_UID"]): node.id
        for node in nodes.values()
        if node.type_name in {"CustomFunctionEvent", "Flow_CustomFunctionEvent"} and node.raw.get("_UID")
    }
    for node in nodes.values():
        if node.type_name != "CustomFunctionCall" or not node.raw.get("_sourceOutputUID"):
            continue
        target_id = uid_targets.get(str(node.raw["_sourceOutputUID"]))
        if target_id is None:
            diagnostics.append(f"custom function call {node.id} has unresolved UID {node.raw['_sourceOutputUID']}")
            continue
        call_edge = Edge(node.id, "call", target_id, "invoke", "Synthetic.CustomFunctionCall", "flow")
        if call_edge.key not in seen:
            seen.add(call_edge.key)
            edges.append(call_edge)

    graph = Graph(source.stem, source, nodes, edges, diagnostics, duplicates)
    for node_id in nodes:
        graph.incoming_flow[node_id] = []
        graph.outgoing_flow[node_id] = []
    for edge in edges:
        if edge.kind == "flow":
            graph.incoming_flow[edge.target].append(edge)
            graph.outgoing_flow[edge.source].append(edge)
        else:
            graph.incoming_data.setdefault((edge.target, edge.target_port), []).append(edge)
            graph.outgoing_data.setdefault((edge.source, edge.source_port), []).append(edge)
    for collection in (*graph.incoming_flow.values(), *graph.outgoing_flow.values(),
                       *graph.incoming_data.values(), *graph.outgoing_data.values()):
        collection.sort(key=lambda edge: (edge.source, edge.source_port, edge.target, edge.target_port))
    return graph
