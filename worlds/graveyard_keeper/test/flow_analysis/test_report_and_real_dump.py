from __future__ import annotations

import json
from pathlib import Path

from ...tools.flow_analysis.analysis import analyze_graph
from ...tools.flow_analysis.graph_report import (
    build_game_data_script_index, build_quest_graph_data, load_quest_node_names,
    render_quest_graph_html,
)
from ...tools.flow_analysis.mapping import APWorldIndex
from ...tools.flow_analysis.parser import parse_graph
from ...tools.flow_analysis.report import render_graph, render_readme
from ...tools.flow_analysis.summaries import build_phrase_unlock_index, build_quest_summaries
from ...tools.flow_analysis.values import ValueResolver, extract_options

from .helpers import FlowAnalysisTestCase, edge, node, stored, wrapper


COMPANION_DUMP = Path(
    r"C:\Users\Kai\RiderProjects\GraveyardKeepelago\GraveyardKeepelago\Dumps\FlowGraphExports\npc_astrologer.json"
)
ACTRESS_DUMP = COMPANION_DUMP.with_name("npc_actress.json")
CULTIST_DUMP = COMPANION_DUMP.with_name("npc_cultist.json")
TAVERN_SKULL_DUMP = COMPANION_DUMP.with_name("tavern_skull.json")
TAVERN_OWNER_DUMP = COMPANION_DUMP.with_name("npc_tavern owner.json")
INQUISITOR_DUMP = COMPANION_DUMP.with_name("npc_inquisitor.json")
GYPSY_DUMP = COMPANION_DUMP.with_name("npc_gypsy.json")
BISHOP_DUMP = COMPANION_DUMP.with_name("npc_bishop.json")
CRAFTING_SKULL_DUMP = COMPANION_DUMP.with_name("crafting_skull_3.json")
QUEST_NODE_NAMES = Path(__file__).parents[2] / "data" / "quest_node_names.json"


class TestFlowGraphReports(FlowAnalysisTestCase):
    def test_real_curated_node_names_are_valid_analyzer_data(self) -> None:
        raw_names = json.loads(QUEST_NODE_NAMES.read_text(encoding="utf-8-sig"))
        loaded_names = load_quest_node_names(QUEST_NODE_NAMES)

        self.assertIsInstance(raw_names, dict)
        self.assertTrue(raw_names)
        self.assertEqual(raw_names.keys(), loaded_names.keys())
        for node_id, display_name in loaded_names.items():
            with self.subTest(node_id=node_id):
                self.assertTrue(node_id.strip())
                self.assertEqual(node_id, node_id.strip())
                self.assertEqual(display_name, display_name.strip())

    def test_curated_node_name_replaces_label_but_preserves_technical_name(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": None}, answers=["technical_phrase"]),
            node(2, "Flow_AddRelation", {"Value": stored(10.0, "System.Single")}),
        ], [edge(1, "out_0", 2, "In")]))
        names_path = self.temporary_path / "quest_node_names.json"
        names_path.write_text(json.dumps({
            "fixture:1:option:0": "Tell the Astrologer what happened",
            "ignored-empty-name": "   ",
        }), encoding="utf-8")

        names = load_quest_node_names(names_path)
        data = build_quest_graph_data([analyze_graph(graph)], node_names=names)
        finding = next(value for value in data["nodes"] if value["id"] == "fixture:1:option:0")
        details = data["details"][finding["id"]]

        self.assertEqual("Tell the Astrologer what happened", finding["label"])
        self.assertEqual("Tell the Astrologer what happened", details["displayName"])
        self.assertEqual("technical_phrase", details["technicalName"])
        self.assertIn("Original node name: technical_phrase", finding["title"])
        self.assertIn("tell the astrologer what happened", finding["search"])
        self.assertNotIn("ignored-empty-name", names)
        rendered = render_quest_graph_html(data)
        self.assertIn("Original node name:", rendered)
        self.assertIn("Stable node ID:", rendered)

    def test_content_pack_classification_uses_quest_identifiers(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {
                "#0": None, "#1": None, "#2": None, "#3": None, "#4": None,
            }, answers=[
                "base_quest", "souls_s_test", "refugee_test", "tr_quest_8", "gerry_before_17cs_1",
            ]),
            node(2, "Flow_AddRelation", {"Value": stored(1.0, "System.Single")}),
            node(3, "Flow_AddRelation", {"Value": stored(1.0, "System.Single")}),
            node(4, "Flow_AddRelation", {"Value": stored(1.0, "System.Single")}),
            node(5, "Flow_AddRelation", {"Value": stored(1.0, "System.Single")}),
            node(6, "Flow_AddRelation", {"Value": stored(1.0, "System.Single")}),
        ], [edge(1, f"out_{index}", index + 2, "In") for index in range(5)]))
        data = build_quest_graph_data([analyze_graph(graph)])

        self.assertEqual("Base Game", data["details"]["fixture:1:option:0"]["contentPack"])
        self.assertEqual("Better Call Soul", data["details"]["fixture:1:option:1"]["contentPack"])
        self.assertEqual("Game of Crone", data["details"]["fixture:1:option:2"]["contentPack"])
        self.assertEqual("Stranger Sins", data["details"]["fixture:1:option:3"]["contentPack"])
        self.assertEqual("Stranger Sins", data["details"]["fixture:1:option:4"]["contentPack"])
        self.assertEqual({
            "Base Game": 1,
            "Better Call Soul": 1,
            "Game of Crone": 1,
            "Stranger Sins": 2,
        }, data["stats"]["contentPacks"])
        self.assertNotIn("color", data["nodes"][0])
        rendered = render_quest_graph_html(data)
        self.assertIn('id="content-pack"', rendered)
        self.assertNotIn('<select id="content-pack"', rendered)
        self.assertIn('class="multi-select has-search" id="graph"', rendered)
        self.assertIn('class="multi-select has-search" id="node-list"', rendered)
        self.assertIn('class="select-all"', rendered)
        self.assertIn('placeholder="Search graphs…"', rendered)
        self.assertIn('placeholder="Search matching nodes…"', rendered)
        self.assertIn('id="show-debug"', rendered)
        self.assertIn("showDebug.checked=savedState.showDebug===true", rendered)
        self.assertIn("showDebug.checked||!n.isDebug", rendered)
        self.assertIn(".checkbox-menu label[hidden] { display:none; }", rendered)
        self.assertIn("setChecklistOptions", rendered)
        self.assertIn("visibleChecklistInputs(control)", rendered)
        self.assertIn('id="graph-navigation"', rendered)
        self.assertIn("graph_expander", rendered)
        self.assertIn("setGraphIncluded(clicked.expandGraph,true)", rendered)
        self.assertIn("compactVisibleLayout", rendered)
        self.assertIn("compactVisibleLayout(seed,expanders)", rendered)
        self.assertIn("layoutDepth:visibleNode.depth+side", rendered)
        self.assertIn("layoutRank:group.direction==='in'?0:2", rendered)
        self.assertIn("− Collapse ${graphName}", rendered)
        self.assertIn("network.getViewPosition()", rendered)
        self.assertIn("network.getScale()", rendered)
        self.assertIn("network.moveTo({position:preservedView.position", rendered)
        self.assertIn("graveyard-keeper-quest-graph-state-v1", rendered)
        self.assertIn("localStorage.getItem(STORAGE_KEY)", rendered)
        self.assertIn("localStorage.setItem(STORAGE_KEY", rendered)
        self.assertIn("matchingNodes:[...checklistValues(nodeList)]", rendered)
        self.assertIn("selection:{nodes:network.getSelectedNodes(),edges:network.getSelectedEdges()}", rendered)
        self.assertIn("network.setSelection({nodes:selectedNodes,edges:selectedEdges}", rendered)
        self.assertIn("applyFilter(validSavedView(savedState.view))", rendered)
        self.assertIn("window.addEventListener('beforeunload',persistState)", rendered)
        self.assertIn('id="loading-progress"', rendered)
        self.assertIn("initializeGraph().catch", rendered)
        self.assertIn("left → right by dependency depth", rendered)
        self.assertIn("content-anchor:${packName}", rendered)

    def test_neutral_reward_inherits_dlc_from_required_player_state_source(self) -> None:
        source_graph = parse_graph(self.write_graph([
            node(1, "StartEvent"),
            node(2, "Flow_SetPlayerParam", {
                "Param name": stored("drop_ending_note"), "Value": stored(1)}),
            node(3, "Flow_UnlockPhrase", {"Phrase": stored("refugee_ending_ready")}),
        ], [
            edge(1, "Once", 2, "In"), edge(2, "Out", 3, "In"),
        ], name="alarich"))
        neutral_graph = parse_graph(self.write_graph([
            node(1, "CustomEvent", identifier="prayed"),
            node(2, "Flow_PlayerFlag", {"param": stored("drop_ending_note")}),
            node(3, "Flow_DropItem", {
                "Res_id": stored("ending_note"), "Amount": stored(1)}),
        ], [
            edge(1, "Out", 2, "In"), edge(2, ">= 1", 3, "In"),
        ], name="donation_box"))

        data = build_quest_graph_data([
            analyze_graph(source_graph), analyze_graph(neutral_graph),
        ])

        self.assertEqual("Game of Crone", data["details"]["donation_box:3"]["contentPack"])

    def test_generated_edge_ids_are_unique_and_contiguous(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": None}, answers=["answer"]),
            node(2, "Flow_UnlockPhrase", {"Phrase ID": stored("next")}),
            node(3, "Flow_MultiAnswer", {"#0": None}, answers=["@next"]),
            node(4, "Flow_AddRelation", {"Value": stored(1.0, "System.Single")}),
        ], [
            edge(1, "out_0", 2, "In"), edge(3, "out_0", 4, "In"),
        ]))

        data = build_quest_graph_data([analyze_graph(graph)])

        edge_ids = [value["id"] for value in data["edges"]]
        self.assertEqual([f"edge:{index}" for index in range(len(edge_ids))], edge_ids)
        self.assertEqual(len(edge_ids), len(set(edge_ids)))

    def test_parent_answer_price_is_inherited_by_nested_choice_results(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": {"$type": "AnswerData"}}, answers=["@pay"]),
            wrapper(2, "Flow_Answer", {"price": {}, "lock": {}, "reward": {}}),
            wrapper(3, "Flow_SmartRes", {
                "res_type": stored("Item"), "id": stored("quest_fake_coins"), "v": stored(1.0),
            }),
            node(4, "Flow_Talk", {"Text": stored("before_nested_choice")}),
            node(5, "Flow_MultiAnswer", {"#0": None, "#1": None}, answers=["reply_a", "reply_b"]),
            node(6, "Flow_UnlockPhrase", {"Phrase ID": stored("result_a")}),
            node(7, "Flow_UnlockPhrase", {"Phrase ID": stored("result_b")}),
        ], [
            edge(3, "Value", 2, "price", "SmartRes"),
            edge(2, "Value", 1, "#0", "AnswerData"),
            edge(1, "out_0", 4, "In"), edge(4, "Out", 5, "In"),
            edge(5, "out_0", 6, "In"), edge(5, "out_1", 7, "In"),
        ]))

        summaries = build_quest_summaries(
            analyze_graph(graph), build_phrase_unlock_index([analyze_graph(graph)]),
            include_without_rewards=True,
        )
        nested = [summary for summary in summaries if summary.multi_answer_node == "5"]

        self.assertEqual(2, len(nested))
        self.assertTrue(all(summary.required_items == ["quest_fake_coins x1"] for summary in nested))

    def test_item_returned_after_answer_price_is_not_a_reward(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": {"$type": "AnswerData"}}, answers=["show_papers"]),
            wrapper(2, "Flow_Answer", {"price": {}, "lock": {}, "reward": {}}),
            wrapper(3, "Flow_SmartRes", {
                "res_type": stored("Item"), "id": stored("rightful_citizen_paper"), "v": stored(1.0),
            }),
            node(4, "Flow_DropItem", {
                "Res_id": stored("rightful_citizen_paper"), "Amount": stored(1),
            }),
            node(5, "Flow_UnlockPhrase", {"Phrase ID": stored("papers_shown")}),
        ], [
            edge(3, "Value", 2, "price", "SmartRes"),
            edge(2, "Value", 1, "#0", "AnswerData"),
            edge(1, "out_0", 4, "In"), edge(4, "Out", 5, "In"),
        ]))

        summary = build_quest_summaries(
            analyze_graph(graph), {}, include_without_rewards=True,
        )[0]

        self.assertEqual(["rightful_citizen_paper x1"], summary.required_items)
        self.assertEqual([], summary.item_drops)
        self.assertEqual(["papers_shown"], summary.phrases_unlocked)

    def test_overhead_item_roundtrip_is_not_an_item_reward(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_GetOverhead"),
            node(2, "Flow_DropItem", {"Item": None, "Amount": stored(1)}),
            node(3, "Flow_SetOverhead"),
        ], [
            edge(1, "Item", 2, "Item", "Item"),
            edge(2, "Out", 3, "In"),
        ]))

        analysis = analyze_graph(graph)

        self.assertEqual([], analysis.findings)

    def test_item_return_excess_remains_a_reward(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": {"$type": "AnswerData"}}, answers=["trade"]),
            wrapper(2, "Flow_Answer", {"price": {}, "lock": {}, "reward": {}}),
            wrapper(3, "Flow_SmartRes", {
                "res_type": stored("Item"), "id": stored("token"), "v": stored(1.0),
            }),
            node(4, "Flow_DropItem", {"Res_id": stored("token"), "Amount": stored(3)}),
        ], [
            edge(3, "Value", 2, "price", "SmartRes"),
            edge(2, "Value", 1, "#0", "AnswerData"),
            edge(1, "out_0", 4, "In"),
        ]))

        summary = build_quest_summaries(analyze_graph(graph), {})[0]

        self.assertEqual(["token x1"], summary.required_items)
        self.assertEqual([("token", 2)], [
            (drop.item, drop.amount) for drop in summary.item_drops
        ])

    def test_inventory_requirement_does_not_cancel_same_item_reward(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "CustomEvent"),
            node(2, "Flow_CreateItem", {
                "item_id": stored("token"), "value": stored(1.0, "System.Single")}),
            node(3, "Flow_HasItemInInventory", {"Item": None, "Item ID": stored(None)}),
            node(4, "Flow_DropItem", {"Res_id": stored("token"), "Amount": stored(1)}),
        ], [
            edge(1, "Out", 3, "In"), edge(2, "Value", 3, "Item", "Item"),
            edge(3, "Yes", 4, "In"),
        ]))

        summary = build_quest_summaries(analyze_graph(graph), {})[0]

        self.assertEqual(["token x1"], summary.required_items)
        self.assertEqual([("token", 1)], [
            (drop.item, drop.amount) for drop in summary.item_drops
        ])

    def test_remove_then_drop_is_a_return_but_drop_then_remove_is_a_reward(self) -> None:
        def summary_for_order(remove_first: bool):
            first, second = (2, 3) if remove_first else (3, 2)
            graph = parse_graph(self.write_graph([
                node(1, "Flow_MultiAnswer", {"#0": None}, answers=["exchange"]),
                node(2, "Flow_RemoveItemFromInventory", {
                    "Item ID": stored("token"), "Items Count": stored(1)}),
                node(3, "Flow_DropItem", {"Res_id": stored("token"), "Amount": stored(1)}),
                node(4, "Flow_UnlockPhrase", {"Phrase ID": stored("exchange_complete")}),
            ], [
                edge(1, "out_0", first, "In"), edge(first, "Out", second, "In"),
                edge(second, "Out", 4, "In"),
            ], name=f"fixture_{remove_first}"))
            return build_quest_summaries(
                analyze_graph(graph), {}, include_without_rewards=True,
            )[0]

        returned = summary_for_order(True)
        rewarded = summary_for_order(False)

        self.assertEqual(["token x1"], returned.required_items)
        self.assertEqual([], returned.item_drops)
        self.assertEqual([("token", 1)], [
            (drop.item, drop.amount) for drop in rewarded.item_drops
        ])

    def test_nested_choice_only_inherits_prices_common_to_every_entry_option(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": {"$type": "AnswerData"}, "#1": None},
                 answers=["paid", "free"]),
            wrapper(2, "Flow_Answer", {"price": {}, "lock": {}, "reward": {}}),
            wrapper(3, "Flow_SmartRes", {
                "res_type": stored("Item"), "id": stored("optional_item"), "v": stored(1.0),
            }),
            node(4, "Flow_MultiAnswer", {"#0": None}, answers=["result"]),
            node(5, "Flow_UnlockPhrase", {"Phrase ID": stored("finished")}),
        ], [
            edge(3, "Value", 2, "price", "SmartRes"),
            edge(2, "Value", 1, "#0", "AnswerData"),
            edge(1, "out_0", 4, "In"), edge(1, "out_1", 4, "In"),
            edge(4, "out_0", 5, "In"),
        ]))
        analysis = analyze_graph(graph)

        summary = next(value for value in build_quest_summaries(
            analysis, build_phrase_unlock_index([analysis]), include_without_rewards=True,
        ) if value.multi_answer_node == "4")

        self.assertEqual([], summary.required_items)

    def test_real_snake_fake_coin_answers_inherit_the_parent_answer_price(self) -> None:
        if not CULTIST_DUMP.exists():
            self.skipTest("local companion dump is not available")

        analysis = analyze_graph(parse_graph(CULTIST_DUMP))
        summaries = build_quest_summaries(
            analysis, build_phrase_unlock_index([analysis]), include_without_rewards=True,
        )
        by_reference = {summary.reference: summary for summary in summaries}

        for reference in ("npc_cultist:624:option:0", "npc_cultist:624:option:1"):
            self.assertEqual(["quest_fake_coins x1"], by_reference[reference].required_items)

    def test_real_bishop_citizen_papers_are_consumed_without_a_return_reward(self) -> None:
        if not BISHOP_DUMP.exists():
            self.skipTest("local companion dump is not available")

        analysis = analyze_graph(parse_graph(BISHOP_DUMP))
        summary = next(value for value in build_quest_summaries(
            analysis, build_phrase_unlock_index([analysis]), include_without_rewards=True,
        ) if value.reference == "npc_bishop:1068:option:0")

        self.assertEqual(["rightful_citizen_paper x1"], summary.required_items)
        self.assertEqual([], summary.item_drops)

    def test_unresolved_standalone_reward_remains_visible(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_DropItem", {
                "Res_id": stored("important_reward"), "Amount": stored(1),
            }),
        ], []))

        data = build_quest_graph_data([analyze_graph(graph)])

        reward = data["details"]["fixture:1"]
        self.assertEqual("important_reward", reward["rewards"][0]["item"])
        self.assertTrue(reward["unresolvedEntry"])
        self.assertIn(
            "Ausführungseinstieg nicht aufgelöst; Reward bleibt sichtbar",
            reward["uncertainties"],
        )

    def test_blacklist_only_answer_returning_to_menu_is_not_a_quest_leaf(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": None}, answers=["close_dialogue"]),
            node(2, "Flow_AddPhraseToBlacklist", {
                "Phrase ID": stored("close_dialogue"),
                "remove": stored(False, "System.Boolean"),
            }),
        ], [
            edge(1, "out_0", 2, "In"),
            edge(2, "Out", 1, "In"),
        ]))

        data = build_quest_graph_data([analyze_graph(graph)])

        self.assertNotIn("fixture:1:option:0", data["details"])
        self.assertFalse(any(node["label"] == "close_dialogue" for node in data["nodes"]))

    def test_initial_plain_answer_is_connected_to_start(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": None}, answers=["initial_answer"]),
            node(2, "Flow_AddRelation", {"Value": stored(1.0, "System.Single")}),
        ], [edge(1, "out_0", 2, "In")]))

        data = build_quest_graph_data([analyze_graph(graph)])

        self.assertIn("quest-start", data["details"])
        self.assertTrue(any(
            value["from"] == "quest-start"
            and value["to"] == "fixture:1:option:0"
            and value["kind"] == "initial"
            for value in data["edges"]
        ))
        positions = {value["id"]: value["x"] for value in data["nodes"]}
        self.assertLess(positions["quest-start"], positions["fixture:1:option:0"])

    def test_reward_item_connects_to_game_data_craft_requirement(self) -> None:
        reward_graph = parse_graph(self.write_graph([
            node(1, "Flow_DropItem", {
                "Res_id": stored("portal_key"), "Amount": stored(1),
            }),
        ], [], name="reward_source"))
        target_graph = parse_graph(self.write_graph([
            node(1, "StartEvent"),
            node(2, "Flow_AddRelation", {"Value": stored(1.0, "System.Single")}),
        ], [edge(1, "Out", 2, "In")], name="portal_entry"))
        scripts = {"portal_entry": [{
            "file": "craft_data.json", "record": "craft_portal",
            "field": "end_script", "trigger": "craft craft_portal",
            "requiredItems": ["portal_key x1"],
        }]}

        data = build_quest_graph_data(
            [analyze_graph(reward_graph), analyze_graph(target_graph)],
            game_data_scripts=scripts,
        )

        craft = next(value["id"] for value in data["nodes"]
                     if value["label"] == "craft craft_portal → portal_entry")
        self.assertTrue(any(
            value["from"] == "reward_source:1" and value["to"] == craft
            and value["kind"] == "item_requirement"
            for value in data["edges"]
        ))

    def test_game_start_script_is_connected_to_start(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "StartEvent"),
            node(2, "Flow_AddRelation", {"Value": stored(1.0, "System.Single")}),
        ], [edge(1, "Out", 2, "In")], name="initial_script"))
        scripts = {"initial_script": [{
            "file": "quests_data.json", "record": "start", "field": "start_script",
            "trigger": "game_start",
        }]}

        data = build_quest_graph_data([analyze_graph(graph)], game_data_scripts=scripts)

        entry = next(value["id"] for value in data["nodes"]
                     if value["label"] == "game_start → initial_script")
        self.assertTrue(any(
            value["from"] == "quest-start" and value["to"] == entry
            and value["kind"] == "initial"
            for value in data["edges"]
        ))

    def test_identical_finding_offered_by_multiple_menus_is_rendered_once(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": None}, answers=["@shared_answer"]),
            node(2, "Flow_MultiAnswer", {"#0": None}, answers=["@shared_answer"]),
            node(3, "Flow_Talk", {"Text": stored("shared_talk")}),
            node(4, "Flow_AddRelation", {"Value": stored(10.0, "System.Single")}),
        ], [
            edge(1, "out_0", 3, "In"), edge(2, "out_0", 3, "In"),
            edge(3, "On Finished", 4, "In"),
        ]))
        data = build_quest_graph_data([analyze_graph(graph)])
        matching = [node for node in data["nodes"] if node["label"] == "shared_answer"]

        self.assertEqual(1, len(matching))
        self.assertEqual(["1", "2"], data["details"][matching[0]["id"]]["multiAnswerNodes"])

    def test_null_answer_data_keeps_phrase_requirement_and_blacklist_removal(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": None}, answers=["@required_phrase"]),
            node(2, "CustomFunctionCall", _sourceOutputUID="option-function"),
            node(3, "CustomFunctionEvent", _UID="option-function", identifier="@required_phrase"),
            node(4, "Flow_AddPhraseToBlacklist", {
                "Phrase ID": stored("@required_phrase"), "remove": stored(True, "System.Boolean")}),
            node(5, "Flow_AddRelation", {"Value": stored(5.0, "System.Single")}),
            node(6, "Return"),
        ], [
            edge(1, "out_0", 2, ""), edge(3, "", 4, "In"), edge(4, "Out", 5, "In"),
            edge(5, "Out", 6, "In"),
        ]))
        summaries = build_quest_summaries(analyze_graph(graph), {})
        self.assertEqual(1, len(summaries))
        self.assertEqual(["required_phrase"], summaries[0].required_quests)
        self.assertEqual(["required_phrase"], summaries[0].phrases_removed_from_blacklist)
        self.assertFalse(summaries[0].phrases_to_blacklist)

    def test_plain_phrase_is_a_required_quest_and_uses_unlock_source(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": None}, answers=["plain_phrase"]),
            node(2, "Flow_AddRelation", {"Value": stored(5.0, "System.Single")}),
            node(3, "Return"),
            node(4, "Flow_UnlockPhrase", {"Phrase": stored("plain_phrase")}),
        ], [edge(1, "out_0", 2, "In"), edge(2, "Out", 3, "In")]))
        analysis = analyze_graph(graph)
        summaries = build_quest_summaries(analysis, build_phrase_unlock_index([analysis]))

        self.assertEqual(["plain_phrase"], summaries[0].required_quests)
        self.assertEqual(["fixture.json:4"], summaries[0].phrase_unlock_sources)

    def test_plain_phrase_without_unlock_is_initially_visible_without_uncertainty(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": None}, answers=["plain_phrase"]),
            node(2, "Flow_AddRelation", {"Value": stored(5.0, "System.Single")}),
        ], [edge(1, "out_0", 2, "In")]))

        summary = build_quest_summaries(analyze_graph(graph), {})[0]

        self.assertEqual(["plain_phrase"], summary.required_quests)
        self.assertEqual([
            "Beim neuen Spiel sichtbar (MultiAnswerGUI-Regel: kein @-Präfix)"
        ], summary.phrase_unlock_sources)
        self.assertFalse(any("Freischaltquelle" in issue for issue in summary.uncertainties))

    def test_blacklist_removal_is_a_phrase_visibility_source(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_AddPhraseToBlacklist", {
                "Phrase ID": stored("plain_phrase"), "remove": stored(True, "System.Boolean")}),
            node(2, "Flow_MultiAnswer", {"#0": None}, answers=["plain_phrase"]),
            node(3, "Flow_AddRelation", {"Value": stored(5.0, "System.Single")}),
        ], [edge(2, "out_0", 3, "In")]))
        analysis = analyze_graph(graph)
        phrase_sources = build_phrase_unlock_index([analysis])
        summary = build_quest_summaries(analysis, phrase_sources)[0]

        self.assertEqual(["fixture.json:1"], phrase_sources["plain_phrase"])
        self.assertEqual(["fixture.json:1"], summary.phrase_unlock_sources)

        data = build_quest_graph_data([analysis], phrase_sources)
        self.assertIn(("unlock:fixture.json:1", "fixture:2:option:0", "plain_phrase"), {
            (entry["from"], entry["to"], entry["label"]) for entry in data["edges"]
        })

    def test_quest_graph_connects_phrase_unlock_to_phrase_target(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": None, "#1": None}, answers=["source", "next"]),
            node(2, "Flow_UnlockPhrase", {"Phrase": stored("next")}), node(3, "Return"),
            node(4, "Flow_AddPhraseToBlacklist", {
                "Phrase ID": stored("next"), "remove": stored(False, "System.Boolean")}),
            node(5, "Flow_AddRelation", {"Value": stored(5.0, "System.Single")}), node(6, "Return"),
        ], [edge(1, "out_0", 2, "In"), edge(2, "Out", 3, "In"),
            edge(1, "out_1", 4, "In"), edge(4, "Out", 5, "In"), edge(5, "Out", 6, "In")]))
        data = build_quest_graph_data([analyze_graph(graph)])

        self.assertIn(("fixture:1:option:0", "fixture:1:option:1", "next"), {
            (entry["from"], entry["to"], entry["label"]) for entry in data["edges"]})
        rendered = render_quest_graph_html(data)
        self.assertIn('id="network"', rendered)
        self.assertIn('id="detail"', rendered)

    def test_quest_graph_connects_run_script_to_target_start_results(self) -> None:
        caller = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": None}, answers=["@finale"]),
            node(2, "Flow_RunScript", {"Script name": stored("final_ritual")}),
            node(3, "Flow_AddPhraseToBlacklist", {
                "Phrase ID": stored("@finale"), "remove": stored(False, "System.Boolean")}),
        ], [edge(1, "out_0", 2, "In"), edge(2, "Out", 3, "In")], name="npc_cultist"))
        target = parse_graph(self.write_graph([
            node(1, "StartEvent"),
            node(2, "Flow_DropItem", {"Res_id": stored("eternal_burning_coil"), "Amount": stored(1)}),
        ], [edge(1, "Once", 2, "In")], name="final_ritual"))

        data = build_quest_graph_data([analyze_graph(caller), analyze_graph(target)])
        source = "npc_cultist:1:option:0"
        result = "final_ritual:2"
        link = next(entry for entry in data["edges"]
                    if entry["from"] == source and entry["to"] == result)

        self.assertEqual("run_script", link["kind"])
        self.assertEqual("runs final_ritual", link["label"])
        self.assertIn({
            "from": source, "to": result, "script": "final_ritual",
            "callNode": "2", "targetGraph": "final_ritual", "direction": "calls",
        }, data["details"][source]["scriptLinks"])
        self.assertIn("2 -> final_ritual (Flow_RunScript)",
                      data["details"][source]["functionCalls"])

    def test_local_run_script_event_does_not_create_cross_graph_link(self) -> None:
        caller = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": None}, answers=["local"]),
            node(2, "Flow_RunScript", {"Script name": stored(":final_ritual")}),
            node(3, "Flow_AddPhraseToBlacklist", {"Phrase ID": stored("local")}),
        ], [edge(1, "out_0", 2, "In"), edge(2, "Out", 3, "In")], name="caller"))
        target = parse_graph(self.write_graph([
            node(1, "StartEvent"),
            node(2, "Flow_DropItem", {"Res_id": stored("reward"), "Amount": stored(1)}),
        ], [edge(1, "Once", 2, "In")], name="final_ritual"))

        data = build_quest_graph_data([analyze_graph(caller), analyze_graph(target)])

        self.assertFalse(any(edge_data["kind"] == "run_script" for edge_data in data["edges"]))

    def test_quest_graph_keeps_rewardless_run_script_dispatcher_as_bridge(self) -> None:
        dispatcher = parse_graph(self.write_graph([
            node(1, "StartEvent"),
            node(2, "Flow_RunScript", {"Script name": stored("cutscene")}),
        ], [edge(1, "Once", 2, "In")], name="world_entry"))
        target = parse_graph(self.write_graph([
            node(1, "StartEvent"),
            node(2, "Flow_DropItem", {"Res_id": stored("reward"), "Amount": stored(1)}),
        ], [edge(1, "Once", 2, "In")], name="cutscene"))

        data = build_quest_graph_data([analyze_graph(dispatcher), analyze_graph(target)])
        bridge = "script-call:world_entry.json:2"

        self.assertIn(bridge, data["details"])
        self.assertIn((bridge, "cutscene:2", "run_script"), {
            (entry["from"], entry["to"], entry["kind"]) for entry in data["edges"]
        })

    def test_quest_graph_connects_unique_cross_graph_interaction_event(self) -> None:
        source = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": None}, answers=["continue"]),
            node(2, "Flow_AddInteractionEvent", {"Event": stored("quest_finished")}),
        ], [edge(1, "out_0", 2, "In")], name="npc_source"))
        target = parse_graph(self.write_graph([
            node(1, "CustomEvent", eventName={"_value": "quest_finished"}),
            node(2, "Flow_DropItem", {"Res_id": stored("reward"), "Amount": stored(1)}),
        ], [edge(1, "Received", 2, "In")], name="quest_target"))

        data = build_quest_graph_data([analyze_graph(source), analyze_graph(target)])
        link = next(entry for entry in data["edges"] if entry["kind"] == "event")

        self.assertEqual("npc_source:1:option:0", link["from"])
        self.assertEqual("quest_target:2", link["to"])
        self.assertEqual("enables interaction: quest_finished", link["label"])

    def test_event_wgo_target_disambiguates_repeated_event_name(self) -> None:
        source = parse_graph(self.write_graph([
            node(1, "StartEvent"),
            node(2, "Flow_AddInteractionEvent", {"Event": stored("available"), "WGO": None}),
            node(3, "Flow_FindWGO", {"custom_tag": stored("target_a"), "obj_id": None}),
        ], [
            edge(1, "Once", 2, "In"),
            edge(3, "WGO", 2, "WGO", "WorldGameObject"),
        ], name="dispatcher"))
        targets = []
        for name, item in (("target_a", "reward_a"), ("target_b", "reward_b")):
            targets.append(parse_graph(self.write_graph([
                node(1, "CustomEvent", eventName={"_value": "available"}),
                node(2, "Flow_DropItem", {"Res_id": stored(item), "Amount": stored(1)}),
            ], [edge(1, "Received", 2, "In")], name=name)))

        data = build_quest_graph_data([
            analyze_graph(source), *(analyze_graph(target) for target in targets),
        ])
        event_targets = {entry["to"] for entry in data["edges"] if entry["kind"] == "event"}

        self.assertEqual({"target_a:2"}, event_targets)

    def test_game_data_object_script_is_an_external_graph_entry(self) -> None:
        (self.temporary_path / "objs_data.json").write_text(json.dumps([{
            "id": "sleeping_place",
            "interaction_1": {"script": "normal_sleep"},
        }]), encoding="utf-8")
        target = parse_graph(self.write_graph([
            node(1, "StartEvent"),
            node(2, "Flow_DropItem", {"Res_id": stored("body"), "Amount": stored(1)}),
        ], [edge(1, "Once", 2, "In")], name="normal_sleep"))

        scripts = build_game_data_script_index(self.temporary_path)
        data = build_quest_graph_data([analyze_graph(target)], game_data_scripts=scripts)
        link = next(entry for entry in data["edges"] if entry["kind"] == "game_data")

        self.assertEqual("normal_sleep:2", link["to"])
        self.assertEqual("starts normal_sleep", link["label"])
        self.assertEqual("world object sleeping_place",
                         data["details"][link["from"]]["otherRequirements"][0])

    def test_quest_graph_connects_wgo_flag_through_registered_interaction_event(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": None, "#1": None}, answers=["@silver", "@gold"]),
            node(2, "Flow_AddRelation", {"Value": stored(5.0, "System.Single")}),
            node(3, "Flow_SetWGOParam", {
                "Param name": stored("books_1_is_unlocked"), "Value": stored(1.0, "System.Single")}),
            node(4, "Return"),
            node(5, "Flow_AddPhraseToBlacklist", {
                "Phrase ID": stored("@gold"), "remove": stored(False, "System.Boolean")}),
            node(6, "Flow_AddRelation", {"Value": stored(5.0, "System.Single")}),
            node(7, "Return"),
            node(8, "CustomEvent", eventName={"_value": "on_came_to_finish"}),
            node(9, "Flow_ParamFlag", {"param": stored("books_1_is_unlocked")}),
            node(10, "Flow_AddInteractionEvent", {"Event": stored("books_1")}),
            node(11, "CustomEvent", eventName={"_value": "books_1"}),
            node(12, "Flow_UnlockPhrase", {"Phrase": stored("@gold")}),
            node(13, "Return"),
        ], [
            edge(1, "out_0", 2, "In"), edge(2, "Out", 3, "In"), edge(3, "Out", 4, "In"),
            edge(1, "out_1", 5, "In"), edge(5, "Out", 6, "In"), edge(6, "Out", 7, "In"),
            edge(8, "Received", 9, "In"), edge(9, ">= 1", 10, "In"),
            edge(11, "Received", 12, "In"), edge(12, "Out", 13, "In"),
        ]))
        data = build_quest_graph_data([analyze_graph(graph)])
        edges = {(entry["from"], entry["to"], entry["kind"]): entry for entry in data["edges"]}

        source = "fixture:1:option:0"
        unlock = "unlock:fixture.json:12"
        target = "fixture:1:option:1"
        self.assertIn((source, unlock, "state_event"), edges)
        self.assertEqual("books_1_is_unlocked → books_1", edges[(source, unlock, "state_event")]["label"])
        self.assertEqual("11 -> 12", data["details"][unlock]["stateEventLinks"][0]["eventPath"])
        self.assertIn((unlock, target, "phrase"), edges)
        self.assertEqual("enables", data["details"][source]["stateEventLinks"][0]["direction"])
        self.assertEqual("requires", data["details"][unlock]["stateEventLinks"][0]["direction"])

    def test_quest_graph_connects_cross_graph_player_state_and_keeps_filter_context(self) -> None:
        source_graph = parse_graph(self.write_graph([
            node(1, "StartEvent"),
            node(2, "Flow_SetPlayerParam", {
                "Param name": stored("repair_finished"), "Value": stored(1.0, "System.Single")}),
            node(3, "Flow_SetTaskState", {"Task": stored("repair"), "State": stored("Complete")}),
            node(4, "Flow_UnlockPhrase", {"Phrase": stored("@source_phrase")}),
        ], [
            edge(1, "Once", 2, "In"), edge(2, "Out", 3, "In"), edge(3, "Out", 4, "In"),
        ], name="source_event"))
        target_graph = parse_graph(self.write_graph([
            node(1, "StartEvent"),
            node(2, "Flow_PlayerFlag", {"param": stored("repair_finished")}),
            node(3, "Flow_UnlockPhrase", {"Phrase": stored("@target_phrase")}),
            node(4, "Flow_EndScript"),
        ], [
            edge(1, "Once", 2, "In"), edge(2, ">= 1", 3, "In"), edge(2, "== 0", 4, "In"),
        ], name="target_event"))
        data = build_quest_graph_data([
            analyze_graph(source_graph), analyze_graph(target_graph),
        ])
        source = "unlock:source_event.json:4"
        target = "unlock:target_event.json:3"
        link = next(entry for entry in data["edges"]
                    if entry["from"] == source and entry["to"] == target)

        self.assertEqual("player_state", link["kind"])
        self.assertEqual("repair_finished (sets)", link["label"])
        self.assertEqual(["StartEvent"], data["details"][source]["entryEvents"])
        self.assertIn({"task": "repair", "state": "Complete"}, data["details"][source]["taskStates"])
        self.assertIn("Flow_PlayerFlag repair_finished -> >= 1",
                      data["details"][target]["otherRequirements"])
        rendered = render_quest_graph_html(data)
        self.assertIn("expandable graph boundaries", rendered)
        self.assertIn("collapsed_graph", rendered)
        self.assertIn("fromVisible===toVisible", rendered)
        self.assertIn("setGraphIncluded(clicked.expandGraph,true)", rendered)

    def test_quest_graph_connects_integer_player_param_comparison(self) -> None:
        source_graph = parse_graph(self.write_graph([
            node(1, "StartEvent"),
            node(2, "Flow_SetPlayerParam", {
                "Param name": stored("dialogues_count"), "Value": stored(2)}),
            node(3, "Flow_UnlockPhrase", {"Phrase": stored("source")}),
        ], [
            edge(1, "Once", 2, "In"), edge(2, "Out", 3, "In"),
        ], name="source_counter"))
        target_graph = parse_graph(self.write_graph([
            node(1, "StartEvent"),
            node(2, "Flow_PlayerParamCompareInt", {
                "param": stored("dialogues_count"), "value": stored(2)}),
            node(3, "Flow_UnlockPhrase", {"Phrase": stored("target")}),
        ], [
            edge(1, "Once", 2, "In"), edge(2, "==", 3, "In"),
        ], name="target_counter"))
        data = build_quest_graph_data([
            analyze_graph(source_graph), analyze_graph(target_graph),
        ])
        source = "unlock:source_counter.json:3"
        target = "unlock:target_counter.json:3"
        link = next(entry for entry in data["edges"]
                    if entry["from"] == source and entry["to"] == target)

        self.assertEqual("player_state", link["kind"])
        self.assertEqual("dialogues_count (sets)", link["label"])
        self.assertIn("Flow_PlayerParamCompareInt dialogues_count == 2",
                      data["details"][target]["otherRequirements"])

    def test_reward_details_include_player_state_changes(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "CustomEvent"),
            node(2, "Flow_SetPlayerParam", {
                "Param name": stored("quest_done"), "Value": stored(1)}),
            node(3, "Flow_AddRelation", {"Value": stored(5.0, "System.Single")}),
        ], [
            edge(1, "Out", 2, "In"), edge(2, "Out", 3, "In"),
        ]))
        data = build_quest_graph_data([analyze_graph(graph)])

        self.assertEqual([{
            "operation": "set", "parameter": "quest_done", "value": "1", "node": "2",
        }], data["details"]["fixture:3"]["playerStateChanges"])

    def test_nested_multi_answer_options_are_linked_without_merging_their_effects(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": None}, answers=["@parent"]),
            node(2, "Flow_AddPhraseToBlacklist", {
                "Phrase ID": stored("@parent"), "remove": stored(False, "System.Boolean")}),
            node(3, "Flow_MultiAnswer", {"#0": None, "#1": None}, answers=["child_a", "child_b"]),
            node(4, "Flow_Talk", {"Text": stored("child_a_talk")}),
            node(5, "Flow_SetTaskState", {"Task": stored("child_a_task"), "State": stored("Complete")}),
            node(6, "Flow_UnlockPhrase", {"Phrase": stored("@after_a")}),
            node(7, "Flow_UnlockPhrase", {"Phrase": stored("@after_b")}),
        ], [
            edge(1, "out_0", 2, "In"), edge(2, "Out", 3, "In"),
            edge(3, "out_0", 4, "In"), edge(4, "On Finished", 5, "In"), edge(5, "On Finished", 6, "In"),
            edge(3, "out_1", 7, "In"),
        ]))
        data = build_quest_graph_data([analyze_graph(graph)])
        links = {(entry["from"], entry["to"], entry["kind"]) for entry in data["edges"]}
        parent = "fixture:1:option:0"
        menu = "choice-menu:fixture:3"
        child_a = "fixture:3:option:0"
        child_b = "fixture:3:option:1"

        self.assertIn((parent, menu, "choice_menu"), links)
        self.assertIn((menu, child_a, "choice_option"), links)
        self.assertIn((menu, child_b, "choice_option"), links)
        self.assertEqual([{"task": "child_a_task", "state": "Complete"}],
                         data["details"][child_a]["taskStates"])
        self.assertFalse(data["details"][child_b]["taskStates"])

    def test_equivalent_nested_answers_share_one_outcome_node(self) -> None:
        graph = parse_graph(self.write_graph([
            node(0, "StartEvent"),
            node(1, "Flow_MultiAnswer", {"#0": None}, answers=["@parent"]),
            node(2, "Flow_AddPhraseToBlacklist", {
                "Phrase ID": stored("@parent"), "remove": stored(False, "System.Boolean")}),
            node(3, "Flow_MultiAnswer", {"#0": None, "#1": None},
                 answers=["answer_a", "answer_b"]),
            node(4, "Flow_Talk", {"Text": stored("answer_a_talk")}),
            node(5, "Flow_AddPhraseToBlacklist", {
                "Phrase ID": stored("answer_a"), "remove": stored(False, "System.Boolean")}),
            node(6, "Flow_Talk", {"Text": stored("answer_b_talk")}),
            node(7, "Flow_AddPhraseToBlacklist", {
                "Phrase ID": stored("answer_b"), "remove": stored(False, "System.Boolean")}),
        ], [
            edge(0, "Out", 1, "In"), edge(1, "out_0", 2, "In"), edge(2, "Out", 3, "In"),
            edge(3, "out_0", 4, "In"), edge(4, "On Finished", 5, "In"),
            edge(3, "out_1", 6, "In"), edge(6, "On Finished", 7, "In"),
        ]))
        data = build_quest_graph_data([analyze_graph(graph)])
        parent = "fixture:1:option:0"
        menu = "choice-menu:fixture:3"
        canonical = "fixture:3:option:0"
        alias = "fixture:3:option:1"
        links = {(entry["from"], entry["to"], entry["kind"]) for entry in data["edges"]}

        self.assertIn((parent, menu, "choice_menu"), links)
        self.assertIn((menu, canonical, "choice_option"), links)
        self.assertNotIn(alias, data["details"])
        self.assertEqual(["answer_a", "answer_b"], [
            entry["phrase"] for entry in data["details"][canonical]["choiceAlternatives"]])
        self.assertEqual(["answer_a_talk", "answer_b_talk"], [
            entry["conversations"][0]
            for entry in data["details"][canonical]["choiceAlternatives"]])

    def test_nested_answers_with_different_rewards_remain_separate(self) -> None:
        graph = parse_graph(self.write_graph([
            node(0, "StartEvent"),
            node(1, "Flow_MultiAnswer", {"#0": None}, answers=["@parent"]),
            node(2, "Flow_AddPhraseToBlacklist", {
                "Phrase ID": stored("@parent"), "remove": stored(False, "System.Boolean")}),
            node(3, "Flow_MultiAnswer", {"#0": None, "#1": None},
                 answers=["twenty_relation", "ten_relation"]),
            node(4, "Flow_AddRelation", {"Value": stored(20.0, "System.Single")}),
            node(5, "Flow_AddRelation", {"Value": stored(10.0, "System.Single")}),
        ], [
            edge(0, "Out", 1, "In"), edge(1, "out_0", 2, "In"), edge(2, "Out", 3, "In"),
            edge(3, "out_0", 4, "In"), edge(3, "out_1", 5, "In"),
        ]))
        data = build_quest_graph_data([analyze_graph(graph)])
        menu = "choice-menu:fixture:3"
        twenty = "fixture:3:option:0"
        ten = "fixture:3:option:1"
        linked_children = {
            entry["to"] for entry in data["edges"]
            if entry["from"] == menu and entry["kind"] == "choice_option"
        }

        self.assertEqual({twenty, ten}, linked_children)
        self.assertEqual("20", data["details"][twenty]["rewards"][0]["amount"])
        self.assertEqual("10", data["details"][ten]["rewards"][0]["amount"])

    def test_submenu_return_does_not_link_back_to_every_main_menu_answer(self) -> None:
        graph = parse_graph(self.write_graph([
            node(0, "StartEvent"),
            node(1, "Flow_MultiAnswer", {"#0": None}, answers=["@main"]),
            node(2, "Flow_AddPhraseToBlacklist", {
                "Phrase ID": stored("@main"), "remove": stored(False, "System.Boolean")}),
            node(3, "Flow_MultiAnswer", {"#0": None}, answers=["@submenu_answer"]),
            node(4, "Flow_AddPhraseToBlacklist", {
                "Phrase ID": stored("@submenu_answer"),
                "remove": stored(False, "System.Boolean")}),
        ], [
            edge(0, "Out", 1, "In"), edge(1, "out_0", 2, "In"), edge(2, "Out", 3, "In"),
            edge(3, "out_0", 4, "In"), edge(4, "Out", 1, "In"),
        ]))
        data = build_quest_graph_data([analyze_graph(graph)])
        main = "fixture:1:option:0"
        menu = "choice-menu:fixture:3"
        submenu = "fixture:3:option:0"
        links = {(entry["from"], entry["to"], entry["kind"]) for entry in data["edges"]}

        self.assertIn((main, menu, "choice_menu"), links)
        self.assertIn((menu, submenu, "choice_option"), links)
        self.assertFalse(any(entry["from"] == submenu and entry["kind"] == "choice_menu"
                             for entry in data["edges"]))

    def test_custom_function_return_resumes_call_continuation(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": None}, answers=["@parent"]),
            node(2, "CustomFunctionCall", _sourceOutputUID="function-uid"),
            node(3, "CustomFunctionEvent", _UID="function-uid", identifier="shared_function"),
            node(4, "Flow_Talk", {"Text": stored("inside_function")}),
            node(5, "Return"),
            node(6, "Flow_SetTaskState", {"Task": stored("after_call"), "State": stored("Complete")}),
            node(7, "Flow_UnlockPhrase", {"Phrase": stored("@after_function")}),
            node(8, "Flow_AddPhraseToBlacklist", {
                "Phrase ID": stored("@parent"), "remove": stored(False, "System.Boolean")}),
        ], [
            edge(1, "out_0", 8, "In"), edge(8, "Out", 2, ""),
            edge(2, "", 6, "In"),
            edge(3, "", 4, "In"), edge(4, "On Finished", 5, ""),
            edge(6, "On Finished", 7, "In"),
        ]))
        data = build_quest_graph_data([analyze_graph(graph)])
        parent = data["details"]["fixture:1:option:0"]

        self.assertEqual(["inside_function"], parent["conversations"])
        self.assertEqual([{"task": "after_call", "state": "Complete"}], parent["taskStates"])
        self.assertIn("after_function", parent["phrasesUnlocked"])
        self.assertEqual(["2 -> shared_function (CustomFunctionEvent 3)"], parent["functionCalls"])
        self.assertNotIn("unlock:fixture.json:7", data["details"])

    def test_shared_custom_function_reward_is_one_outcome_with_multiple_callers(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": None, "#1": None},
                 answers=["ask_about_blacksmith", "Leave"]),
            node(2, "CustomFunctionCall", _sourceOutputUID="function-uid"),
            node(3, "CustomFunctionCall", _sourceOutputUID="function-uid"),
            node(4, "CustomFunctionEvent", _UID="function-uid", identifier="shared_reward"),
            node(5, "Flow_DropItem", {"Res_id": stored("letter"), "Amount": stored(1)}),
            node(6, "Return"),
            node(7, "Flow_PlayerEnable"),
            node(8, "Flow_Vendor"),
        ], [
            edge(1, "out_0", 2, "In"), edge(1, "out_1", 3, "In"),
            edge(2, "", 8, "In"), edge(3, "", 7, "In"),
            edge(4, "", 5, "In"), edge(5, "Out", 6, "In"),
        ]))

        data = build_quest_graph_data([analyze_graph(graph)])
        canonical = "fixture:1:option:0"

        self.assertIn(canonical, data["details"])
        self.assertNotIn("fixture:1:option:1", data["details"])
        self.assertEqual(["letter"], [
            reward["item"] for reward in data["details"][canonical]["rewards"]
        ])
        self.assertEqual(
            ["ask_about_blacksmith", "Leave"],
            [variant["phrase"] for variant in data["details"][canonical]["choiceAlternatives"]],
        )

    def test_known_debug_dialogue_graph_is_available_but_marked_hidden_by_default(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": None}, answers=["Say something good"]),
            node(2, "Flow_AddRelation", {"Value": stored(10.0, "System.Single")}),
        ], [edge(1, "out_0", 2, "In")], name="priest_speak"))

        data = build_quest_graph_data([analyze_graph(graph)])
        finding = data["nodes"][0]

        self.assertTrue(finding["isDebug"])
        self.assertTrue(data["details"][finding["id"]]["isDebug"])

    def test_detached_legacy_first_sermon_rewards_are_marked_debug(self) -> None:
        graph = parse_graph(self.write_graph([
            node(100, "Flow_DropItem", {"Res_id": stored("faith"), "Amount": stored(1)}),
        ], [], name="on_start_preaching"))

        data = build_quest_graph_data([analyze_graph(graph)])

        self.assertTrue(data["details"]["on_start_preaching:100"]["isDebug"])

    def test_real_horadric_letter_function_is_not_duplicated_for_leave(self) -> None:
        if not TAVERN_OWNER_DUMP.exists():
            self.skipTest("Companion FlowGraph dump is unavailable")
        data = build_quest_graph_data([analyze_graph(parse_graph(TAVERN_OWNER_DUMP))])
        canonical = data["details"]["npc_tavern owner:13:option:20"]

        self.assertNotIn("npc_tavern owner:13:option:26", data["details"])
        self.assertEqual(
            ["horadric_2_1b", "Leave"],
            [variant["phrase"] for variant in canonical["choiceAlternatives"]],
        )
        self.assertEqual(["bs_letter"], [
            reward["item"] for reward in canonical["rewards"]
        ])

    def test_markdown_is_stable_and_compact(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "CustomEvent"), node(2, "Flow_ParamFlag", {"param": stored("ready")}),
            node(3, "Flow_DropItem", {"Res_id": stored("acid"), "Amount": stored(1)}),
        ], [edge(1, "Out", 2, "In"), edge(2, ">= 1", 3, "In")]))
        analysis = analyze_graph(graph)
        output_a = render_graph(analysis, APWorldIndex(None))
        output_b = render_graph(analysis, APWorldIndex(None))
        self.assertEqual(output_a, output_b)
        self.assertIn("file: fixture.json", output_a)
        self.assertIn("reward_count: 1", output_a)
        self.assertIn("- type: item_drop", output_a)
        self.assertIn("  item: acid", output_a)
        self.assertIn("  amount: 1", output_a)
        self.assertNotIn("Belegpfad", output_a)

        filtered = render_readme([analysis], [], {"item": "missing", "node": None, "target_type": None})
        self.assertIn("Belohnungsoptionen/-pfade: 0", filtered)
        self.assertNotIn("[fixture](fixture.md)", filtered)

    def test_separate_equal_rewards_are_counted_separately(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": {"$type": "AnswerData"}}, answers=["@reward"]),
            node(2, "Flow_AddRelation", {"Value": stored(10.0, "System.Single")}),
            node(3, "Flow_AddRelation", {"Value": stored(10.0, "System.Single")}),
            node(4, "Return"),
        ], [edge(1, "out_0", 2, "In"), edge(2, "Out", 3, "In"), edge(3, "Out", 4, "In")]))
        summary = build_quest_summaries(analyze_graph(graph), {})[0]

        self.assertEqual([10.0, 10.0], summary.add_relations)
        self.assertEqual(2, summary.reward_count)

    def test_inventory_yes_path_is_required_item_but_no_alternative_is_free(self) -> None:
        yes_graph = parse_graph(self.write_graph([
            node(1, "CustomEvent"),
            node(2, "Flow_CreateItem", {
                "item_id": stored("apple"), "value": stored(5.0, "System.Single")}),
            node(3, "Flow_HasItemInInventory", {"Item": None, "Item ID": stored(None)}),
            node(4, "Flow_DropItem", {"Res_id": stored("reward"), "Amount": stored(1)}),
            node(5, "Flow_Talk"),
        ], [
            edge(1, "Out", 3, "In"), edge(2, "Value", 3, "Item", "Item"),
            edge(3, "Yes", 4, "In"), edge(3, "No", 5, "In"),
        ]))
        yes_summary = build_quest_summaries(analyze_graph(yes_graph), {})[0]
        self.assertEqual(["apple x5"], yes_summary.required_items)

        alternative_graph = parse_graph(self.write_graph([
            node(1, "CustomEvent"),
            node(2, "Flow_CreateItem", {
                "item_id": stored("apple"), "value": stored(5.0, "System.Single")}),
            node(3, "Flow_HasItemInInventory", {"Item": None, "Item ID": stored(None)}),
            node(4, "Flow_DropItem", {"Res_id": stored("reward"), "Amount": stored(1)}),
        ], [
            edge(1, "Out", 3, "In"), edge(2, "Value", 3, "Item", "Item"),
            edge(3, "Yes", 4, "In"), edge(3, "No", 4, "In"),
        ]))
        alternative_summary = build_quest_summaries(analyze_graph(alternative_graph), {})[0]
        self.assertFalse(alternative_summary.required_items)

    def test_empty_answer_data_does_not_render_placeholder_requirements(self) -> None:
        graph = parse_graph(self.write_graph([
            node(1, "Flow_MultiAnswer", {"#0": {"$type": "AnswerData"}}, answers=["@reward"]),
            node(2, "Flow_AddRelation", {"Value": stored(10.0, "System.Single")}),
            node(3, "Return"),
        ], [edge(1, "out_0", 2, "In"), edge(2, "Out", 3, "In")]))
        summary = build_quest_summaries(analyze_graph(graph), {})[0]

        self.assertFalse(summary.required_items)
        self.assertFalse(summary.costs)
        self.assertFalse(summary.other_requirements)

    def test_astrologer_charm_no_compact_summary(self) -> None:
        if not COMPANION_DUMP.exists() or not ACTRESS_DUMP.exists():
            self.skipTest("local companion dumps are not available")
        astrologer = analyze_graph(parse_graph(COMPANION_DUMP))
        actress = analyze_graph(parse_graph(ACTRESS_DUMP))
        phrase_unlocks = build_phrase_unlock_index([astrologer, actress])
        summaries = build_quest_summaries(astrologer, phrase_unlocks)
        summary = next(entry for entry in summaries if entry.multi_answer == "@astrologer_charm_no")

        self.assertEqual([10.0], summary.add_relations)
        self.assertEqual("astrologer", summary.relation_rewards[0].npc)
        self.assertEqual("aus Graph-Dateiname abgeleitet", summary.relation_rewards[0].npc_source)
        self.assertEqual([f"astrologer_charm_no_{index}" for index in range(8, 0, -1)], summary.conversations)
        self.assertEqual([("astrologer_daghter", "Complete"), ("astrologer_help", "Visible")], [
            (entry.task, entry.state) for entry in summary.task_states])
        self.assertEqual(["astrologer_charm_no"], summary.phrases_to_blacklist)
        self.assertEqual(["astrologer_charm_no"], summary.required_quests)
        self.assertIn("npc_actress.json:371", summary.phrase_unlock_sources)

    def test_astrologer_reference_option_when_companion_dump_is_available(self) -> None:
        if not COMPANION_DUMP.exists():
            self.skipTest("local companion dump is not available")
        graph = parse_graph(COMPANION_DUMP)
        options = extract_options(graph, ValueResolver(graph))
        option = next(entry for entry in options if entry.multi_answer_node == "44" and entry.index == 3)
        self.assertEqual("@astrologer_acid", option.phrase)
        self.assertEqual("476", option.answer.source.node_id)
        self.assertEqual("acid", option.answer.price.resource_id)
        self.assertEqual(1.0, option.answer.price.amount)
        self.assertEqual("_rel", option.answer.reward.resource_id)
        self.assertEqual(10.0, option.answer.reward.amount)

    def test_gerry_rusty_key_option_requires_beer_and_sand_when_available(self) -> None:
        if not CRAFTING_SKULL_DUMP.exists():
            self.skipTest("local companion dumps are not available")
        analysis = analyze_graph(parse_graph(CRAFTING_SKULL_DUMP))
        summary = next(
            entry for entry in build_quest_summaries(analysis, {})
            if entry.multi_answer == "@souls_s_s2_1_ask"
        )

        self.assertEqual(["cup_beer:1 x1", "sand_river x1"], sorted(summary.required_items))

    def test_astrologer_inventory_keeps_key_drop_and_relation_rewards_when_available(self) -> None:
        if not COMPANION_DUMP.exists():
            self.skipTest("local companion dump is not available")
        analysis = analyze_graph(parse_graph(COMPANION_DUMP))
        self.assertTrue(any(
            finding.node_id == "163" and finding.resource_id == "quest_key_astrologer"
            for finding in analysis.findings))
        self.assertTrue(any(finding.node_id == "742" and finding.kind == "relation"
                            for finding in analysis.findings))
        self.assertTrue(any(finding.node_id == "774" and finding.kind == "relation"
                            for finding in analysis.findings))
        self.assertTrue(any(finding.option and finding.option.phrase == "@astrologer_acid"
                            for finding in analysis.findings))

    def test_astrologer_gold_unlock_is_connected_to_silver_option_when_available(self) -> None:
        if not COMPANION_DUMP.exists():
            self.skipTest("local companion dump is not available")
        data = build_quest_graph_data([analyze_graph(parse_graph(COMPANION_DUMP))])
        links = {(entry["from"], entry["to"], entry["kind"]) for entry in data["edges"]}

        silver = "npc_astrologer:44:option:10"
        unlock = "unlock:npc_astrologer.json:947"
        gold = "npc_astrologer:44:option:11"
        self.assertIn((silver, unlock, "state_event"), links)
        self.assertIn((unlock, gold, "phrase"), links)

    def test_souls_repairs_are_joined_by_player_flags_when_available(self) -> None:
        if not COMPANION_DUMP.exists():
            self.skipTest("local companion dumps are not available")
        dump_root = COMPANION_DUMP.parent
        paths = [
            dump_root / "on_fix_beehouse_decor_broken.json",
            dump_root / "on_fix_egg_seller_broken.json",
            dump_root / "on_fix_mf_potter_wheel_1_decor_broken.json",
        ]
        if not all(path.exists() for path in paths):
            self.skipTest("local Souls repair dumps are not available")
        data = build_quest_graph_data([analyze_graph(parse_graph(path)) for path in paths])
        links = {(entry["from"], entry["to"], entry["label"]) for entry in data["edges"]}
        beehouse = "unlock:on_fix_beehouse_decor_broken.json:22"
        egg = "unlock:on_fix_egg_seller_broken.json:16"
        potter = "unlock:on_fix_mf_potter_wheel_1_decor_broken.json:16"

        self.assertIn((egg, beehouse, "fixed_egg_seller_broken (sets)"), links)
        self.assertIn((potter, beehouse, "fixed_potters_wheel (sets)"), links)
        self.assertIn((beehouse, egg, "fixed_beehouses_broken (sets)"), links)

    def test_actress_singing_charm_continues_into_nested_choice_when_available(self) -> None:
        if not ACTRESS_DUMP.exists():
            self.skipTest("local companion dump is not available")
        data = build_quest_graph_data([analyze_graph(parse_graph(ACTRESS_DUMP))])
        parent = "npc_actress:30:option:12"
        menu = "choice-menu:npc_actress:968"
        children = {"npc_actress:968:option:0"}
        linked_children = {
            entry["to"] for entry in data["edges"]
            if entry["from"] == menu and entry["kind"] == "choice_option"
        }

        self.assertTrue(any(entry["from"] == parent and entry["to"] == menu
                            and entry["kind"] == "choice_menu" for entry in data["edges"]))
        self.assertEqual(children, linked_children)
        self.assertNotIn("npc_actress:968:option:1", data["details"])
        self.assertNotIn("npc_actress:968:option:2", data["details"])
        details = data["details"]["npc_actress:968:option:0"]
        self.assertIn({"task": "dlc_stories_persuade_charm", "state": "Complete"},
                      details["taskStates"])
        self.assertIn({"task": "dlc_stories_krezvold_after_charm", "state": "Visible"},
                      details["taskStates"])
        self.assertIn("tr_quest_8_krez_after_charm_1", details["phrasesUnlocked"])
        self.assertEqual([
            "tr_quest_8_singing_charm_7a",
            "tr_quest_8_singing_charm_7b",
            "@tr_quest_8_singing_charm_8",
        ], [
            entry["phrase"] for entry in details["choiceAlternatives"]])
        self.assertEqual(["tr_quest_8_singing_charm_7c"],
                         details["choiceAlternatives"][2]["viaPhrases"])

    def test_tavern_skull_calls_return_to_their_quest_continuations_when_available(self) -> None:
        if not TAVERN_SKULL_DUMP.exists():
            self.skipTest("local tavern skull dump is not available")
        data = build_quest_graph_data([analyze_graph(parse_graph(TAVERN_SKULL_DUMP))])
        loose_calls = [
            node for node in data["nodes"]
            if node["graph"] == "tavern_skull" and "CustomFunctionCall" in node["label"]
        ]
        sixth_cutscene = data["details"]["tavern_skull:15:option:6"]

        self.assertFalse(loose_calls)
        self.assertIn("gerry_before_7cs_1", sixth_cutscene["phrasesUnlocked"])
        self.assertIn("800 -> send_player_to_machine (CustomFunctionEvent 551)",
                      sixth_cutscene["functionCalls"])
        self.assertIn("805 -> time_machine_start_anim (CustomFunctionEvent 464)",
                      sixth_cutscene["functionCalls"])
        self.assertIn("833 -> time_machine_stop_anim (CustomFunctionEvent 473)",
                      sixth_cutscene["functionCalls"])

    def test_inquisitor_shared_graveyard_answers_are_not_duplicated(self) -> None:
        if not INQUISITOR_DUMP.exists():
            self.skipTest("local inquisitor dump is not available")
        data = build_quest_graph_data([analyze_graph(parse_graph(INQUISITOR_DUMP))])

        for phrase in ("inquisitor_grave_1_1", "inquisitor_grave_2_1", "inquisitor_grave_2a"):
            matching = [node for node in data["nodes"] if node["label"] == phrase]
            self.assertEqual(1, len(matching), phrase)
            self.assertEqual(["736", "843"],
                             data["details"][matching[0]["id"]]["multiAnswerNodes"])

    def test_gypsy_rat_dialogue_relay_collapses_into_one_reward_outcome(self) -> None:
        if not GYPSY_DUMP.exists():
            self.skipTest("local gypsy dump is not available")
        data = build_quest_graph_data([analyze_graph(parse_graph(GYPSY_DUMP))])
        menu = "choice-menu:npc_gypsy:312"
        rat_outcomes = [
            node for node in data["nodes"]
            if node["label"].startswith("tr_quest_18_baron_rat_9")
        ]

        self.assertEqual(1, len(rat_outcomes))
        outcome = rat_outcomes[0]["id"]
        self.assertEqual({"rat_for_dig"}, {
            reward["item"] for reward in data["details"][outcome]["rewards"]
            if reward["type"] == "item_drop"
        })
        self.assertEqual(
            ["tr_quest_18_baron_rat_9", "@tr_quest_18_baron_rat_12"],
            [value["phrase"] for value in data["details"][outcome]["choiceAlternatives"]],
        )
        second = data["details"][outcome]["choiceAlternatives"][1]
        self.assertEqual(["tr_quest_18_baron_rat_11"], second["viaPhrases"])
        self.assertNotIn("npc_gypsy:312:option:1", data["details"])
        self.assertNotIn("npc_gypsy:11:option:6", data["details"])
        self.assertTrue(any(
            edge["from"] == menu and edge["to"] == outcome and edge["kind"] == "choice_option"
            for edge in data["edges"]
        ))
