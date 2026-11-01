import json
import unittest
from pathlib import Path

import importlib_resources

from ...data import load_json_data


GAME_DATA_ROOT = Path(__file__).parents[2] / "dumps" / "raw"


class TestItemGrants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_items = {}
        item_root = importlib_resources.files("worlds.graveyard_keeper") / "data" / "shared" / "items"
        for item_file in sorted(item_root.rglob("*.json"), key=str):
            if "unused" in item_file.parts:
                continue
            file_items = load_json_data("items/" + str(item_file.relative_to(item_root)))
            overlap = cls.raw_items.keys() & file_items.keys()
            if overlap:
                raise AssertionError(f"Duplicate item definitions: {sorted(overlap)}")
            cls.raw_items.update(file_items)
        cls.raw_grants = load_json_data("item_grants.json")

    def test_every_declared_item_has_exactly_one_grant_definition(self):
        self.assertEqual(self.raw_items.keys(), self.raw_grants.keys())

    def test_item_grants_use_supported_type_specific_schema(self):
        schemas = {
            "game_item": ({"item_id"}, set()),
            "craft_unlock": ({"craft_ids"}, set()),
            "progressive_craft_unlock": ({"stages"}, set()),
            "work_unlock": ({"work_ids", "perk_ids"}, set()),
            "progressive_work_unlock": ({"stages"}, set()),
            "perk_unlock": ({"perk_id", "craft_ids", "work_ids"}, set()),
            "permanent_buff": ({"buff_id", "resource_types", "icon"}, set()),
            "relation": ({"npc_id", "amount"}, set()),
            "research_points": ({"color", "amount"}, set()),
            "technology_unlock": ({"technology_ids"}, set()),
            "flow_script": ({"script_id"}, set()),
            "trap": ({"trap_id"}, set()),
            "TODO": ({"reason"}, set()),
        }
        for item_key, grant in self.raw_grants.items():
            with self.subTest(item=item_key):
                self.assertIsInstance(grant, dict)
                self.assertIn(grant.get("type"), schemas)
                required, optional = schemas[grant["type"]]
                self.assertFalse(required - grant.keys())
                self.assertFalse(grant.keys() - required - optional - {"type"})

    def test_scalar_grant_fields_have_valid_values(self):
        string_fields = {
            "item_id", "perk_id", "buff_id", "npc_id", "color", "reason", "script_id", "trap_id",
        }
        for item_key, grant in self.raw_grants.items():
            for field in string_fields & grant.keys():
                with self.subTest(item=item_key, field=field):
                    self.assertIsInstance(grant[field], str)
                    self.assertTrue(grant[field].strip())
            if "amount" in grant:
                with self.subTest(item=item_key, field="amount"):
                    self.assertIs(type(grant["amount"]), int)
                    self.assertGreater(grant["amount"], 0)

    def test_research_point_grants_use_supported_colors(self):
        research_grants = {
            item_key: grant
            for item_key, grant in self.raw_grants.items()
            if grant["type"] == "research_points"
        }
        self.assertEqual(
            {
                "ITEM_RED_RESEARCH_POINTS",
                "ITEM_GREEN_RESEARCH_POINTS",
                "ITEM_BLUE_RESEARCH_POINTS",
            },
            research_grants.keys(),
        )
        self.assertEqual(
            {"red", "green", "blue"},
            {grant["color"] for grant in research_grants.values()},
        )

    def test_list_grant_fields_contain_only_unique_strings(self):
        list_fields = {
            "craft_ids", "work_ids", "perk_ids", "resource_types", "technology_ids",
        }
        for item_key, grant in self.raw_grants.items():
            for field in list_fields & grant.keys():
                values = grant[field]
                with self.subTest(item=item_key, field=field):
                    self.assertIsInstance(values, list)
                    self.assertTrue(all(isinstance(value, str) and value for value in values))
                    self.assertEqual(len(values), len(set(values)))

    def test_progressive_stages_are_non_empty_lists_of_unique_ids(self):
        for item_key, grant in self.raw_grants.items():
            if "stages" not in grant:
                continue
            with self.subTest(item=item_key):
                self.assertIsInstance(grant["stages"], list)
                self.assertTrue(grant["stages"])
                for stage in grant["stages"]:
                    self.assertIsInstance(stage, list)
                    self.assertTrue(stage)
                    self.assertTrue(all(isinstance(value, str) and value for value in stage))
                    self.assertEqual(len(stage), len(set(stage)))

    def test_technology_group_grants_match_declared_research_roots(self):
        unlocks = load_json_data("items/unlocks.json")
        technology_grants = {
            item_key: grant
            for item_key, grant in self.raw_grants.items()
            if grant["type"] == "technology_unlock"
        }

        self.assertEqual(unlocks.keys(), technology_grants.keys())
        for item_key, unlock in unlocks.items():
            with self.subTest(item=item_key):
                self.assertEqual(
                    len(unlock["researches"]),
                    len(technology_grants[item_key]["technology_ids"]),
                )

    def test_raw_game_corrections_are_not_regressed_to_old_factory_values(self):
        self.assertEqual("p_big_guy", self.raw_grants["ITEM_PERK_BIG_GUY"]["perk_id"])
        self.assertEqual(
            ["souls_builddesk::soul_healing_for_human"],
            self.raw_grants["ITEM_BP_HUMAN_SOUL_HEALING"]["craft_ids"],
        )
        self.assertEqual("preach_1", self.raw_grants["ITEM_CASUAL_PRAYER"]["item_id"])
        self.assertEqual("global_control", self.raw_grants["ITEM_REMOTE_CRAFTING"]["item_id"])
        self.assertEqual(
            {
                "type": "flow_script",
                "script_id": "elevator_and_supplies_place",
            },
            self.raw_grants["ITEM_BP_CRATE_FACTORY"],
        )

    def test_technology_grant_ids_exist_in_raw_game_data_when_available(self):
        techs_path = GAME_DATA_ROOT / "techs_data.json"
        if not techs_path.exists():
            self.skipTest("local raw technology dump is not available")
        technology_ids = {
            technology["id"]
            for technology in json.loads(techs_path.read_text(encoding="utf-8-sig"))
        }
        for item_key, grant in self.raw_grants.items():
            if grant["type"] != "technology_unlock":
                continue
            for technology_id in grant["technology_ids"]:
                with self.subTest(item=item_key, technology=technology_id):
                    self.assertIn(technology_id, technology_ids)

    def test_game_item_grant_ids_exist_in_raw_game_data_when_available(self):
        items_path = GAME_DATA_ROOT / "items_data.json"
        if not items_path.exists():
            self.skipTest("local raw item dump is not available")
        game_item_ids = {
            item["id"]
            for item in json.loads(items_path.read_text(encoding="utf-8-sig"))
        }
        for item_key, grant in self.raw_grants.items():
            if grant["type"] != "game_item":
                continue
            with self.subTest(item=item_key, game_item=grant["item_id"]):
                self.assertIn(grant["item_id"], game_item_ids)

    def test_item_grants_have_no_unresolved_todos(self):
        unresolved = {
            item_key: grant["reason"]
            for item_key, grant in self.raw_grants.items()
            if grant["type"] == "TODO"
        }
        self.assertEqual({}, unresolved)


if __name__ == "__main__":
    unittest.main()
