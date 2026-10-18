import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from ...data import data, load_json_data
from ...models import LocationTriggerData, QuestEventData
from ...world import GraveyardKeeperWorld


FLOW_DUMP_ROOT = Path(
    r"C:\Users\Kai\RiderProjects\GraveyardKeepelago\GraveyardKeepelago\Dumps\FlowGraphExports"
)
GAME_DATA_ROOT = Path(__file__).parents[2] / "dumps" / "raw"


class TestQuestLocationTriggers(unittest.TestCase):
    @staticmethod
    def _serialized_triggers(location_key):
        return [trigger.to_slot_data() for trigger in data.locations[location_key].triggers]

    def test_every_quest_reward_location_has_triggers_or_an_explicit_todo(self):
        reward_locations = {
            location
            for event in data.events.values()
            if isinstance(event, QuestEventData)
            for location in event.rewards
        }
        incomplete = {
            location: data.locations[location].trigger_todo
            for location in reward_locations
            if not data.locations[location].triggers and not data.locations[location].trigger_todo
        }
        self.assertFalse(incomplete, f"Quest reward locations without trigger metadata: {incomplete}")

    def test_only_the_known_clay_pot_legacy_location_has_a_trigger_todo(self):
        todos = {
            location_key: location.trigger_todo
            for location_key, location in data.locations.items()
            if location.trigger_todo is not None
        }
        self.assertEqual(
            {"LOCATION_REWARD_TIME_MACHINE_ITEM_14_2"},
            set(todos),
            f"Resolve existing trigger TODOs before adding new ones: {todos}",
        )

    def test_trigger_metadata_is_only_attached_to_quest_reward_locations(self):
        reward_locations = {
            location
            for event in data.events.values()
            if isinstance(event, QuestEventData)
            for location in event.rewards
        }
        unexpected = {
            location_key
            for location_key, location in data.locations.items()
            if (location.triggers or location.trigger_todo) and location_key not in reward_locations
        }
        self.assertFalse(unexpected)

    def test_location_triggers_are_unique_and_serialize_without_null_fields(self):
        for location_key, location in data.locations.items():
            serialized = [trigger.to_slot_data() for trigger in location.triggers]
            with self.subTest(location=location_key):
                self.assertEqual(len(serialized), len({
                    json.dumps(trigger, sort_keys=True) for trigger in serialized
                }))
                self.assertTrue(all(value is not None for trigger in serialized for value in trigger.values()))

    def test_raw_location_trigger_schema_uses_only_supported_type_specific_fields(self):
        required_fields = {
            "flow_quest_reward": {"graph", "node_id"},
            "flow_relation_reward": {"graph", "node_id"},
            "craft_reward": {"craft_id"},
            "world_item_reward": {"item_id"},
            "technology_reward": {"technology_id"},
        }
        raw_locations = load_json_data("locations.json")
        for location_key, location in raw_locations.items():
            for index, trigger in enumerate(location.get("triggers", [])):
                with self.subTest(location=location_key, trigger=index):
                    self.assertIn(trigger.get("type"), required_fields)
                    allowed = required_fields[trigger["type"]] | {"type"}
                    if trigger["type"].startswith("flow_"):
                        allowed.add("answer_index")
                    self.assertFalse(required_fields[trigger["type"]] - trigger.keys())
                    self.assertFalse(trigger.keys() - allowed)

    def test_relation_and_non_relation_flow_rewards_remain_distinguishable(self):
        trigger_types = {
            trigger.type
            for location in data.locations.values()
            for trigger in location.triggers
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
                        trigger.answer_index
                        for trigger in data.locations[location_key].triggers
                    },
                )

        farmer_triggers = self._serialized_triggers(
            "LOCATION_FARMER_REWARD_REACT_TO_SONS_SECRET_DRINKING"
        )
        self.assertIn(
            {
                "type": "flow_relation_reward",
                "graph": "farmer_comes_to_pl_house",
                "node_id": "21",
            },
            farmer_triggers,
        )
        self.assertIn(
            {
                "type": "flow_relation_reward",
                "graph": "npc_farmer",
                "node_id": "15",
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
                triggers = data.locations[location_key].triggers
                self.assertTrue(all(trigger.type == "flow_relation_reward" for trigger in triggers))
                self.assertIn(1, {trigger.answer_index for trigger in triggers})

    def test_real_flow_trigger_nodes_and_answer_indexes_exist_when_dumps_are_available(self):
        if not FLOW_DUMP_ROOT.exists():
            self.skipTest("local companion FlowGraph exports are not available")
        graphs = {}
        for location_key, location in data.locations.items():
            for trigger in location.triggers:
                if not trigger.type.startswith("flow_"):
                    continue
                graph_nodes = graphs.get(trigger.graph)
                if graph_nodes is None:
                    graph_path = FLOW_DUMP_ROOT / f"{trigger.graph}.json"
                    self.assertTrue(graph_path.exists(), f"Missing graph for {location_key}: {graph_path}")
                    graph = json.loads(graph_path.read_text(encoding="utf-8-sig"))
                    graph_nodes = {
                        node.get("$id"): node for node in graph["nodes"] if node.get("$id") is not None
                    }
                    graphs[trigger.graph] = graph_nodes
                with self.subTest(location=location_key, graph=trigger.graph, node=trigger.node_id):
                    self.assertIn(trigger.node_id, graph_nodes)
                    node = graph_nodes[trigger.node_id]
                    if "MultiAnswer" in node["$type"]:
                        self.assertIsNotNone(
                            trigger.answer_index,
                            f"MultiAnswer trigger must identify the selected answer: {location_key}",
                        )
                    if trigger.answer_index is not None:
                        self.assertIn("MultiAnswer", node["$type"])
                        self.assertLess(trigger.answer_index, len(node.get("answers", [])))

    def test_non_flow_trigger_ids_exist_in_game_data_when_dumps_are_available(self):
        dump_files = {
            "craft_reward": ("craft_data.json", "craft_id"),
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
            ids["craft_reward"].update({
                row["id"]
                for row in json.loads(craft_objects_path.read_text(encoding="utf-8-sig"))
            })
        for location_key, location in data.locations.items():
            for trigger in location.triggers:
                if trigger.type not in dump_files:
                    continue
                field_name = dump_files[trigger.type][1]
                trigger_id = getattr(trigger, field_name)
                with self.subTest(location=location_key, trigger_type=trigger.type, trigger_id=trigger_id):
                    self.assertIn(trigger_id, ids[trigger.type])


class TestLocationTriggerSerialization(unittest.TestCase):
    def test_serialization_uses_only_fields_relevant_to_the_trigger_type(self):
        trigger = LocationTriggerData(
            type="flow_relation_reward", graph="npc_bishop", node_id="75", answer_index=2,
        )
        self.assertEqual(
            {
                "type": "flow_relation_reward",
                "graph": "npc_bishop",
                "node_id": "75",
                "answer_index": 2,
            },
            trigger.to_slot_data(),
        )

    def test_slot_data_contains_only_enabled_addressable_location_triggers(self):
        enabled_label = data.locations["LOCATION_BISHOP_REWARD_FIX_THE_GRAVEYARD_1"].label
        disabled_label = data.locations["LOCATION_GAME_OF_CRONE_REWARD_COMPLETE_STORY"].label
        fake_world = SimpleNamespace(
            player=1,
            options=MagicMock(),
            multiworld=MagicMock(),
        )
        fake_world.options.as_dict.return_value = {
            "stranger_sins": 0,
            "game_of_crone": 0,
            "better_save_soul": 0,
        }
        fake_world.multiworld.get_locations.return_value = [
            SimpleNamespace(name=enabled_label, address=1),
            SimpleNamespace(name=disabled_label, address=None),
        ]

        slot_data = GraveyardKeeperWorld.fill_slot_data(fake_world)

        fake_world.options.as_dict.assert_called_once_with(
            "stranger_sins", "game_of_crone", "better_save_soul",
        )
        self.assertEqual(1, slot_data["quest_location_triggers"]["version"])
        self.assertEqual(
            {enabled_label},
            set(slot_data["quest_location_triggers"]["locations"]),
        )
