import unittest

from ..data import data
from ..logic.custom_rules import CanBuy, CanGet
from ..options import VendorLogic
from .fakes import FakeState, FakeWorld


class TestVendorLogic(unittest.TestCase):
    optional_vendor_item = "ITEM_FEATHER"
    mandatory_vendor_item = "ITEM_SILK"

    @staticmethod
    def _world(mode: int) -> FakeWorld:
        return FakeWorld({
            "vendor_logic": mode,
            "stranger_sins": True,
            "game_of_crone": True,
            "better_save_soul": True,
        })

    def test_optional_vendor_item_is_out_of_logic_by_default(self):
        world = self._world(VendorLogic.option_out_of_logic)
        rule = CanBuy(self.optional_vendor_item).resolve(world)

        self.assertFalse(rule(FakeState()))

    def test_mandatory_vendor_item_requires_money_source_in_out_of_logic_mode(self):
        world = self._world(VendorLogic.option_out_of_logic)
        rule = CanBuy(self.mandatory_vendor_item).resolve(world)

        self.assertFalse(rule(FakeState()))
        self.assertTrue(rule(FakeState([
            data.events["EVENT_CHURCH_OPEN"].item_label,
        ])))

    def test_money_source_mode_requires_open_church(self):
        world = self._world(VendorLogic.option_require_money_source)
        rule = CanBuy(self.optional_vendor_item).resolve(world)

        self.assertFalse(rule(FakeState()))
        self.assertTrue(rule(FakeState([
            data.events["EVENT_CHURCH_OPEN"].item_label,
        ])))

    def test_mandatory_vendor_item_also_requires_money_source_in_money_mode(self):
        world = self._world(VendorLogic.option_require_money_source)
        rule = CanBuy(self.mandatory_vendor_item).resolve(world)

        self.assertFalse(rule(FakeState()))
        self.assertTrue(rule(FakeState([
            data.events["EVENT_CHURCH_OPEN"].item_label,
        ])))

    def test_always_available_mode_only_requires_vendor_access(self):
        world = self._world(VendorLogic.option_always_available)
        rule = CanBuy(self.optional_vendor_item).resolve(world)

        self.assertTrue(rule(FakeState()))

    def test_can_get_uses_the_vendor_acquisition_rule(self):
        world = self._world(VendorLogic.option_always_available)

        self.assertTrue(CanGet(self.optional_vendor_item).resolve(world)(FakeState()))
