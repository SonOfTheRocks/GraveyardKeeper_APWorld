from __future__ import annotations

from ...tools.flow_analysis.parser import parse_graph
from ...tools.flow_analysis.values import ValueResolver, extract_options, option_index

from .helpers import FlowAnalysisTestCase, edge, node, stored, wrapper


def _answer_data(price=None, reward=None, lock=None):
    return {"$type": "AnswerData", "d_price": price or {}, "d_reward": reward or {}, "d_lock": lock or {}}


class TestFlowGraphValues(FlowAnalysisTestCase):
    def test_smart_res_resolves_legacy_display_port_names(self) -> None:
        graph = parse_graph(self.write_graph([
            wrapper(1, "Flow_SmartRes", {
                "Res type": stored("GameRes"),
                "Id": stored("rightful_citizen_paper"),
                "V": stored(1.0, "System.Single"),
                "res_type": stored("Item"),
            }),
        ], []))

        value = ValueResolver(graph).resolve_output("1", "Value")

        self.assertEqual("Item", value.resource_type)
        self.assertEqual("rightful_citizen_paper", value.resource_id)
        self.assertEqual(1.0, value.amount)

    def test_inline_item_and_create_item_outputs_resolve_item_ids(self) -> None:
        inline_item = {"$type": "Item", "id": "inline_reward", "value": 1}
        graph = parse_graph(self.write_graph([
            node(1, "Flow_DropItem", {"Item": inline_item, "Res_id": None, "Amount": stored(1)}),
            node(2, "Flow_CreateItem", {"item_id": stored("created_reward"), "value": stored(1)}),
            node(3, "Flow_DropItem", {"Item": None, "Res_id": None, "Amount": stored(1)}),
        ], [edge(2, "Value", 3, "Item", "Item")]))
        resolver = ValueResolver(graph)

        self.assertEqual("inline_reward", resolver.resolve_input("1", "Item").resource_id)
        self.assertEqual("created_reward", resolver.resolve_input("3", "Item").resource_id)

    def test_option_indices_are_numeric_and_ignore_connection_order(self) -> None:
        inputs = {f"<color=#A08030>#{index}</color>": _answer_data() for index in (10, 2, 1, 0)}
        multi = node(20, "Flow_MultiAnswer", inputs, answers=[f"phrase_{i}" for i in range(11)])
        nodes = [multi, node(30, "Flow_Talk"), node(31, "Flow_Talk"), node(32, "Flow_Talk"), node(40, "Flow_Talk")]
        edges = [edge(20, "out_10", 40, "In"), edge(20, "out_0", 30, "In"),
                 edge(20, "out_2", 32, "In"), edge(20, "out_1", 31, "In")]
        graph = parse_graph(self.write_graph(nodes, edges))
        options = extract_options(graph, ValueResolver(graph))

        self.assertEqual(10, option_index("<color=#A08030>#10</color>"))
        self.assertEqual(list(range(11)), [option.index for option in options])
        self.assertEqual(("40",), next(option for option in options if option.index == 10).target_nodes)

    def test_connected_answer_and_smartres_override_inline_defaults(self) -> None:
        inline_price = {"$type": "SmartRes", "id": stored("wrong"), "v": stored(99, "System.Int32")}
        multi = node(20, "Flow_MultiAnswer", {"#0": _answer_data(price=inline_price)}, answers=["@acid"])
        answer = wrapper(21, "Flow_Answer", {"price": {}, "lock": {}, "reward": {}})
        smart = wrapper(22, "Flow_SmartRes", {"res_type": stored("Item"), "id": stored("acid"), "v": stored(1.0)})
        graph = parse_graph(self.write_graph([multi, answer, smart], [
            edge(22, "Value", 21, "price", "SmartRes"), edge(21, "Value", 20, "#0", "AnswerData")]))
        option = extract_options(graph, ValueResolver(graph))[0]

        self.assertIsNotNone(option.answer)
        self.assertEqual("acid", option.answer.price.resource_id)
        self.assertEqual(1.0, option.answer.price.amount)

    def test_inline_answer_fields_remain_distinct(self) -> None:
        def smart(resource_id):
            return {"$type": "SmartRes", "res_type": stored("Item"), "id": stored(resource_id), "v": stored(1)}

        multi = node(20, "Flow_MultiAnswer", {
            "#0": _answer_data(smart("price"), smart("reward"), smart("lock"))}, answers=["phrase"])
        graph = parse_graph(self.write_graph([multi], []))
        option = extract_options(graph, ValueResolver(graph))[0]
        self.assertEqual("lock", option.answer.lock.resource_id)
        self.assertEqual("price", option.answer.price.resource_id)
        self.assertEqual("reward", option.answer.reward.resource_id)
