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
class TestTechUnlocks(GraveyardKeeperTestBase):
    run_default_tests = False
    unlock_key = typing.ClassVar[str]

    options = {
        'stranger_sins': True,
        'game_of_crone': True,
        'better_save_soul': True,
    }

    def test_tech_unlock_locations_require_unlock(self):
        locations = self.get_unlock_locations()

        for location in locations:
            with self.subTest(location=location):
                rule = CanReachLocation(location)

                self.assertFalse(
                    rule.resolve(self.world),
                    msg=(
                        f"Location {location!r} is reachable without "
                        f"unlock {self.unlock_key!r}"
                    )
                )

    def get_unlock_locations(self) -> list[str]:
        locations = []

        for unlock in data.unlocks[self.unlock_key].unlocks:
            tech_name = unlock.rsplit("/", 1)[-1]

            for level in range(1, 4):
                location_name = self.get_unlock_location_name(
                    unlock,
                    tech_name,
                    level,
                )

                self.assertIn(
                    location_name,
                    data.locations,
                    msg=(
                        f"Expected location {location_name!r} for "
                        f"unlock {self.unlock_key!r}, but it does not exist."
                    )
                )

        return locations

    @staticmethod
    def get_unlock_location_name(
            unlock: str,
            tech_name: str,
            level: int,
    ) -> str:
        if unlock in {
            "REGION_TECH_TREE_SPIRITUALISM/STONE_GRAVESTONES",
            "REGION_TECH_TREE_SPIRITUALISM/MARBLE_GRAVESTONES",
        }:
            return f"LOCATION_{tech_name}_SPIRITUALISM_UNLOCK_{level}"

        return f"LOCATION_{tech_name}_UNLOCK_{level}"
