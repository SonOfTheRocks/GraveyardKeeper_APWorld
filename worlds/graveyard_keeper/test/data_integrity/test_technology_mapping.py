import json
import unittest
from pathlib import Path

from ...data import data, load_json_data, active_research_locations


class TestTechnologyMapping(unittest.TestCase):
    def test_all_research_regions_have_exactly_their_existing_locations(self):
        technologies = load_json_data("technologies.json")
        regions = {key: value for key, value in data.regions.items()
                   if key.startswith("REGION_TECH_TREE") and "/" in key}
        self.assertEqual(set(regions), {value["region"] for value in technologies.values()})
        self.assertEqual(184, len(technologies))
        all_locations = []
        for game_id, technology in technologies.items():
            with self.subTest(game_id=game_id):
                region = regions[technology["region"]]
                expected = [data.locations[key].label for key in region.locations]
                self.assertEqual(expected, technology["locations"])
                count = 0 if "quest_reward" in technology else 1 if "recipe_item" in technology else 3
                self.assertEqual(count, len(expected))
                self.assertEqual(region.dlc.name, technology["dlc"])
                all_locations.extend(expected)
        self.assertEqual(len(all_locations), len(set(all_locations)))
        self.assertEqual(487, len(all_locations))

    def test_quest_technologies_have_no_extra_research_definitions(self):
        for game_id in ("First slice", "Grave plate", "Iron"):
            technology = load_json_data("technologies.json")[game_id]
            self.assertEqual([], technology["locations"])
            self.assertIn(technology["quest_reward"], {value.label for value in data.locations.values()})

    def test_one_check_per_recipe_item_including_bags_and_gravestones(self):
        technologies = load_json_data("technologies.json")
        books = {key: value for key, value in technologies.items() if "recipe_item" in value}
        self.assertEqual(28, len(books))
        self.assertEqual(28, len({value["recipe_item"] for value in books.values()}))
        active = active_research_locations()
        self.assertEqual(487, len(active))
        for technology in books.values():
            self.assertEqual({technology["locations"][0]}, set(technology["locations"]) & active)
        self.assertEqual("recipe_2min", books["2min"]["recipe_item"])
        self.assertIn("Advanced gravestones", books)
        self.assertIn("tech_bag_alchemy", books)

    def test_self_researched_technologies_keep_three_checks(self):
        ordinary = [technology for technology in load_json_data("technologies.json").values()
                    if "recipe_item" not in technology and "quest_reward" not in technology]
        self.assertEqual(153, len(ordinary))
        self.assertTrue(all(len(technology["locations"]) == 3 for technology in ordinary))

    def test_native_parent_ids_exist_and_do_not_form_a_cycle(self):
        technologies = load_json_data("technologies.json")
        def visit(game_id, path):
            self.assertNotIn(game_id, path)
            for parent in technologies[game_id]["parents"]:
                self.assertIn(parent, technologies)
                visit(parent, path | {game_id})
        for game_id in technologies:
            visit(game_id, set())

    def test_spiritualism_labels_keep_existing_special_case(self):
        technologies = load_json_data("technologies.json")
        self.assertNotEqual(technologies["Stone gravestones"]["locations"],
                            technologies["soul_stone_fences"]["locations"])

    def test_client_shared_copy_matches_when_checkout_is_available(self):
        client_copy = Path(__file__).resolve().parents[6] / "RiderProjects" / "GraveyardKeepelago" / "External" / "GraveyardKeeperData" / "technologies.json"
        if not client_copy.exists():
            self.skipTest("Companion client checkout is not available")
        self.assertEqual(load_json_data("technologies.json"), json.loads(client_copy.read_text(encoding="utf-8-sig")))
