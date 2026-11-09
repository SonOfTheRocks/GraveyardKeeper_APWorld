from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from BaseClasses import CollectionState, ItemClassification
from ..data import CRAFTING_EVENT_PREFIX, data
from ..items import GraveyardKeeperItem
from ..logic.custom_rules import CanComplete, CanCraftRecipe
from ..logic.trade_office_calculator import (
    TRADE_OFFICE_RATING, HasTradeOfficeRating, TradeOfficePointCalculator,
)
from ..models import AreaPointData
from .fakes import FakeState, FakeWorld


OPEN = TRADE_OFFICE_RATING["open_event"]
PALLET = TRADE_OFFICE_RATING["pallet_buildable"]
FLYER = TRADE_OFFICE_RATING["marketing_material"]


def office_state(*crafts, opened=True):
    labels = [data.events[CRAFTING_EVENT_PREFIX + key].item_label for key in crafts]
    if opened:
        labels.append(data.events[OPEN].item_label)
    return FakeState(labels)


class TestTradeOfficeRating(TestCase):
    def score(self, *crafts, **kwargs):
        return TradeOfficePointCalculator(office_state(*crafts, **kwargs), 1).calculate()

    def test_closed_office_has_no_quality(self):
        self.assertEqual(0, self.score(FLYER, PALLET, opened=False))
        self.assertFalse(HasTradeOfficeRating(0).resolve(FakeWorld())(office_state(opened=False)))

    def test_existing_pallet_counts_without_materials(self):
        self.assertEqual(1, self.score())
        rule = HasTradeOfficeRating(1).resolve(FakeWorld())
        self.assertTrue(rule(office_state()))
        self.assertFalse(HasTradeOfficeRating(2).resolve(FakeWorld())(office_state()))

    def test_unused_marketing_points_suffice_without_new_pallets(self):
        self.assertEqual(499996, self.score(FLYER))
        self.assertTrue(HasTradeOfficeRating(3).resolve(FakeWorld())(office_state(FLYER)))

    def test_pallets_replace_available_spaces_without_double_counting_initial_one(self):
        self.assertEqual(10, self.score(PALLET))
        self.assertEqual(500005, self.score(PALLET, FLYER))

    def test_exact_threshold_and_region_access(self):
        state = office_state(FLYER, PALLET)
        self.assertTrue(HasTradeOfficeRating(500005).resolve(FakeWorld())(state))
        self.assertFalse(HasTradeOfficeRating(500006).resolve(FakeWorld())(state))
        with patch.object(state, "can_reach_region", return_value=False):
            self.assertFalse(HasTradeOfficeRating(3).resolve(FakeWorld())(state))

    def test_actual_merchant_quest_requires_quality_three(self):
        key = "EVENT_MERCHANT_COMPLETE_MARKETING"
        self.assertEqual(frozenset({AreaPointData("TRADE_OFFICE", 3)}),
                         frozenset(data.events[key].required_area_points))
        # Isolate the quality gate from the independently tested quest chain.
        quest = replace(data.events[key], required_quests=frozenset())
        with patch.dict(data.events, {key: quest}):
            rule = CanComplete(key).resolve(FakeWorld())
        self.assertFalse(rule(office_state()))
        self.assertFalse(rule(office_state(FLYER, opened=False)))
        self.assertTrue(rule(office_state(FLYER)))

    def test_pallet_requires_flitch_and_flyers_but_no_morgue_blueprint(self):
        recipe, = data.recipes[PALLET]
        self.assertEqual(frozenset({"REGION_TRADE_OFFICE"}), recipe.regions)
        self.assertEqual(frozenset({"ITEM_FLITCH", "ITEM_FLYER"}), recipe.ingredients)
        rule = CanCraftRecipe(recipe).resolve(FakeWorld())
        labels = [data.events[CRAFTING_EVENT_PREFIX + key].item_label for key in recipe.ingredients]
        self.assertTrue(rule(FakeState(labels)))
        for missing in labels:
            with self.subTest(missing=missing):
                self.assertFalse(rule(FakeState([label for label in labels if label != missing])))

    def test_quest_diagnostics_agree_with_production_quality_gate(self):
        from .rule_evaluation import QuestRuleEvaluator
        key = "EVENT_MERCHANT_COMPLETE_MARKETING"
        quest = replace(data.events[key], required_quests=frozenset())
        with patch.dict(data.events, {key: quest}):
            below = QuestRuleEvaluator(state=office_state()).evaluate(key)
            enough = QuestRuleEvaluator(state=office_state(FLYER)).evaluate(key)
        self.assertFalse(below.passed)
        self.assertIn("trade office rating 3", below.format_failed_tree())
        self.assertTrue(enough.passed)

    def test_base_game_rule_works_for_every_dlc_combination(self):
        from itertools import product
        for sins, crone, soul in product((False, True), repeat=3):
            with self.subTest(sins=sins, crone=crone, soul=soul):
                rule = HasTradeOfficeRating(3).resolve(FakeWorld({
                    "stranger_sins": sins, "game_of_crone": crone, "better_save_soul": soul,
                }))
                self.assertTrue(rule(office_state(FLYER)))
                self.assertFalse(rule(office_state()))

    def test_every_input_declares_a_dependency(self):
        rule = HasTradeOfficeRating(3).resolve(FakeWorld())
        for key in (OPEN, CRAFTING_EVENT_PREFIX + FLYER, CRAFTING_EVENT_PREFIX + PALLET):
            self.assertIn(data.events[key].item_label, rule.item_dependencies())
        self.assertIn(data.regions["REGION_TRADE_OFFICE"].label, rule.region_dependencies())

    def test_cached_quality_updates_on_collection_and_removal(self):
        from .test_progression import generate_worlds
        multiworld = generate_worlds({})
        world = multiworld.worlds[1]
        rule = HasTradeOfficeRating(3).resolve(world)
        world.register_rule_dependencies(rule)
        furniture_rule = HasTradeOfficeRating(500005).resolve(world)
        world.register_rule_dependencies(furniture_rule)
        state = CollectionState(multiworld)

        def item(key):
            return GraveyardKeeperItem(data.events[key].item_label, ItemClassification.progression, None, 1)

        opening = item(OPEN)
        flyers = item(CRAFTING_EVENT_PREFIX + FLYER)
        with patch.object(state, "can_reach_region", return_value=True):
            self.assertFalse(rule(state))
            state.collect(opening, prevent_sweep=True)
            self.assertFalse(rule(state))
            state.collect(flyers, prevent_sweep=True)
            self.assertTrue(rule(state))
            self.assertFalse(furniture_rule(state))
            pallets = item(CRAFTING_EVENT_PREFIX + PALLET)
            state.collect(pallets, prevent_sweep=True)
            self.assertTrue(furniture_rule(state))
            state.remove(pallets)
            self.assertFalse(furniture_rule(state))
            self.assertFalse(rule(CollectionState(multiworld)))
            state.remove(flyers)
            self.assertFalse(rule(state))
            state.collect(flyers, prevent_sweep=True)
            self.assertTrue(rule(state))
            state.remove(opening)
            self.assertFalse(rule(state))
