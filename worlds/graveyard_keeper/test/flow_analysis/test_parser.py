from __future__ import annotations

from ...tools.flow_analysis.parser import FlowGraphParseError, normalize_type, parse_graph

from .helpers import FlowAnalysisTestCase, edge, node, stored, wrapper


class TestFlowGraphParser(FlowAnalysisTestCase):
    def test_normalizes_wrapper_separates_edges_and_deduplicates(self) -> None:
        nodes = [node(1, "CustomEvent"), wrapper(2, "Flow_SmartRes", {"id": stored("acid")}),
                 node(3, "Flow_DropItem")]
        flow = edge(1, "Out", 3, "In")
        data = edge(2, "Value", 3, "Item", "SmartRes")
        graph = parse_graph(self.write_graph(nodes, [flow, flow, data]))

        self.assertEqual("Flow_SmartRes", normalize_type(nodes[1]["$type"]))
        self.assertEqual(1, graph.duplicate_edges)
        self.assertEqual([graph.edges[0]], graph.outgoing_flow["1"])
        self.assertEqual("data", graph.incoming_data[("3", "Item")][0].kind)

    def test_invalid_reference_is_diagnosed(self) -> None:
        graph = parse_graph(self.write_graph([node(1, "CustomEvent")], [edge(1, "Out", 999, "In")]))
        self.assertFalse(graph.edges)
        self.assertIn("invalid $ref", graph.diagnostics[0])

    def test_custom_function_uid_becomes_a_synthetic_call_edge(self) -> None:
        call = node(1, "CustomFunctionCall", _sourceOutputUID="function-uid")
        event = node(2, "CustomFunctionEvent", _UID="function-uid", identifier="work")
        graph = parse_graph(self.write_graph([call, event], []))
        self.assertEqual([("1", "call", "2", "invoke")], [
            (entry.source, entry.source_port, entry.target, entry.target_port) for entry in graph.edges])

    def test_exporter_control_character_is_preserved_and_diagnosed(self) -> None:
        path = self.temporary_path / "compatible.json"
        path.write_bytes(b'{"nodes": [], "comment": "bad\x01value"}')
        graph = parse_graph(path)
        self.assertEqual(["accepted unescaped control characters inside JSON strings (U+0001)"], graph.diagnostics)

    def test_other_malformed_json_is_not_silently_cleaned(self) -> None:
        path = self.temporary_path / "bad.json"
        path.write_text('{"nodes": [}', encoding="utf-8")
        with self.assertRaises(FlowGraphParseError):
            parse_graph(path)
