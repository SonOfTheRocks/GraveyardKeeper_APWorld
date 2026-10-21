import unittest

import importlib_resources

from ...data import load_json_data


class TestItemGrants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_items = {}
        item_root = importlib_resources.files("worlds.graveyard_keeper") / "data" / "items"
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
        string_fields = {"item_id", "perk_id", "buff_id", "npc_id", "reason"}
        for item_key, grant in self.raw_grants.items():
            for field in string_fields & grant.keys():
                with self.subTest(item=item_key, field=field):
                    self.assertIsInstance(grant[field], str)
                    if grant["type"] != "game_item" or item_key not in {
                        "ITEM_CASUAL_PRAYER",
                        "ITEM_REMOTE_CRAFTING",
                    }:
                        self.assertTrue(grant[field].strip())
            if "amount" in grant:
                with self.subTest(item=item_key, field="amount"):
                    self.assertIs(type(grant["amount"]), int)
                    self.assertGreater(grant["amount"], 0)

    def test_list_grant_fields_contain_only_unique_strings(self):
        list_fields = {"craft_ids", "work_ids", "perk_ids", "resource_types"}
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


if __name__ == "__main__":
    unittest.main()
