import unittest

from ...data import CRAFTING_EVENT_PREFIX, CRAFTING_REGION_KEY, data
from ...logic.acquisition import get_higher_quality_substitutes
from ...logic.custom_rules import build_crafting_event_rule
from ..fakes import FakeState, FakeWorld


class TestCraftingEvents(unittest.TestCase):

    def test_every_non_ap_acquisition_has_exactly_one_event(self):
        vendor_items = {
            item_key
            for vendor in data.vendors.values()
            for item_key in vendor.sells_all
        }
        expected_item_keys = {
            item_key
            for item_key in data.recipes.keys() | vendor_items
            if item_key not in data.items
        }
        actual_item_keys = {
            event_key.removeprefix(CRAFTING_EVENT_PREFIX)
            for event_key in data.events
            if event_key.startswith(CRAFTING_EVENT_PREFIX)
        }

        self.assertEqual(expected_item_keys, actual_item_keys)

    def test_every_crafting_event_is_in_the_crafting_region(self):
        crafting_region_events = set(data.regions[CRAFTING_REGION_KEY].events)
        crafting_events = {
            event_key
            for event_key in data.events
            if event_key.startswith(CRAFTING_EVENT_PREFIX)
        }

        self.assertEqual(crafting_events, crafting_region_events)

    def test_higher_quality_variants_can_satisfy_lower_quality_events(self):
        self.assertEqual(
            (
                "ITEM_PRAY_FOR_SOULS_REPOSE_SILVER",
                "ITEM_PRAY_FOR_SOULS_REPOSE_GOLD",
            ),
            get_higher_quality_substitutes("ITEM_PRAY_FOR_SOULS_REPOSE_COPPER"),
        )
        self.assertEqual(
            ("ITEM_PRAY_FOR_SOULS_REPOSE_GOLD",),
            get_higher_quality_substitutes("ITEM_PRAY_FOR_SOULS_REPOSE_SILVER"),
        )
        self.assertEqual(
            (),
            get_higher_quality_substitutes("ITEM_PRAY_FOR_SOULS_REPOSE_GOLD"),
        )

        resolved_rule = build_crafting_event_rule(
            "ITEM_PRAY_FOR_SOULS_REPOSE_COPPER"
        ).resolve(FakeWorld())
        gold_event_label = data.events[
            CRAFTING_EVENT_PREFIX + "ITEM_PRAY_FOR_SOULS_REPOSE_GOLD"
        ].item_label

        self.assertIn(gold_event_label, resolved_rule.item_dependencies())
        self.assertTrue(resolved_rule(FakeState([gold_event_label])))

    def test_one_dependent_recipe_does_not_hide_an_independent_recipe(self):
        self.assertEqual(
            (
                "ITEM_STEEL_CHISEL_SILVER",
                "ITEM_STEEL_CHISEL_GOLD",
            ),
            get_higher_quality_substitutes("ITEM_STEEL_CHISEL_COPPER"),
        )

    def test_vendor_path_can_make_a_higher_quality_variant_independent(self):
        self.assertEqual(
            (
                "ITEM_HARDCOVER_SILVER",
                "ITEM_HARDCOVER_GOLD",
            ),
            get_higher_quality_substitutes("ITEM_HARDCOVER_COPPER"),
        )

    def test_variant_is_excluded_if_every_path_requires_the_lower_quality(self):
        self.assertEqual(
            (),
            get_higher_quality_substitutes("ITEM_HARDCOVER_SILVER"),
        )

    def test_shoots_and_roots_prayer_uses_standard_quality_suffixes(self):
        self.assertEqual(
            (
                "ITEM_PRAYER_FOR_SHOOTS_AND_ROOTS_SILVER",
                "ITEM_PRAYER_FOR_SHOOTS_AND_ROOTS_GOLD",
            ),
            get_higher_quality_substitutes("ITEM_PRAYER_FOR_SHOOTS_AND_ROOTS_COPPER"),
        )
