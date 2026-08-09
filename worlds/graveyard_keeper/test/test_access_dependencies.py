import typing

from test.param import classvar_matrix
from .bases import GraveyardKeeperTestBase
from ..data import data
class TestTechUnlocks(GraveyardKeeperTestBase):
    run_default_tests = False
    #unlock_key = typing.ClassVar[...]
    options = {
        'stranger_sins': True,
        'game_of_crone': True,
        'better_save_soul': True,
    }

    def test_tech_unlock_dependency(self):
        unlock_keys = [
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
        ]
        for unlock_key in unlock_keys:
            with self.subTest(unlock_key=unlock_key, msg=unlock_key):
                locations: list[str] = []
                for unlock in data.unlocks[unlock_key].unlocks:
                    tech_name = unlock.split('/')[-1]
                    for i in range(1, 4):
                        if unlock == "REGION_TECH_TREE_SPIRITUALISM/STONE_GRAVESTONES"\
                                or unlock == "REGION_TECH_TREE_SPIRITUALISM/MARBLE_GRAVESTONES":
                            location_name = f"LOCATION_{tech_name}_SPIRITUALISM_UNLOCK_{i}"
                        else:
                            location_name = f"LOCATION_{tech_name}_UNLOCK_{i}"
                        self.assertIn(location_name, data.locations)
                        self.assertFalse(self.multiworld.state.can_reach_location(
                            data.locations[location_name].label, self.player))
                        locations.append(data.locations[location_name].label)

                self.assertAccessDependency(
                    locations,
                    [[data.unlocks[unlock_key].label]],
                    only_check_listed=True
                )