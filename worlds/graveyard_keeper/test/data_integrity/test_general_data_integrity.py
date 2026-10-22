import unittest

import importlib_resources

from BaseClasses import ItemClassification
from ...data import data, load_json_data
from ...items import ITEM_NAME_TO_ID


class TestDataIntegrity(unittest.TestCase):

    def test_happiness_items_use_the_ten_point_logic_quantum(self):
        happiness_items = {
            item_key: item_data
            for item_key, item_data in data.items.items()
            if "_HAPPINESS_" in item_key
        }

        self.assertTrue(happiness_items)
        for item_key, item_data in happiness_items.items():
            with self.subTest(item=item_key):
                self.assertTrue(item_key.endswith("_HAPPINESS_10"))
                self.assertTrue(item_data.label.endswith("Happiness +10"))
                self.assertEqual(10, item_data.amount)
                self.assertEqual(ItemClassification.progression, item_data.classification)

    def test_item_ids_are_unique_and_positive(self):
        item_ids = tuple(ITEM_NAME_TO_ID.values())

        self.assertEqual(len(item_ids), len(set(item_ids)))
        self.assertTrue(item_ids)
        self.assertGreater(min(item_ids), 0)

    def test_region_labels(self):
        regions_json = load_json_data("regions.json")
        for region_name, region_data in regions_json.items():
            self.assertTrue(
                "label" in region_data,
                f"region '{region_name}' does not have label!"
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

        crafts_filenames = importlib_resources.files(__name__).glob("data/logic/recipes/*.json")
        crafts = {}
        for crafts_filename in crafts_filenames:
            for craft_name, crafts_data_list in load_json_data(f"logic/recipes/{crafts_filename}").items():
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
        item_root = importlib_resources.files("worlds.graveyard_keeper") / "data/shared/items"
        blueprint_filenames = item_root.rglob("blueprints.json")
        for blueprint_filename in blueprint_filenames:
            relative_name = str(blueprint_filename.relative_to(item_root))
            for blueprint_name, blueprint_json in load_json_data(f"items/{relative_name}").items():
                with self.subTest(file=blueprint_filename, blueprint=blueprint_name):
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
        item_root = importlib_resources.files("worlds.graveyard_keeper") / "data/shared/items"
        item_filenames = set(item_root.rglob("*.json"))
        for item_filename in item_filenames:
            relative_name = str(item_filename.relative_to(item_root))
            for item_key, item_data in load_json_data(f"items/{relative_name}").items():
                with self.subTest(file=str(item_filename), item=item_key):
                    self.assertIn("dlc", item_data)
                    self.assertIn(
                        item_data["dlc"],
                        ["BASE_GAME", "GAME_OF_CRONE", "STRANGER_SINS", "BETTER_SAVE_SOUL"]
                    )

    def test_ap_items_used_by_recipes_are_progression(self):
        dependencies: set[str] = set()
        for recipes in data.recipes.values():
            for recipe in recipes:
                dependencies.update(recipe.workstations)
                dependencies.update(recipe.ingredients)
                if recipe.required_recipe_item:
                    dependencies.add(recipe.required_recipe_item)

        resolved_dependencies = {
            data.progressive_items_reverse[item_key].key
            if item_key in data.progressive_items_reverse
            else item_key
            for item_key in dependencies
        }
        non_progression_items = {
            item_key: data.items[item_key].classification
            for item_key in resolved_dependencies & data.items.keys()
            if data.items[item_key].classification != ItemClassification.progression
        }

        self.assertFalse(
            non_progression_items,
            "AP items used by crafting logic must be progression items: "
            f"{non_progression_items}",
        )
