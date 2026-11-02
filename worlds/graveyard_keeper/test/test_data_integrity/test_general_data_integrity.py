import unittest
from typing import FrozenSet, Set

from importlib.resources import files

from BaseClasses import ItemClassification
from ..bases import GraveyardKeeperTestBase
from ...data import data, load_json_data, iter_json_files
from worlds import graveyard_keeper


class TestDataIntegrity(unittest.TestCase):

    def test_region_labels(self):
        regions_json = load_json_data("regions.json")
        for region_name, region_data in regions_json.items():
            self.assertTrue(
                "label" in region_data,
                f"region '{region_name}' does not have label!"
            )

    def test_regions_exits_exist(self):
        regions_json = load_json_data("regions.json")
        region_names = list(regions_json.keys())
        for region_name, region_data in regions_json.items():
            for exit_region in region_data["exits"]:
                self.assertTrue(
                    exit_region in region_names,
                    f"exit '{exit_region}' does not exist! (found in region '{region_name}')"
                )

    def test_regions_exits_double_linking(self):
        regions_json = load_json_data("regions.json")
        for region_name, region_data in regions_json.items():
            for exit_region in region_data["exits"]:
                self.assertTrue(
                    region_name in regions_json[exit_region]["exits"],
                    f"region '{exit_region}' does not link back to '{region_name}'"
                )

    def test_region_event_linking(self):
        regions_json = load_json_data("regions.json")
        events_in_regions = set([event for region in regions_json.values() for event in region["events"]])
        events_json = load_json_data("quest_events.json")
        events_in_events = list(events_json.keys())
        self.assertEqual(sorted(events_in_regions), sorted(events_in_events))

    def test_region_location_linking(self):
        locations_in_regions = {location for region in data.regions.values() for location in region.locations}
        locations_in_data = set(data.locations.keys())

        missing_from_data = locations_in_regions - locations_in_data
        missing_from_regions = locations_in_data - locations_in_regions

        print(f"locations_in_regions: {locations_in_regions}")
        print(f"locations_in_data: {locations_in_data}")

        self.assertFalse(
            missing_from_data or missing_from_regions,
            "\n".join([
                "Region/location linking is inconsistent:",
                f"  Missing from data.locations: {sorted(missing_from_data)}",
                f"  Missing from regions: {sorted(missing_from_regions)}",
            ])
        )

    def test_unlocks_exists(self):
        techs = [t for t in load_json_data("regions.json").keys() if t.startswith("REGION_TECH")]
        unlocks_json = load_json_data("items/unlocks.json")
        for unlock_name, unlock_data in unlocks_json.items():
            for tech_ref in unlock_data["unlocks"]:
                self.assertTrue(
                    tech_ref in techs,
                    f"unlock '{tech_ref}' does not exist! (found in unlock '{unlock_name}')"
                )

    def test_unlocks_have_progression_classification(self):
        unlocks_json = load_json_data("items/unlocks.json")
        for unlock_name, unlock_json in unlocks_json.items():
            self.assertEqual(
                unlock_json["classification"],
                "PROGRESSION",
                f"unlock '{unlock_name}' does not have PROGRESSION classification!"
            )

    def test_workstations_exist(self):
        crafting_stations = load_json_data("logic/workstations.json").keys()

        crafts_filenames = (entry for entry in files(graveyard_keeper).joinpath("data", "logic", "recipes").iterdir()
                            if entry.is_file() and entry.name.endswith(".json"))
        crafts = {}
        for crafts_filename in crafts_filenames:
            for craft_name, crafts_data_list in load_json_data(crafts_filename).items():
                for craft_data in crafts_data_list:
                    for crafting_station in craft_data["crafting_stations"]:
                        self.assertTrue(
                            crafting_station in crafting_stations,
                            f"workstation '{crafting_station}' does not exist! (found in craft '{craft_name}')"
                        )

    def test_all_blueprints_progression_or_useful_except_paintings(self):
        decorative_items = [
            "ITEM_BP_BURNING_WITCH",
            "ITEM_BP_BISHOPS_CHOICE",
            "ITEM_BP_INQUISITORS_JOY",
            "ITEM_BP_MS_CHARM_MONROE",
            "ITEM_BP_DONKEYS_OF_THE_WORLD_UNITE",
            "ITEM_BP_SPICY_ORANGE"
        ]
        blueprint_filenames = (entry for entry in iter_json_files(files(graveyard_keeper).joinpath("data", "items"))
                               if entry.name == "blueprints.json")
        for blueprint_filename in blueprint_filenames:

            for blueprint_name, blueprint_json in load_json_data(blueprint_filename).items():
                with self.subTest(file=str(blueprint_filename), blueprint=blueprint_name):
                    if blueprint_name in decorative_items:
                        self.assertEqual(
                            blueprint_json["classification"],
                            "FILLER",
                            f"decorative blueprint '{blueprint_name}' doesn't have FILLER classification!"
                        )
                    else:
                        self.assertIn(
                            blueprint_json["classification"],
                            ["PROGRESSION", "USEFUL"],
                            f"blueprint '{blueprint_name}' has invalid classification!"
                        )

    def test_recipes_ingredients_are_valid(self):
        can_be_crafted = data.recipes.keys()

        vendors = load_json_data("logic/vendors.json")
        can_be_bought = set()
        for vendor in data.vendors.values():
            can_be_bought.update(vendor.sells_all)

        blacklist = [
            "ITEM_FACETED_DIAMOND",
            # TODO: GOO
            "ITEM_GOO_OF_DEATH",
            "ITEM_RUINED_BOOK",
            "ITEM_METAL_SCRAP",
            # items given by quest
            "ITEM_KEEPERS_KEY",
            "ITEM_INSTRUCTIONS_FOR_KEY",
            "ITEM_MEMORY_POWDER",
            "ITEM_PIECE_OF_DONKEY_HAIR",
            "ITEM_STAMP",
            "ITEM_SALTY_FORK",
            "ITEM_MIRROR_OF_PRIDE",
            "ITEM_ETERNAL_BURNING_COAL",
            "ITEM_GOLDEN_ANGLE",
            "ITEM_ENDLESS_NOTEBOOK",
            "ITEM_NECKLACE"
        ]

        for output_item_key, recipes in data.recipes.items():
            for recipe in recipes:
                for ingredient in recipe.ingredients:
                    self.assertTrue(
                        ingredient in blacklist \
                        or ingredient in data.items \
                        or ingredient in can_be_crafted \
                        or ingredient in can_be_bought,
                        f"ingredient '{ingredient}' cannot be obtained! (ingredient found for '{output_item_key}')"
                    )

    def test_crafts_require_existing_blueprints(self):
        recipes = data.recipes
        items = data.items.keys()

        for recipes_list in data.recipes.values():
            for recipe in recipes_list:
                if recipe.required_recipe_item:
                    recipe_required = recipe.required_recipe_item
                    if recipe.required_recipe_item in data.progressive_items_reverse.keys():
                        self.assertIn(data.progressive_items_reverse[recipe_required].key, items)
                    else:
                        self.assertIn(recipe_required, items)

    def test_inventory_crafts_need_no_recipes(self):
        # TODO
        return

    def test_all_items_have_dlc_classification(self):
        item_filenames = iter_json_files(files(graveyard_keeper).joinpath("data", "items"))
        for item_filename in item_filenames:
            for item_key, item_data in load_json_data(item_filename).items():
                with self.subTest(file=str(item_filename), item=item_key):
                    self.assertIn("dlc", item_data)
                    self.assertIn(
                        item_data["dlc"],
                        ["BASE_GAME", "GAME_OF_CRONE", "STRANGER_SINS", "BETTER_SAVE_SOUL"]
                    )

    def test_item_classification_for_recipe_requirements(self):
        # TODO: fill this list with all items necessary for quests
        items_needed_for_checks = [
            "ITEM_A_CARVED_PIECE_OF_MARBLE_GOLD",
            "ITEM_A_MUG_OF_BEER_COPPER",
        ]

        required_ap_items: FrozenSet[str] = []
        for item in items_needed_for_checks:
            required_ap_items += GraveyardKeeperTestBase.get_required_ap_items_for(item)

        self.assertNotEqual([], required_ap_items)

        for item_key in required_ap_items:
            if item_key in data.progressive_items_reverse.keys():
                (item_key, _) = data.progressive_items_reverse[item_key]
            expected_classification = ItemClassification.progression

            self.assertEqual(
                expected_classification,
                data.items[item_key].classification,
                f"item '{item_key}' is in necessary crafting rules and therefore must have PROGRESSION classification"
            )