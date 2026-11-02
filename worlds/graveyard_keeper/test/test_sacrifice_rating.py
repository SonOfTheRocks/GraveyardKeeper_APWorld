from dataclasses import replace
from itertools import product
from unittest import TestCase
from unittest.mock import patch

from BaseClasses import CollectionState, ItemClassification
from ..data import CRAFTING_EVENT_PREFIX, data
from ..items import GraveyardKeeperItem
from ..logic.custom_rules import CanComplete, CanCraftRecipe
from ..logic.sacrifice_calculator import SACRIFICE_RATING, HasSacrificeRating, SacrificePointCalculator
from ..models import AreaPointData
from .fakes import FakeState, FakeWorld


UNLOCK = "EVENT_SNAKE_OFFER_TO_PREPARE_RITUAL_SITE"
FOUNTAIN = "BUILDABLE_SACRIFICE_BLOOD_FOUNTAIN"
FURNITURE = tuple(SACRIFICE_RATING["furniture"])


def sacrifice_state(*crafts, unlocked=True):
    labels = [data.events[CRAFTING_EVENT_PREFIX + key].item_label for key in crafts]
    if unlocked:
        labels.append(data.events[UNLOCK].item_label)
    return FakeState(labels)


class TestSacrificeRating(TestCase):
    def score(self, *crafts, **kwargs):
        return SacrificePointCalculator(sacrifice_state(*crafts, **kwargs), 1).calculate()

    def test_empty_site_has_no_free_quality(self):
        self.assertEqual(0, self.score())
        self.assertEqual(0, self.score("ITEM_BLOOD"))

    def test_each_furniture_uses_its_two_dedicated_places(self):
        expected = {
            FOUNTAIN: 4,
            "BUILDABLE_SACRIFICE_CRUCIFIED_SKELETON": 4,
            "BUILDABLE_SACRIFICE_WALL_SKELETON": 2,
            "BUILDABLE_SACRIFICE_WALL_SKULLS": 2,
            "BUILDABLE_SACRIFICE_COLUMN_SKULLS": 2,
        }
        for key, points in expected.items():
            with self.subTest(furniture=key):
                self.assertEqual(points, self.score(key))

    def test_snakes_unlock_is_required_for_fountains_and_skeletons(self):
        for key, entry in SACRIFICE_RATING["furniture"].items():
            if "required_event" in entry:
                with self.subTest(furniture=key):
                    self.assertEqual(0, self.score(key, "ITEM_BLOOD", unlocked=False))
        self.assertEqual(4, self.score(*FURNITURE, "ITEM_BLOOD", unlocked=False))

    def test_activation_replaces_empty_fountains_instead_of_stacking(self):
        self.assertEqual(4, self.score(FOUNTAIN))
        self.assertEqual(10, self.score(FOUNTAIN, "ITEM_BLOOD"))
        self.assertEqual(14, self.score(*FURNITURE))
        self.assertEqual(20, self.score(*FURNITURE, "ITEM_BLOOD"))

    def test_all_furniture_and_blood_are_needed_for_twenty(self):
        rule = HasSacrificeRating(20).resolve(FakeWorld())
        crafts = (*FURNITURE, "ITEM_BLOOD")
        self.assertTrue(rule(sacrifice_state(*crafts)))
        for missing in crafts:
            with self.subTest(missing=missing):
                self.assertFalse(rule(sacrifice_state(*(key for key in crafts if key != missing))))

    def test_inclusive_threshold_and_region_access(self):
        state = sacrifice_state(*FURNITURE, "ITEM_BLOOD")
        self.assertTrue(HasSacrificeRating(20).resolve(FakeWorld())(state))
        self.assertFalse(HasSacrificeRating(21).resolve(FakeWorld())(state))
        with patch.object(state, "can_reach_region", return_value=False):
            self.assertFalse(HasSacrificeRating(20).resolve(FakeWorld())(state))

    def test_actual_quest_and_diagnostics_enforce_twenty(self):
        from .rule_evaluation import QuestRuleEvaluator
        key = "EVENT_SNAKE_SHOW_PREPARED_RITUAL_SITE"
        self.assertEqual(frozenset({AreaPointData("SACRIFICE_ZONE", 20)}),
                         frozenset(data.events[key].required_area_points))
        quest = replace(data.events[key], required_quests=frozenset())
        with patch.dict(data.events, {key: quest}):
            rule = CanComplete(key).resolve(FakeWorld())
            for state, expected in [(sacrifice_state(*FURNITURE), False),
                                    (sacrifice_state(*FURNITURE, "ITEM_BLOOD"), True)]:
                self.assertEqual(expected, rule(state))
                result = QuestRuleEvaluator(state=state).evaluate(key)
                self.assertEqual(expected, result.passed)
                if not expected:
                    self.assertIn("sacrifice rating 20", result.format_failed_tree())

    def test_building_recipes_require_each_native_material(self):
        expected = {
            FOUNTAIN: {"ITEM_A_POLISHED_BRICK_OF_STONE", "ITEM_POLISHING_PASTE", "ITEM_STONE_REPAIR_KIT"},
            "BUILDABLE_SACRIFICE_CRUCIFIED_SKELETON": {"ITEM_SKULL", "ITEM_WOODEN_BEAM", "ITEM_PUMPKIN_SILVER"},
            "BUILDABLE_SACRIFICE_WALL_SKELETON": {"ITEM_SKULL", "ITEM_WOODEN_BEAM", "ITEM_PUMPKIN_SILVER"},
            "BUILDABLE_SACRIFICE_WALL_SKULLS": {"ITEM_SKULL"},
            "BUILDABLE_SACRIFICE_COLUMN_SKULLS": {"ITEM_SKULL"},
        }
        for key, ingredients in expected.items():
            with self.subTest(furniture=key):
                recipe, = data.recipes[key]
                self.assertEqual(frozenset({"REGION_SACRIFICE_ZONE"}), recipe.regions)
                self.assertEqual(frozenset(ingredients), recipe.ingredients)
                self.assertFalse(recipe.required_recipe_item)
                rule = CanCraftRecipe(recipe).resolve(FakeWorld())
                labels = [data.events[CRAFTING_EVENT_PREFIX + item].item_label for item in ingredients]
                self.assertTrue(rule(FakeState(labels)))
                for missing in labels:
                    self.assertFalse(rule(FakeState([label for label in labels if label != missing])))

    def test_stone_repair_kit_requires_recipe_materials_and_either_stonecutter(self):
        recipe, = data.recipes["ITEM_STONE_REPAIR_KIT"]
        self.assertEqual("ITEM_LEARN_CREATE_STONE_REPAIR_KIT", recipe.required_recipe_item)
        self.assertEqual(frozenset({"ITEM_A_PIECE_OF_STONE", "ITEM_SIMPLE_IRON_PARTS", "ITEM_CLAY"}),
                         recipe.ingredients)
        self.assertEqual(frozenset({"CRAFTING_STATION_STONE_CUTTER", "CRAFTING_STATION_STONE_CUTTER_2"}),
                         recipe.workstations)
        rule = CanCraftRecipe(recipe).resolve(FakeWorld())
        labels = [data.events[CRAFTING_EVENT_PREFIX + key].item_label for key in recipe.ingredients]
        labels.append(data.items[recipe.required_recipe_item].label)
        self.assertFalse(rule(FakeState(labels)))
        for station in recipe.workstations:
            station_label = data.events[CRAFTING_EVENT_PREFIX + station].item_label
            self.assertTrue(rule(FakeState([*labels, station_label])))
            for missing in labels:
                self.assertFalse(rule(FakeState([station_label, *(label for label in labels if label != missing)])))

    def test_base_game_quality_works_with_every_dlc_combination(self):
        for sins, crone, soul in product((False, True), repeat=3):
            with self.subTest(sins=sins, crone=crone, soul=soul):
                rule = HasSacrificeRating(20).resolve(FakeWorld({
                    "stranger_sins": sins, "game_of_crone": crone, "better_save_soul": soul,
                }))
                self.assertTrue(rule(sacrifice_state(*FURNITURE, "ITEM_BLOOD")))
                self.assertFalse(rule(sacrifice_state(*FURNITURE)))

    def test_every_observed_input_declares_a_dependency(self):
        rule = HasSacrificeRating(20).resolve(FakeWorld())
        for key in (UNLOCK, *(CRAFTING_EVENT_PREFIX + key for key in (*FURNITURE, "ITEM_BLOOD"))):
            self.assertIn(data.events[key].item_label, rule.item_dependencies())
        self.assertIn(data.regions["REGION_SACRIFICE_ZONE"].label, rule.region_dependencies())

    def test_cached_quality_updates_after_collecting_and_removing_inputs(self):
        from .test_progression import generate_worlds
        multiworld = generate_worlds({})
        world = multiworld.worlds[1]
        rule = HasSacrificeRating(20).resolve(world)
        world.register_rule_dependencies(rule)
        state = CollectionState(multiworld)

        def item(key):
            return GraveyardKeeperItem(data.events[key].item_label, ItemClassification.progression, None, 1)

        unlock = item(UNLOCK)
        blood = item(CRAFTING_EVENT_PREFIX + "ITEM_BLOOD")
        for key in FURNITURE:
            state.collect(item(CRAFTING_EVENT_PREFIX + key), prevent_sweep=True)
        with patch.object(state, "can_reach_region", return_value=True):
            self.assertFalse(rule(state))
            state.collect(blood, prevent_sweep=True)
            self.assertFalse(rule(state))
            state.collect(unlock, prevent_sweep=True)
            self.assertTrue(rule(state))
            self.assertFalse(rule(CollectionState(multiworld)))
            for removable in (blood, unlock, item(CRAFTING_EVENT_PREFIX + FOUNTAIN)):
                state.remove(removable)
                self.assertFalse(rule(state))
                state.collect(removable, prevent_sweep=True)
                self.assertTrue(rule(state))
