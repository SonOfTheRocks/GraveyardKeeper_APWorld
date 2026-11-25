from dataclasses import replace
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from BaseClasses import CollectionState
from ..data import CRAFTING_EVENT_PREFIX, data
from ..logic.church_calculator import CHURCH_RATING, CHURCH_UPGRADES, ChurchPointCalculator, HasChurchRating
from ..logic.custom_rules import CanComplete, CanCraftRecipe, resolve_item_labels
from ..models import ChurchLevel
from .fakes import FakeState, FakeWorld


def church_state(*keys, level=ChurchLevel.OPEN):
    labels = [data.events[CRAFTING_EVENT_PREFIX + key].item_label for key in keys]
    if level in CHURCH_UPGRADES:
        labels.append(data.events[CHURCH_UPGRADES[level]].item_label)
    return FakeState(labels)


class TestChurchRating(TestCase):
    def rating(self, *keys, level=ChurchLevel.OPEN):
        return ChurchPointCalculator(church_state(*keys, level=level), 1).calculate()

    def test_initial_church_and_no_free_upgrade_bonus(self):
        for level in (ChurchLevel.OPEN, ChurchLevel.BIG, ChurchLevel.CATHEDRAL):
            with self.subTest(level=level.name):
                self.assertEqual(5, self.rating(level=level))

    def test_benches_replace_originals_instead_of_stacking(self):
        self.assertEqual(9, self.rating("BUILDABLE_CHURCH_BENCH"))
        self.assertEqual(21, self.rating("BUILDABLE_SOFT_CHURCH_BENCH"))
        self.assertEqual(21, self.rating("BUILDABLE_CHURCH_BENCH", "BUILDABLE_SOFT_CHURCH_BENCH"))

    def test_candles_require_a_candelabrum_and_use_best_type(self):
        self.assertEqual(5, self.rating("ITEM_CANDLE_4"))
        self.assertEqual(13, self.rating("BUILDABLE_CANDELABRA_1"))
        self.assertEqual(37, self.rating("BUILDABLE_CANDELABRA_1", "ITEM_CANDLE_4"))
        self.assertEqual(37, self.rating("BUILDABLE_CANDELABRA_1", "ITEM_CANDLE_1", "ITEM_CANDLE_3", "ITEM_CANDLE_4"))
        self.assertEqual(101, self.rating("BUILDABLE_CANDELABRA_3", "ITEM_CANDLE_4"))

    def test_incense_requires_a_burner_and_uses_best_type(self):
        self.assertEqual(5, self.rating("ITEM_INCENSE_2"))
        self.assertEqual(23, self.rating("BUILDABLE_INCENSE_BURNER_2"))
        self.assertEqual(47, self.rating("BUILDABLE_INCENSE_BURNER_2", "ITEM_INCENSE_2"))
        self.assertEqual(47, self.rating("BUILDABLE_INCENSE_BURNER_2", "ITEM_INCENSE", "ITEM_INCENSE_2"))

    def test_competing_furniture_is_not_added_together(self):
        self.assertEqual(19, self.rating("BUILDABLE_CONFESSIONAL_2"))
        self.assertEqual(21, self.rating("BUILDABLE_CONFESSIONAL_2", "BUILDABLE_STONE_CHURCH_SHRINE"))
        # Four narrow spaces and two pairs in the wide spaces, versus two shrines.
        self.assertEqual(101, self.rating("BUILDABLE_CONFESSIONAL_2", "BUILDABLE_STONE_CHURCH_SHRINE",
                                          "BUILDABLE_CANDELABRA_3", "ITEM_CANDLE_4"))

    def test_expanded_spaces_and_walls_require_upgrade(self):
        self.assertEqual(5, self.rating("BUILDABLE_WALL_CANDELABRA_3", "ITEM_CANDLE_4"))
        self.assertEqual(53, self.rating("BUILDABLE_WALL_CANDELABRA_3", "ITEM_CANDLE_4", level=ChurchLevel.BIG))
        self.assertEqual(65, self.rating("BUILDABLE_WALL_CANDELABRA_3", "ITEM_CANDLE_4", level=ChurchLevel.CATHEDRAL))
        self.assertEqual(5, self.rating("BUILDABLE_STAINED_GLASS_WINDOW", level=ChurchLevel.BIG))
        self.assertEqual(10, self.rating("BUILDABLE_STAINED_GLASS_WINDOW", level=ChurchLevel.CATHEDRAL))

    def test_twenty_and_fifty_point_quest_requirements_are_enforced(self):
        world = FakeWorld()
        cases = [
            ("EVENT_BISHOP_IMPROVE_CHURCH", ("BUILDABLE_CONFESSIONAL", "BUILDABLE_CANDELABRA_1"), "ITEM_CANDLE_1"),
            ("EVENT_BISHOP_IMPROVE_CHURCH_FOR_CATHEDRAL",
             ("BUILDABLE_SOFT_CHURCH_BENCH", "BUILDABLE_STONE_CHURCH_SHRINE", "BUILDABLE_CANDELABRA_3"), "ITEM_CANDLE_1"),
        ]
        for key, furniture, extra in cases:
            with self.subTest(quest=key):
                # Isolate the authored area requirement from unrelated quest prerequisites.
                quest = replace(data.events[key], required_quests=frozenset(), required_happiness=frozenset(),
                                required_quest_items=frozenset(), required_craft_items=frozenset())
                with patch.dict(data.events, {key: quest}):
                    rule = CanComplete(key).resolve(world)
                self.assertFalse(rule(church_state(*furniture)))
                self.assertTrue(rule(church_state(*furniture, extra)))

    def test_threshold_is_inclusive_and_region_access_is_required(self):
        world = FakeWorld()
        state = church_state("BUILDABLE_SOFT_CHURCH_BENCH")
        self.assertTrue(HasChurchRating(21).resolve(world)(state))
        self.assertFalse(HasChurchRating(22).resolve(world)(state))
        with patch.object(state, "can_reach_region", return_value=False):
            self.assertFalse(HasChurchRating(5).resolve(world)(state))

    def test_every_input_and_upgrade_is_declared_for_progression_and_caching(self):
        dependencies = HasChurchRating(50).resolve(FakeWorld()).item_dependencies()
        for key in CHURCH_RATING["furniture"] | CHURCH_RATING["consumables"]:
            self.assertIn(data.events[CRAFTING_EVENT_PREFIX + key].item_label, dependencies)
        for key in CHURCH_UPGRADES.values():
            self.assertIn(data.events[key].item_label, dependencies)

    def test_furniture_needs_blueprint_and_each_material(self):
        for key in CHURCH_RATING["furniture"]:
            with self.subTest(furniture=key):
                recipe, = data.recipes[key]
                self.assertEqual(frozenset({"REGION_CHURCH"}), recipe.regions)
                rules = CanCraftRecipe(recipe).resolve(FakeWorld())
                inputs = [recipe.required_recipe_item, *recipe.ingredients]
                labels = {}
                for item in inputs:
                    # Ownership items use their progressive stage; materials use obtainable events.
                    resolved = resolve_item_labels(item) if item == recipe.required_recipe_item else {
                        (data.events[CRAFTING_EVENT_PREFIX + item].item_label, 1)}
                    labels[item] = dict(resolved)
                all_counts = {name: count for values in labels.values() for name, count in values.items()}
                self.assertTrue(rules(FakeState(counts=all_counts)))
                for missing, values in labels.items():
                    state = FakeState(counts={name: count for name, count in all_counts.items() if name not in values})
                    self.assertFalse(rules(state), f"{key} without {missing}")

    def test_layout_groups_and_material_references_exist(self):
        groups = {entry["group"] for entry in CHURCH_RATING["furniture"].values()}
        for patch_data in CHURCH_RATING["patches"]:
            self.assertIn(patch_data["minimum_level"], ChurchLevel.__members__)
            for configuration in patch_data["configurations"]:
                self.assertLessEqual(configuration.keys(), groups)
        for key in CHURCH_RATING["furniture"]:
            self.assertIn(key, data.recipes)
            for material in data.recipes[key][0].ingredients:
                self.assertIn(CRAFTING_EVENT_PREFIX + material, data.events)

    def test_received_blueprints_match_native_client_unlocks(self):
        path = Path(__file__).resolve().parents[5] / "RiderProjects/GraveyardKeepelago/External/GraveyardKeeperData/item_grants.json"
        if not path.exists():
            self.skipTest("Companion client checkout is unavailable")
        grants = json.loads(path.read_text(encoding="utf-8-sig"))
        native = {
            "CHURCH_BENCH": "church_bench", "SOFT_CHURCH_BENCH": "church_bench_2",
            "CONFESSIONAL": "church_budka_1_place", "CONFESSIONAL_2": "church_budka_2_place",
            "WOODEN_CHURCH_SHRINE": "church_table_1_place", "STONE_CHURCH_SHRINE": "church_table_2_place",
            "INCENSE_BURNER": "c_obj_incense_1_place", "INCENSE_BURNER_2": "c_obj_incense_2_place",
            "STAINED_GLASS_WINDOW": "church_window_1",
        }
        for level in (1, 2, 3):
            native[f"CANDELABRA_{level}"] = f"candelabrum_{level}"
            native[f"WALL_CANDELABRA_{level}"] = f"wall_candelabrum_{level}"
        for furniture, native_id in native.items():
            recipe, = data.recipes["BUILDABLE_" + furniture]
            key = recipe.required_recipe_item
            reverse = data.progressive_items_reverse.get(key)
            grant = grants[reverse.key if reverse else key]
            crafts = grant["stages"][reverse.count - 1] if reverse else grant["craft_ids"]
            self.assertIn("church_builddesk:p:" + native_id, [craft.lstrip("@") for craft in crafts])

    def test_cached_rating_updates_after_collecting_and_removing_inputs(self):
        from .test_progression import generate_worlds
        multiworld = generate_worlds({})
        world = multiworld.worlds[1]
        state = CollectionState(multiworld)
        state.collect(world.create_item(data.items["ITEM_PERK_PREACHER"].label), prevent_sweep=True)
        rule = HasChurchRating(20).resolve(world)
        world.register_rule_dependencies(rule)
        key = CRAFTING_EVENT_PREFIX + "BUILDABLE_SOFT_CHURCH_BENCH"
        item = world.get_location(data.events[key].location_label).item
        # Isolate rating cache invalidation from the tutorial's region-access rules.
        with patch.object(state, "can_reach_region", return_value=True):
            self.assertFalse(rule(state))
            state.collect(item, prevent_sweep=True)
            self.assertTrue(rule(state))
            self.assertFalse(rule(CollectionState(multiworld)))
            state.remove(item)
            self.assertFalse(rule(state))
