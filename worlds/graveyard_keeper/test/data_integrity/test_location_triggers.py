import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from ...data import data, load_json_data
from ...models import QuestEventData
from ...world import GraveyardKeeperWorld
from ..flow_dump import FLOW_DUMP_ROOT


GAME_DATA_ROOT = Path(__file__).parents[2] / "dumps" / "raw"


class TestQuestLocationTriggers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_locations = load_json_data("locations.json")
        cls.raw_triggers = load_json_data("quest_reward_triggers.json")

    def test_every_quest_reward_location_has_triggers(self):
        reward_locations = {
            location
            for event in data.events.values()
            if isinstance(event, QuestEventData)
            for location in event.rewards
        }
        incomplete = {
            location
            for location in reward_locations
            if not self.raw_triggers.get(location)
        }
        self.assertFalse(incomplete, f"Quest reward locations without trigger metadata: {incomplete}")

    def test_no_quest_location_trigger_todos_remain(self):
        todos = {
            location_key: triggers
            for location_key, triggers in self.raw_triggers.items()
            if not triggers
        }
        self.assertFalse(todos, f"Resolve empty trigger mappings before adding new ones: {todos}")

    def test_trigger_metadata_is_only_attached_to_known_locations(self):
        unexpected = {
            location_key
            for location_key in self.raw_triggers
            if location_key not in data.locations
        }
        self.assertFalse(unexpected)

    def test_location_triggers_are_unique_and_contain_no_null_fields(self):
        for location_key, triggers in self.raw_triggers.items():
            with self.subTest(location=location_key):
                self.assertEqual(
                    len(triggers),
                    len({json.dumps(trigger, sort_keys=True) for trigger in triggers}),
                )
                self.assertTrue(all(value is not None for trigger in triggers for value in trigger.values()))

    def test_raw_location_trigger_schema_uses_only_supported_type_specific_fields(self):
        required_fields = {
            "flow_quest_reward": {"graph", "node_id", "runtime_node_id"},
            "flow_relation_reward": {"graph", "node_id", "runtime_node_id"},
            "craft_completion_reward": {"craft_id"},
            "craft_unlock_reward": {"craft_id"},
            "world_item_reward": {"item_id"},
            "technology_reward": {"technology_id"},
        }
        for location_key, triggers in self.raw_triggers.items():
            self.assertIsInstance(triggers, list, location_key)
            for index, trigger in enumerate(triggers):
                with self.subTest(location=location_key, trigger=index):
                    self.assertIsInstance(trigger, dict)
                    self.assertIn(trigger.get("type"), required_fields)
                    allowed = required_fields[trigger["type"]] | {"type"}
                    if trigger["type"].startswith("flow_"):
                        allowed.add("answer_index")
                    self.assertFalse(required_fields[trigger["type"]] - trigger.keys())
                    self.assertFalse(trigger.keys() - allowed)
                    string_fields = required_fields[trigger["type"]] - {"runtime_node_id"}
                    for field_name in string_fields:
                        self.assertIsInstance(trigger[field_name], str)
                        self.assertTrue(trigger[field_name].strip())
                    if "runtime_node_id" in trigger:
                        self.assertIs(type(trigger["runtime_node_id"]), int)
                        self.assertGreater(trigger["runtime_node_id"], 0)
                    if "answer_index" in trigger:
                        self.assertIs(type(trigger["answer_index"]), int)
                        self.assertGreaterEqual(trigger["answer_index"], 0)

    def test_relation_and_non_relation_flow_rewards_remain_distinguishable(self):
        trigger_types = {
            trigger["type"]
            for triggers in self.raw_triggers.values()
            for trigger in triggers
        }
        self.assertIn("flow_relation_reward", trigger_types)
        self.assertIn("flow_quest_reward", trigger_types)

    def test_equivalent_vanilla_routes_are_all_valid_location_triggers(self):
        expected_alternatives = {
            "LOCATION_INQUISITOR_REWARD_BURN_THE_WITCH_FIREWOOD": {3, 5},
            "LOCATION_INQUISITOR_REWARD_BURN_THE_WITCH_FLYERS": {4, 6},
            "LOCATION_INQUISITOR_REWARD_GET_GRAVEYARD_EXPANSION_PERMISSION": {1, 2},
            "LOCATION_FARMER_REWARD_RECOVER_BELLAS_RING": {0, 7},
        }
        for location_key, answer_indexes in expected_alternatives.items():
            with self.subTest(location=location_key):
                self.assertEqual(
                    answer_indexes,
                    {
                        trigger["answer_index"]
                        for trigger in self.raw_triggers[location_key]
                    },
                )

        farmer_triggers = self.raw_triggers["LOCATION_FARMER_REWARD_REACT_TO_SONS_SECRET_DRINKING"]
        self.assertIn(
            {
                "type": "flow_relation_reward",
                "graph": "farmer_comes_to_pl_house",
                "node_id": "21",
                "runtime_node_id": 10,
            },
            farmer_triggers,
        )
        self.assertIn(
            {
                "type": "flow_relation_reward",
                "graph": "npc_farmer",
                "node_id": "15",
                "runtime_node_id": 6,
                "answer_index": 3,
            },
            farmer_triggers,
        )

    def test_clotho_health_potion_route_checks_the_three_equivalent_relation_rewards(self):
        clotho_locations = (
            "LOCATION_CLOTHO_REWARD_GIVE_CAULDRON",
            "LOCATION_CLOTHO_REWARD_GIVE_HEALTH_POWDER",
            "LOCATION_CLOTHO_REWARD_GIVE_BEE",
        )
        for location_key in clotho_locations:
            with self.subTest(location=location_key):
                triggers = self.raw_triggers[location_key]
                self.assertTrue(all(trigger["type"] == "flow_relation_reward" for trigger in triggers))
                self.assertIn(1, {trigger["answer_index"] for trigger in triggers})

    def test_real_flow_trigger_nodes_and_answer_indexes_exist_when_dumps_are_available(self):
        if not FLOW_DUMP_ROOT.exists():
            self.skipTest("local companion FlowGraph exports are not available")
        graphs = {}
        for location_key, triggers in self.raw_triggers.items():
            for trigger in triggers:
                if not trigger["type"].startswith("flow_"):
                    continue
                graph_name = trigger["graph"]
                graph_data = graphs.get(graph_name)
                if graph_data is None:
                    graph_path = FLOW_DUMP_ROOT / f"{graph_name}.json"
                    self.assertTrue(graph_path.exists(), f"Missing graph for {location_key}: {graph_path}")
                    graph = json.loads(graph_path.read_text(encoding="utf-8-sig"))
                    graph_nodes = {
                        node.get("$id"): node for node in graph["nodes"] if node.get("$id") is not None
                    }
                    runtime_ids = {
                        node.get("$id"): index
                        for index, node in enumerate(graph["nodes"], start=1)
                        if node.get("$id") is not None
                    }
                    graph_data = graph_nodes, runtime_ids
                    graphs[graph_name] = graph_data
                graph_nodes, runtime_ids = graph_data
                node_id = trigger["node_id"]
                with self.subTest(location=location_key, graph=graph_name, node=node_id):
                    self.assertIn(node_id, graph_nodes)
                    self.assertEqual(runtime_ids[node_id], trigger["runtime_node_id"])
                    node = graph_nodes[node_id]
                    answer_index = trigger.get("answer_index")
                    if "MultiAnswer" in node["$type"]:
                        self.assertIsNotNone(
                            answer_index,
                            f"MultiAnswer trigger must identify the selected answer: {location_key}",
                        )
                    if answer_index is not None:
                        self.assertIn("MultiAnswer", node["$type"])
                        self.assertLess(answer_index, len(node.get("answers", [])))

    def test_non_flow_trigger_ids_exist_in_game_data_when_dumps_are_available(self):
        dump_files = {
            "craft_completion_reward": ("craft_data.json", "craft_id"),
            "craft_unlock_reward": ("craft_data.json", "craft_id"),
            "world_item_reward": ("items_data.json", "item_id"),
            "technology_reward": ("techs_data.json", "technology_id"),
        }
        if not all((GAME_DATA_ROOT / file_name).exists() for file_name, _ in dump_files.values()):
            self.skipTest("local raw GameData dumps are not available")
        ids = {
            trigger_type: {
                row["id"] for row in json.loads((GAME_DATA_ROOT / file_name).read_text(encoding="utf-8-sig"))
            }
            for trigger_type, (file_name, _) in dump_files.items()
        }
        craft_objects_path = GAME_DATA_ROOT / "craft_obj_data.json"
        if craft_objects_path.exists():
            craft_ids = {
                row["id"]
                for row in json.loads(craft_objects_path.read_text(encoding="utf-8-sig"))
            }
            ids["craft_completion_reward"].update(craft_ids)
            ids["craft_unlock_reward"].update(craft_ids)
        for location_key, triggers in self.raw_triggers.items():
            for trigger in triggers:
                trigger_type = trigger["type"]
                if trigger_type not in dump_files:
                    continue
                field_name = dump_files[trigger_type][1]
                trigger_id = trigger[field_name]
                with self.subTest(location=location_key, trigger_type=trigger_type, trigger_id=trigger_id):
                    self.assertIn(trigger_id, ids[trigger_type])


class TestLocationTriggersStayOutOfAPWorldRuntime(unittest.TestCase):
    def test_runtime_location_models_do_not_contain_trigger_metadata(self):
        location = data.locations["LOCATION_BISHOP_REWARD_FIX_THE_GRAVEYARD_1"]
        self.assertFalse(hasattr(location, "triggers"))
        self.assertFalse(hasattr(location, "trigger_todo"))

    def test_slot_data_does_not_contain_location_trigger_metadata(self):
        fake_world = SimpleNamespace(options=MagicMock())
        fake_world.options.as_dict.return_value = {
            "stranger_sins": 0,
            "game_of_crone": 0,
            "better_save_soul": 0,
        }

        slot_data = GraveyardKeeperWorld.fill_slot_data(fake_world)

        fake_world.options.as_dict.assert_called_once_with(
            "goal", "graveyard_goal_rating", "stranger_sins", "game_of_crone", "better_save_soul", "trap_percentage",
            "trap_weights",
        )
        self.assertNotIn("quest_location_triggers", slot_data)
        self.assertIn("graveyard_keeper_data_version", slot_data)
