import importlib
import importlib.util
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from importlib.resources import files

from .. import items
from ..world import GraveyardKeeperWorld


data_module = importlib.import_module("worlds.graveyard_keeper.data")


def load_items_module_with_definitions(definitions):
    spec = importlib.util.spec_from_file_location(
        "worlds.graveyard_keeper._item_id_regression", items.__file__,
    )
    module = importlib.util.module_from_spec(spec)
    with patch.object(data_module.data, "items", definitions):
        spec.loader.exec_module(module)
    return module


class TestStableItemIds(unittest.TestCase):
    def test_shared_file_enumeration_cannot_change_item_pool_order(self):
        root = files(data_module.__package__).joinpath("data", "shared", "items")
        expected = list(data_module.load_items())
        original_iterdir = type(root).iterdir

        def reversed_entries(path):
            return iter(reversed(sorted(original_iterdir(path), key=lambda entry: entry.name)))

        with patch.object(type(root), "iterdir", reversed_entries):
            self.assertEqual(expected, list(data_module.load_items()))

    def test_reordered_shared_files_and_definitions_preserve_public_and_created_ids(self):
        root = files(data_module.__package__).joinpath("data", "shared", "items")
        paths = list(data_module.iter_json_files(root))
        with patch.object(data_module, "iter_json_files", return_value=iter(reversed(paths))):
            reordered = data_module.load_items()
        permutations = (reordered, dict(reversed(list(data_module.data.items.items()))))
        for definitions in permutations:
            module = load_items_module_with_definitions(definitions)
            self.assertEqual(GraveyardKeeperWorld.item_name_to_id, module.ITEM_NAME_TO_ID)
            world = SimpleNamespace(player=1)
            for name, code in GraveyardKeeperWorld.item_name_to_id.items():
                with self.subTest(name=name):
                    item = module.create_item_with_correct_classification(world, name)
                    self.assertEqual(code, item.code)

    def test_existing_network_ids_and_specific_traps_are_preserved(self):
        expected = {
            "Blueprint: Burning Witch": 1,
            "Blueprint: Bishop's Choice": 2,
            "Ms. Charm Monroe": 4,
            "Bats Trap": 488,
            "Green Slime Trap": 489,
        }
        for name, code in expected.items():
            with self.subTest(name=name):
                self.assertEqual(code, GraveyardKeeperWorld.item_name_to_id[name])

    def test_missing_or_unknown_mapping_entries_are_rejected(self):
        stable_ids = data_module.load_json_data("item_ids.json")
        key = next(iter(stable_ids))
        missing = dict(stable_ids)
        del missing[key]
        with self.assertRaisesRegex(ValueError, f"missing=.*{key}"):
            items._build_item_name_to_id(data_module.data.items, missing)
        with self.assertRaisesRegex(ValueError, "unknown=.*ITEM_UNKNOWN"):
            items._build_item_name_to_id(data_module.data.items, stable_ids | {"ITEM_UNKNOWN": 490})

    def test_duplicate_ids_and_duplicate_network_names_are_rejected(self):
        stable_ids = data_module.load_json_data("item_ids.json")
        first, second = list(stable_ids)[:2]
        with self.assertRaisesRegex(ValueError, "IDs must be unique"):
            items._build_item_name_to_id(data_module.data.items, stable_ids | {second: stable_ids[first]})
        duplicate_name = dict(data_module.data.items)
        duplicate_name[second] = replace(duplicate_name[second], label=duplicate_name[first].label)
        with self.assertRaisesRegex(ValueError, "names must be unique"):
            items._build_item_name_to_id(duplicate_name, stable_ids)

    def test_ids_must_be_positive_integers(self):
        stable_ids = data_module.load_json_data("item_ids.json")
        key = next(iter(stable_ids))
        for invalid in (True, False, 0, -1, 1.0, "1", None):
            with self.subTest(value=invalid), self.assertRaisesRegex(ValueError, "positive integer"):
                items._build_item_name_to_id(data_module.data.items, stable_ids | {key: invalid})

    def test_shared_explicit_ids_cannot_disagree_with_the_network_table(self):
        stable_ids = data_module.load_json_data("item_ids.json")
        key = "ITEM_BATS_TRAP"
        with self.assertRaisesRegex(ValueError, "conflicts with shared explicit ID"):
            items._build_item_name_to_id(data_module.data.items, stable_ids | {key: 490})
        definitions = dict(data_module.data.items)
        key = "ITEM_BP_BURNING_WITCH"
        definitions[key] = replace(definitions[key], code=True)
        with self.assertRaisesRegex(ValueError, "conflicts with shared explicit ID"):
            items._build_item_name_to_id(definitions, stable_ids)

