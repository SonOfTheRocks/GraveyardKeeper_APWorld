from __future__ import annotations

from ...tools.flow_analysis.analysis import AnalysisLimits, analyze_graph
from ...tools.flow_analysis.parser import parse_graph

from .helpers import FlowAnalysisTestCase, edge, node, stored, wrapper


class TestFlowGraphAnalysis(FlowAnalysisTestCase):
    def test_direct_item_and_positive_relation_are_found_but_negative_is_not(self) -> None:
        nodes = [node(1, "CustomEvent"),
                 node(2, "Flow_DropItem", {"Res_id": stored("quest_key"), "Amount": stored(1)}),
                 node(3, "Flow_AddRelation", {"npc_id": stored("astrologer"), "Value": stored(10.0)}),
                 node(4, "Flow_AddRelation", {"npc_id": stored("astrologer"), "Value": stored(-5.0)})]
        graph = parse_graph(self.write_graph(nodes, [
            edge(1, "Out", 2, "In"), edge(2, "Out", 3, "In"), edge(3, "Out", 4, "In")]))
        analysis = analyze_graph(graph)
        self.assertEqual([("item", "quest_key", 1), ("relation", "_rel", 10.0)], [
            (finding.kind, finding.resource_id, finding.amount) for finding in analysis.findings])

    def test_drop_item_uses_runtime_default_amount_one_when_port_is_omitted(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "CustomEvent"),
            node(2, "Flow_DropItem", {"Res_id": stored("quest_key")}),
        ], [edge(1, "Out", 2, "In")]))

        finding = analyze_graph(graph).findings[0]

        self.assertEqual(1, finding.amount)
        self.assertNotIn("Menge konnte nicht aufgelöst werden", finding.issues)

    def test_drop_item_falls_back_to_res_id_when_serialized_item_has_no_id(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "CustomEvent"),
            node(2, "Flow_DropItem", {
                "Item": {"$type": "Item", "value": 1},
                "Res_id": stored("souls_zone_key"),
                "Amount": stored(1),
            }),
        ], [edge(1, "Out", 2, "In")]))

        finding = analyze_graph(graph).findings[0]

        self.assertEqual("souls_zone_key", finding.resource_id)
        self.assertFalse(finding.issues)

    def test_flag_branches_remain_or_alternatives_and_setter_is_an_effect(self) -> None:
        nodes = [node(1, "CustomEvent", eventName={"_value": "a"}),
                 node(2, "CustomEvent", eventName={"_value": "b"}),
                 node(3, "Flow_ParamFlag", {"param": stored("quest_started")}),
                 node(4, "Flow_SetPlayerParam", {"Param name": stored("prepared"), "Value": stored(1)}),
                 node(5, "Flow_DropItem", {"Res_id": stored("reward"), "Amount": stored(1)})]
        edges = [edge(1, "Out", 3, "In"), edge(3, ">= 1", 4, "In"), edge(4, "Out", 5, "In"),
                 edge(2, "Out", 3, "In"), edge(3, "== 0", 5, "In")]
        finding = analyze_graph(parse_graph(self.write_graph(nodes, edges))).findings[0]

        self.assertEqual(4, len(finding.paths))
        self.assertEqual({">= 1", "== 0"}, {
            path.conditions[0].text.rsplit(" -> ", 1)[1] for path in finding.paths})
        self.assertEqual(2, sum(
            any("Flow_SetPlayerParam" in effect.text for effect in path.effects) for path in finding.paths))

    def test_answer_relation_reward_is_attached_to_selected_option_with_price(self) -> None:
        nodes = [node(1, "CustomEvent"),
                 node(2, "Flow_MultiAnswer", {"#0": {"$type": "AnswerData"}}, answers=["@acid"]),
                 wrapper(3, "Flow_Answer", {"price": {}, "lock": {}, "reward": {}}),
                 wrapper(4, "Flow_SmartRes", {"res_type": stored("Item"), "id": stored("acid"), "v": stored(1.0)}),
                 wrapper(5, "Flow_SmartRes", {"res_type": stored("GameRes"), "id": stored("_rel"), "v": stored(10.0)}),
                 node(6, "Flow_Talk")]
        edges = [edge(1, "Out", 2, "In"), edge(2, "out_0", 6, "In"),
                 edge(4, "Value", 3, "price", "SmartRes"), edge(5, "Value", 3, "reward", "SmartRes"),
                 edge(3, "Value", 2, "#0", "AnswerData")]
        finding = analyze_graph(parse_graph(self.write_graph(nodes, edges))).findings[0]

        self.assertEqual("@acid", finding.option.phrase)
        self.assertEqual(10.0, finding.amount)
        self.assertFalse(finding.paths[0].costs)
        self.assertIn("Item acid x1 erforderlich", [
            condition.text for condition in finding.paths[0].conditions])
        self.assertIn("2.out_0 -> 6.In", finding.paths[0].evidence)

    def test_unknown_branch_and_limit_make_result_partial(self) -> None:
        nodes = [node(1, "CustomEvent"), node(2, "MysteryBranch"),
                 node(3, "Flow_DropItem", {"Res_id": stored("reward"), "Amount": stored(1)}), node(4, "Flow_Talk")]
        edges = [edge(1, "Out", 2, "In"), edge(2, "A", 3, "In"), edge(2, "B", 4, "In")]
        finding = analyze_graph(parse_graph(self.write_graph(nodes, edges)), AnalysisLimits(max_paths=1)).findings[0]
        self.assertEqual("teilweise analysiert", finding.status)
        self.assertTrue(any("unbekannter verzweigender" in reason for reason in finding.paths[0].incomplete_reasons))
        self.assertTrue(any("path limit" in issue for issue in finding.issues))

    def test_loop_terminates_and_is_disclosed(self) -> None:
        nodes = [node(1, "CustomEvent"), node(2, "Flow_Talk"),
                 node(3, "Flow_DropItem", {"Res_id": stored("reward"), "Amount": stored(1)})]
        edges = [edge(1, "Out", 2, "In"), edge(2, "Again", 2, "In"), edge(2, "Done", 3, "In")]
        finding = analyze_graph(parse_graph(self.write_graph(nodes, edges))).findings[0]
        self.assertEqual(1, len(finding.paths))

    def test_setter_before_flag_satisfies_check_on_path(self) -> None:
        nodes = [node(1, "CustomEvent"),
                 node(2, "Flow_SetPlayerParam", {"Param name": stored("ready"), "Value": stored(1)}),
                 node(3, "Flow_ParamFlag", {"param": stored("ready")}),
                 node(4, "Flow_DropItem", {"Res_id": stored("reward"), "Amount": stored(1)})]
        finding = analyze_graph(parse_graph(self.write_graph(nodes, [
            edge(1, "Out", 2, "In"), edge(2, "Out", 3, "In"), edge(3, ">= 1", 4, "In")]))).findings[0]
        self.assertFalse(finding.paths[0].conditions)
        self.assertTrue(any("Pfadinterner Zustand erfüllt" in effect.text for effect in finding.paths[0].effects))

    def test_player_param_compare_variants_use_the_node_threshold(self) -> None:
        for node_type, port, stored_value, threshold in (
            ("Flow_PlayerParamCompare", "!=", 1.0, 0.0),
            ("Flow_PlayerParamCompareInt", "==", 2, 2),
        ):
            with self.subTest(node_type=node_type):
                nodes = [
                    node(1, "CustomEvent"),
                    node(2, "Flow_SetPlayerParam", {
                        "Param name": stored("quest_progress"), "Value": stored(stored_value)}),
                    node(3, node_type, {
                        "param": stored("quest_progress"), "value": stored(threshold)}),
                    node(4, "Flow_DropItem", {"Res_id": stored("reward"), "Amount": stored(1)}),
                ]
                analysis = analyze_graph(parse_graph(self.write_graph(nodes, [
                    edge(1, "Out", 2, "In"), edge(2, "Out", 3, "In"),
                    edge(3, port, 4, "In"),
                ])))
                finding = analysis.findings[0]

                self.assertNotIn(node_type, analysis.unsupported_types)
                self.assertFalse(finding.paths[0].conditions)
                self.assertTrue(any(
                    "Pfadinterner Zustand erfüllt" in effect.text
                    and f"{port} {threshold:g}" in effect.text
                    for effect in finding.paths[0].effects
                ))
                self.assertFalse(any(
                    f"unbekannter verzweigender Node-Typ {node_type}" in reason
                    for reason in finding.paths[0].incomplete_reasons
                ))

    def test_relation_delta_adjusts_later_entry_requirement(self) -> None:
        nodes = [node(1, "CustomEvent"),
                 node(2, "Flow_AddRelation", {"npc_id": stored("snake"), "Value": stored(10.0)}),
                 node(3, "Flow_CompareRelation", {"npc_id": stored("snake"), "Value": stored(20.0)}),
                 node(4, "Flow_DropItem", {"Res_id": stored("reward"), "Amount": stored(1)})]
        finding = analyze_graph(parse_graph(self.write_graph(nodes, [
            edge(1, "Out", 2, "In"), edge(2, "Out", 3, "In"), edge(3, ">=", 4, "In")]))).findings[1]
        self.assertIn("Einstiegswert >= 10", finding.paths[0].conditions[0].text)
        self.assertIn("Delta +10", finding.paths[0].conditions[0].text)

    def test_item_removal_is_both_availability_condition_and_cost(self) -> None:
        nodes = [node(1, "CustomEvent"),
                 node(2, "Flow_RemoveItemFromInventory", {"Item ID": stored("acid"), "Items Count": stored(2)}),
                 node(3, "Flow_DropItem", {"Res_id": stored("reward"), "Amount": stored(1)})]
        finding = analyze_graph(parse_graph(self.write_graph(nodes, [
            edge(1, "Out", 2, "In"), edge(2, "Out", 3, "In")]))).findings[0]
        self.assertFalse(finding.paths[0].costs)
        self.assertEqual("Item acid x2 erforderlich", finding.paths[0].conditions[0].text)

    def test_inventory_check_yes_requires_item_and_no_is_unconditional(self) -> None:
        nodes = [
            node(1, "CustomEvent"),
            node(2, "Flow_CreateItem", {
                "item_id": stored("apple"), "value": stored(5.0, "System.Single")}),
            node(3, "Flow_HasItemInInventory", {"Item": None, "Item ID": stored(None)}),
            node(4, "Flow_DropItem", {"Res_id": stored("reward"), "Amount": stored(1)}),
        ]
        graph = parse_graph(self.write_graph(nodes, [
            edge(1, "Out", 3, "In"),
            edge(2, "Value", 3, "Item", "Item"),
            edge(3, "Yes", 4, "In"), edge(3, "No", 4, "In"),
        ]))
        analysis = analyze_graph(graph)
        finding = analysis.findings[0]

        self.assertNotIn("Flow_HasItemInInventory", analysis.unsupported_types)
        self.assertEqual([0, 1], sorted(len(path.conditions) for path in finding.paths))
        condition = next(path.conditions[0] for path in finding.paths if path.conditions)
        self.assertEqual("Item apple x5 im Inventar erforderlich", condition.text)
        self.assertFalse(any(
            "unbekannter verzweigender Node-Typ Flow_HasItemInInventory" in reason
            for path in finding.paths for reason in path.incomplete_reasons
        ))

    def test_split_and_goto_are_known_flow_nodes(self) -> None:
        nodes = [
            node(1, "CustomEvent"), node(2, "Flow_GoTo"), node(3, "Split"),
            node(4, "Flow_DropItem", {"Res_id": stored("reward"), "Amount": stored(1)}),
            node(5, "Flow_Talk"),
        ]
        finding = analyze_graph(parse_graph(self.write_graph(nodes, [
            edge(1, "Out", 2, "In"), edge(2, "Came to dest", 3, "In"),
            edge(3, "0", 4, "In"), edge(3, "1", 5, "In"),
        ]))).findings[0]

        self.assertFalse(any(
            "unbekannter verzweigender Node-Typ" in reason
            for path in finding.paths for reason in path.incomplete_reasons
        ))

    def test_random_flow_is_a_known_chance_condition(self) -> None:
        nodes = [
            node(1, "CustomEvent"),
            node(2, "Flow_RendomFlow", {"chance": stored(0.7, "System.Single")}),
            node(3, "Flow_DropItem", {"Res_id": stored("reward"), "Amount": stored(1)}),
            node(4, "Flow_Talk"),
        ]
        analysis = analyze_graph(parse_graph(self.write_graph(nodes, [
            edge(1, "Out", 2, "In"), edge(2, "true", 3, "In"), edge(2, "false", 4, "In"),
        ])))
        finding = analysis.findings[0]

        self.assertNotIn("Flow_RendomFlow", analysis.unsupported_types)
        self.assertEqual("Zufallsausgang true (70% für true)", finding.paths[0].conditions[0].text)
        self.assertFalse(any(
            "unbekannter verzweigender Node-Typ Flow_RendomFlow" in reason
            for path in finding.paths for reason in path.incomplete_reasons
        ))

    def test_create_item_supplies_drop_item_identity_and_amount(self) -> None:
        nodes = [
            node(1, "CustomEvent"),
            node(2, "Flow_CreateItem", {"item_id": stored("quest_item"), "value": stored(3)}),
            node(3, "Flow_DropItem", {
                "Res_id": stored("ignored_default"), "Item": None, "Amount": stored(1)}),
        ]
        analysis = analyze_graph(parse_graph(self.write_graph(nodes, [
            edge(1, "Out", 3, "In"), edge(2, "Value", 3, "Item", "Item"),
        ])))

        self.assertEqual([("quest_item", 3)], [
            (finding.resource_id, finding.amount) for finding in analysis.findings
        ])
