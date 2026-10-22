import json
import tempfile
import unittest
from pathlib import Path

from ...data import data
from ...tools.build_client_contract import DEFAULT_OUTPUT, build_client_contract, write_client_contract
from ...world import GraveyardKeeperWorld


class TestClientContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = build_client_contract()

    def test_checked_in_contract_matches_its_source_data(self):
        checked_in = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8-sig"))
        self.assertEqual(self.contract, checked_in)

    def test_network_names_are_unique(self):
        for section in ("items", "locations"):
            with self.subTest(section=section):
                names = [entry["name"] for entry in self.contract[section].values()]
                self.assertEqual(len(names), len(set(names)))

    def test_contract_contains_every_public_network_name(self):
        self.assertEqual(
            set(GraveyardKeeperWorld.item_name_to_id),
            {item["name"] for item in self.contract["items"].values()},
        )
        self.assertEqual(
            set(GraveyardKeeperWorld.location_name_to_id),
            {location["name"] for location in self.contract["locations"].values()},
        )

    def test_public_location_ids_are_nonzero_and_contiguous(self):
        location_ids = sorted(GraveyardKeeperWorld.location_name_to_id.values())
        self.assertEqual(list(range(1, len(location_ids) + 1)), location_ids)

    def test_public_location_ids_match_runtime_creation_order(self):
        expected = {}
        next_id = 1
        for region in data.regions.values():
            for location_key in region.locations:
                expected[data.locations[location_key].label] = next_id
                next_id += 1
        self.assertEqual(expected, GraveyardKeeperWorld.location_name_to_id)

    def test_every_item_exposes_its_complete_client_grant(self):
        self.assertTrue(self.contract["items"])
        for item_key, item in self.contract["items"].items():
            with self.subTest(item=item_key):
                self.assertEqual(
                    {"name", "dlc", "classification", "amount", "grant"},
                    item.keys(),
                )
                self.assertNotEqual("TODO", item["grant"]["type"])

    def test_every_location_exposes_trigger_metadata_without_requiring_it(self):
        self.assertTrue(self.contract["locations"])
        for location_key, location in self.contract["locations"].items():
            with self.subTest(location=location_key):
                self.assertEqual(
                    {"name", "dlc", "parent_region", "triggers"},
                    location.keys(),
                )
                self.assertIsInstance(location["triggers"], list)

    def test_writer_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first.json"
            second = Path(temp_dir) / "second.json"
            write_client_contract(first)
            write_client_contract(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
