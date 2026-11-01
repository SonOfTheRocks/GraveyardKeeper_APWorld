import typing

from rule_builder.rules import CanReachLocation
from test.param import classvar_matrix

from .bases import GraveyardKeeperTestBase
from ..data import data

@classvar_matrix(
    unlock_key = [
        "ITEM_UNLOCK_ANATOMY",
        "ITEM_UNLOCK_ALCHEMY",
        "ITEM_UNLOCK_FAITH",
        "ITEM_UNLOCK_GRAVES",
        "ITEM_UNLOCK_WRITING",
        "ITEM_UNLOCK_FARMING",
        "ITEM_UNLOCK_GATHERING",
        "ITEM_UNLOCK_SMITHING",
        "ITEM_UNLOCK_WOOD",
        "ITEM_UNLOCK_STONE",
        "ITEM_UNLOCK_CLAY",
        "ITEM_UNLOCK_SIMPLE_AND_TASTY",
        "ITEM_UNLOCK_VEGETABLE_DISHES",
        "ITEM_UNLOCK_JELLY",
        "ITEM_UNLOCK_BREAD",
        "ITEM_UNLOCK_FISH_DISHES",
        "ITEM_UNLOCK_SWEET_BAKING",
        "ITEM_UNLOCK_EGG_DISHES",
        "ITEM_UNLOCK_PIES",
        "ITEM_UNLOCK_TASTY_AND_HEALTHY",
        "ITEM_UNLOCK_MEAT_FIESTA",
        "ITEM_UNLOCK_FISH_DELICACIES",
        "ITEM_UNLOCK_ZOMBIE_BASICS",
        "ITEM_UNLOCK_ZOMBIE_WORKSTATIONS",
        "ITEM_UNLOCK_SPIRITUALISM"
    ],
)
class TestDormantTechUnlocks(GraveyardKeeperTestBase):
    run_default_tests = False
    unlock_key = typing.ClassVar[str]

    options = {
        'stranger_sins': True,
        'game_of_crone': True,
        'better_save_soul': True,
    }

    def test_legacy_group_is_reserved_but_not_generated(self):
        label = data.items[self.unlock_key].label
        self.assertIn(label, self.world.item_name_to_id)
        self.assertNotIn(label, [item.name for item in self.multiworld.itempool])
