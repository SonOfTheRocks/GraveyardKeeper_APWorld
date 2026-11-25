from dataclasses import replace
from itertools import product
from unittest import TestCase
from unittest.mock import patch

from BaseClasses import CollectionState, ItemClassification
from ..data import CRAFTING_EVENT_PREFIX, data
from ..items import GraveyardKeeperItem
from ..logic.custom_rules import CanComplete, CanCraftRecipe
from ..logic.refugee_camp_calculator import (
    REFUGEE_CAMP_RATING, HasRefugeeCampRating, RefugeeCampPointCalculator,
)
from ..models import AreaPointData, QuestEventData
from .fakes import FakeState, FakeWorld


BUILDINGS = REFUGEE_CAMP_RATING["buildings"]
FIRST = "EVENT_TEODORO_BUILD_FIRST_WELL_AND_TENT"
COOK = "EVENT_REFUGEE_COOK_BUILD_KITCHEN"
STAGE_TWO = ("EVENT_ALARICH_REVIVE_WITH_BLOOD", "EVENT_TEODORO_GROW_CAMP_TO_SEVEN_RESIDENTS")
UPGRADE = "EVENT_TEODORO_UPGRADE_DEPOT_CAMPFIRE_AND_BUILD_SIXTH_TENT"
ALL_EVENTS = tuple(sorted({event for building in BUILDINGS.values()
                           for event in building.get("required_events", ())}))


def camp_state(*buildings, events=(), opened=True, materials=(), amulet=True):
    labels = [data.events[CRAFTING_EVENT_PREFIX + key].item_label for key in (*buildings, *materials)]
    labels.extend(data.events[key].item_label for key in events)
    if opened:
        labels.append(data.events[REFUGEE_CAMP_RATING["open_event"]].item_label)
    if amulet:
        labels.append(data.items["ITEM_PAGAN_AMULET_OF_SPIRIT_SUMMONING"].label)
    return FakeState(labels)


class TestRefugeeCampRating(TestCase):
    def score(self, *buildings, **kwargs):
        return RefugeeCampPointCalculator(camp_state(*buildings, **kwargs), 1).calculate()

    def test_initial_three_tents_give_three_slots_after_introduction(self):
        self.assertEqual(0, self.score(*BUILDINGS, events=ALL_EVENTS, opened=False))
        self.assertEqual(3, self.score())
        self.assertFalse(HasRefugeeCampRating(0).resolve(FakeWorld())(camp_state(opened=False)))

    def test_well_and_first_additional_tent_are_independent(self):
        self.assertEqual(4, self.score("BUILDABLE_REFUGEE_WELL"))
        self.assertEqual(4, self.score("BUILDABLE_REFUGEE_TENT_4"))
        self.assertEqual(5, self.score("BUILDABLE_REFUGEE_WELL", "BUILDABLE_REFUGEE_TENT_4"))
        self.assertEqual(5, self.score(*BUILDINGS))

    def test_first_phase_can_reach_nine_without_later_story_milestones(self):
        self.assertEqual(8, self.score(*BUILDINGS, events=(FIRST,)))
        self.assertEqual(9, self.score(*BUILDINGS, events=(FIRST, COOK)))

    def test_new_builds_cannot_pay_their_own_happiness_cost(self):
        # Without a kitchen the early camp stops at seven. Campfire II and
        # tent six each cost eight; their own extra slot cannot bridge the gap.
        buildings = tuple(key for key in BUILDINGS if key not in {
            "BUILDABLE_REFUGEE_KITCHEN", "BUILDABLE_REFUGEE_KITCHEN_2",
        })
        self.assertEqual(7, self.score(*buildings, events=ALL_EVENTS))
        self.assertFalse(HasRefugeeCampRating(8).resolve(FakeWorld())(
            camp_state(*buildings, events=ALL_EVENTS)))

    def test_repeated_builds_refill_instead_of_summing_all_costs(self):
        self.assertGreater(sum(building["cost"] for building in BUILDINGS.values()), 16)
        self.assertEqual(16, self.score(*BUILDINGS, events=ALL_EVENTS))

    def test_second_phase_needs_both_story_milestones(self):
        for missing in STAGE_TWO:
            with self.subTest(missing=missing):
                self.assertEqual(9, self.score(*BUILDINGS, events=(FIRST, COOK,
                    *(event for event in STAGE_TWO if event != missing))))
        self.assertEqual(11, self.score(*BUILDINGS, events=(FIRST, COOK, *STAGE_TWO)))
        self.assertEqual(12, self.score(*BUILDINGS, events=(FIRST, COOK, *STAGE_TWO, UPGRADE)))

    def test_cooks_arrival_unlocks_kitchen_without_requiring_the_garden(self):
        no_tents = tuple(key for key in BUILDINGS if "TENT_" not in key)
        state = camp_state(*no_tents, events=ALL_EVENTS)
        calculator = RefugeeCampPointCalculator(state, 1)
        self.assertNotIn("BUILDABLE_REFUGEE_KITCHEN", calculator.attainable_buildings())
        no_garden = tuple(key for key in BUILDINGS if key != "BUILDABLE_REFUGEE_GARDEN_FENCE")
        self.assertIn("BUILDABLE_REFUGEE_KITCHEN", RefugeeCampPointCalculator(
            camp_state(*no_garden, events=ALL_EVENTS), 1).attainable_buildings())
        self.assertEqual(7, self.score(*no_garden, events=ALL_EVENTS))

    def test_cooks_kitchen_reward_is_reachable_without_garden_materials(self):
        no_garden = tuple(key for key in BUILDINGS if key != "BUILDABLE_REFUGEE_GARDEN_FENCE")
        first = replace(data.events[FIRST], required_quests=frozenset(), required_craft_items=frozenset(),
                        required_area_points=frozenset())
        with patch.dict(data.events, {FIRST: first}):
            rule = CanComplete("EVENT_REFUGEE_COOK_BUILD_KITCHEN").resolve(FakeWorld())
        self.assertTrue(rule(camp_state(*no_garden, events=(FIRST,), materials=("ITEM_FLITCH", "ITEM_NAILS"))))
        self.assertFalse(rule(camp_state(*no_garden, events=(FIRST,), materials=("ITEM_FLITCH",))))

    def test_upgrades_add_only_the_difference_and_zero_quality_objects_are_excluded(self):
        self.assertEqual(1, BUILDINGS["BUILDABLE_REFUGEE_KITCHEN_2"]["points"])
        self.assertEqual(1, BUILDINGS["BUILDABLE_REFUGEE_CAMPFIRE_2"]["points"])
        self.assertFalse(any(token in key for key in BUILDINGS for token in ("DEPOT", "HIVE", "WORKPLACE")))
        self.assertEqual(16, self.score(*BUILDINGS, events=ALL_EVENTS))

    def test_late_defensive_buildings_follow_their_quest_unlocks(self):
        early = (FIRST, COOK, *STAGE_TWO, UPGRADE)
        self.assertEqual(12, self.score(*BUILDINGS, events=early))
        self.assertEqual(13, self.score(*BUILDINGS, events=(*early, "EVENT_REFUGEE_TANNER_BUILD_WORKPLACE")))
        self.assertEqual(14, self.score(*BUILDINGS, events=(*early,
            "EVENT_REFUGEE_TANNER_BUILD_WORKPLACE", "EVENT_DONKEY_TAKE_HAIR",
            "EVENT_TEODORO_GROW_CAMP_TO_ELEVEN_RESIDENTS")))
        for key in ("EVENT_TEODORO_BUILD_DEFENSIVE_STAKES", "EVENT_TEODORO_BUILD_SWORD_RACK"):
            self.assertLess(self.score(*BUILDINGS, events=tuple(event for event in ALL_EVENTS if event != key)), 16)

    def test_guards_investigation_requires_the_randomized_pagan_amulet(self):
        self.assertEqual(16, self.score(*BUILDINGS, events=ALL_EVENTS))
        self.assertEqual(15, self.score(*BUILDINGS, events=ALL_EVENTS, amulet=False))

    def test_inclusive_threshold_and_region_access(self):
        state = camp_state(*BUILDINGS, events=ALL_EVENTS)
        self.assertTrue(HasRefugeeCampRating(16).resolve(FakeWorld())(state))
        self.assertFalse(HasRefugeeCampRating(17).resolve(FakeWorld())(state))
        with patch.object(state, "can_reach_region", return_value=False):
            self.assertFalse(HasRefugeeCampRating(1).resolve(FakeWorld())(state))

    def test_disabling_game_of_crone_discards_all_dlc_dependencies(self):
        for sins, crone, soul in product((False, True), repeat=3):
            with self.subTest(sins=sins, crone=crone, soul=soul):
                rule = HasRefugeeCampRating(2).resolve(FakeWorld({
                    "stranger_sins": sins, "game_of_crone": crone, "better_save_soul": soul,
                }))
                self.assertEqual(crone, rule(camp_state()))
                if not crone:
                    self.assertEqual({}, rule.item_dependencies())
                    self.assertFalse(rule.region_dependencies())

    def test_every_authored_camp_threshold_is_enforced_and_diagnosed(self):
        from .rule_evaluation import QuestRuleEvaluator
        thresholds = set()
        for key, quest in tuple(data.events.items()):
            if not isinstance(quest, QuestEventData):
                continue
            for area in quest.required_area_points:
                if area.area != "REFUGEE_CAMP":
                    continue
                thresholds.add(area.value)
                isolated = replace(quest, required_quests=frozenset(), required_craft_items=frozenset(),
                                   required_quest_items=frozenset(), required_happiness=frozenset())
                with self.subTest(quest=key), patch.dict(data.events, {key: isolated}):
                    rule = CanComplete(key).resolve(FakeWorld())
                    empty = camp_state(opened=False)
                    full = camp_state(*BUILDINGS, events=ALL_EVENTS)
                    self.assertFalse(rule(empty))
                    self.assertTrue(rule(full))
                    result = QuestRuleEvaluator(state=empty).evaluate(key)
                    self.assertFalse(result.passed)
                    self.assertIn(f"refugee camp rating {area.value}", result.format_failed_tree())
        self.assertEqual({2, 3, 5, 6, 8, 10, 11, 12, 13}, thresholds)

    def test_recipe_materials_and_no_randomized_building_blueprints(self):
        for key in BUILDINGS:
            with self.subTest(building=key):
                recipe, = data.recipes[key]
                self.assertEqual(frozenset({"REGION_REFUGEE_CAMP"}), recipe.regions)
                self.assertFalse(recipe.required_recipe_item)
                rule = CanCraftRecipe(recipe).resolve(FakeWorld())
                labels = [data.events[CRAFTING_EVENT_PREFIX + item].item_label for item in recipe.ingredients]
                self.assertTrue(rule(FakeState(labels)))
                for missing in labels:
                    self.assertFalse(rule(FakeState([label for label in labels if label != missing])))
        recipe, = data.recipes["BUILDABLE_REFUGEE_CAMPFIRE_2"]
        self.assertIn("ITEM_A_PIECE_OF_STONE", recipe.ingredients)
        self.assertNotIn("ITEM_A_POLISHED_BRICK_OF_STONE", recipe.ingredients)

    def test_population_prerequisites_do_not_require_parallel_milestone_reports(self):
        for key in ("EVENT_REFUGEE_COFFIN_MAKER_GIVE_IRON_CHISELS",
                    "EVENT_REFUGEE_COFFIN_MAKER_GIVE_WOOD_WEDGES"):
            self.assertEqual(set(STAGE_TWO), set(data.events[key].required_quests))
            self.assertNotIn(UPGRADE, data.events[key].required_quests)
        self.assertEqual({UPGRADE}, set(data.events["EVENT_REFUGEE_TANNER_BUILD_WORKPLACE"].required_quests))
        self.assertNotIn("EVENT_TEODORO_GROW_CAMP_TO_ELEVEN_RESIDENTS",
                         data.events["EVENT_REFUGEE_TANNER_BUILD_WORKPLACE"].required_quests)

    def test_build_order_is_independent_of_json_order(self):
        state = camp_state(*BUILDINGS, events=ALL_EVENTS)
        with patch.dict(REFUGEE_CAMP_RATING, {"buildings": dict(reversed(tuple(BUILDINGS.items())))}):
            self.assertEqual(16, RefugeeCampPointCalculator(state, 1).calculate())

    def test_every_input_declares_a_dependency(self):
        rule = HasRefugeeCampRating(13).resolve(FakeWorld())
        for key in (REFUGEE_CAMP_RATING["open_event"], *ALL_EVENTS,
                    *(CRAFTING_EVENT_PREFIX + key for key in BUILDINGS)):
            self.assertIn(data.events[key].item_label, rule.item_dependencies())
        self.assertIn(data.items["ITEM_PAGAN_AMULET_OF_SPIRIT_SUMMONING"].label, rule.item_dependencies())

    def test_water_for_happiness_is_renewable_without_a_randomized_unlock(self):
        for key in ("CRAFTING_STATION_WELL", "ITEM_BUCKET_OF_CLEAR_WATER", "ITEM_WATER"):
            recipe, = data.recipes[key]
            self.assertFalse(recipe.required_recipe_item)
        well, = data.recipes["CRAFTING_STATION_WELL"]
        self.assertFalse(well.ingredients)

    def test_all_authored_area_types_now_have_quest_rule_support(self):
        areas = {requirement.area for event in data.events.values() if isinstance(event, QuestEventData)
                 for requirement in event.required_area_points}
        self.assertEqual({"CHURCH", "TAVERN", "OLD_GRAVEYARD", "TRADE_OFFICE", "SACRIFICE_ZONE", "REFUGEE_CAMP"},
                         areas)

    def test_cached_quality_updates_when_builds_and_unlocks_change(self):
        from .test_progression import generate_worlds
        multiworld = generate_worlds({"game_of_crone": True})
        world = multiworld.worlds[1]
        rule = HasRefugeeCampRating(8).resolve(world)
        world.register_rule_dependencies(rule)
        state = CollectionState(multiworld)

        def item(key):
            return GraveyardKeeperItem(data.events[key].item_label, ItemClassification.progression, None, 1)

        opening = item(REFUGEE_CAMP_RATING["open_event"])
        first = item(FIRST)
        kitchen = item(CRAFTING_EVENT_PREFIX + "BUILDABLE_REFUGEE_KITCHEN")
        for key in BUILDINGS:
            state.collect(item(CRAFTING_EVENT_PREFIX + key), prevent_sweep=True)
        state.collect(opening, prevent_sweep=True)
        with patch.object(state, "can_reach_region", return_value=True):
            self.assertFalse(rule(state))
            state.collect(first, prevent_sweep=True)
            self.assertTrue(rule(state))
            self.assertFalse(rule(CollectionState(multiworld)))
            for removable in (first, kitchen, opening):
                state.remove(removable)
                self.assertFalse(rule(state))
                state.collect(removable, prevent_sweep=True)
                self.assertTrue(rule(state))
