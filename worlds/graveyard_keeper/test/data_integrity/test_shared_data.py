import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from ...data import data, load_json_data
from ...world import GraveyardKeeperWorld, WORLD_VERSION


class TestSharedData(unittest.TestCase):
    def test_manifest_has_positive_data_version(self):
        version = load_json_data("manifest.json")["data_version"]
        self.assertIs(type(version), int)
        self.assertGreater(version, 0)

    def test_runtime_items_come_from_shared_item_definitions(self):
        self.assertEqual(
            {item.label for item in data.items.values()},
            set(GraveyardKeeperWorld.item_name_to_id),
        )

    def test_item_grants_cover_every_shared_item(self):
        self.assertEqual(set(data.items), set(load_json_data("item_grants.json")))

    def test_slot_data_advertises_shared_data_version(self):
        fake_world = SimpleNamespace(options=MagicMock())
        fake_world.options.as_dict.return_value = {
            "goal": 0, "stranger_sins": 0, "game_of_crone": 0, "better_save_soul": 0,
        }
        slot_data = GraveyardKeeperWorld.fill_slot_data(fake_world)
        self.assertEqual(load_json_data("manifest.json")["data_version"], slot_data["graveyard_keeper_data_version"])

    def test_slot_data_advertises_goal_and_world_version(self):
        fake_world = SimpleNamespace(options=MagicMock())
        fake_world.options.as_dict.return_value = {
            "goal": 0, "stranger_sins": 0, "game_of_crone": 0, "better_save_soul": 0,
        }

        slot_data = GraveyardKeeperWorld.fill_slot_data(fake_world)

        self.assertEqual(0, slot_data["goal"])
        self.assertEqual(WORLD_VERSION, slot_data["client_version"])

    def test_public_location_ids_are_nonzero_and_contiguous(self):
        location_ids = sorted(GraveyardKeeperWorld.location_name_to_id.values())
        self.assertEqual(list(range(1, len(location_ids) + 1)), location_ids)


if __name__ == "__main__":
    unittest.main()
