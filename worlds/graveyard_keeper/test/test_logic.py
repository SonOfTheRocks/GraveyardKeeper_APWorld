import unittest
from typing import ClassVar
from unittest.mock import patch

from test.param import classvar_matrix
from .fakes import FakeState, FakeWorld, FakeItem
from .bases import GraveyardKeeperTestBase
from ..data import *
from ..logic.grave_calculator import GravePointCalculator
from ..logic.graveyard_calculator import GraveyardPointCalculator
from ..logic.rule_builder import resolve_item_labels
from ..models import ChurchLevel
from ..options import option_presets
from ..rules import get_max_possible_graveyard_points


class TestSolvabilityLogic(GraveyardKeeperTestBase):
    #run_default_tests = False
    options = option_presets["default"]


    def test_all_workstation_blueprints_must_be_progression_items(self):
        # find all workstations mentioned in recipes
        crafting_station_names: list[str] = []
        for recipes_data in data.recipes.values():
            for recipe_data in recipes_data:
                crafting_station_names += recipe_data.workstations

        # check ItemClassification for blueprints for all found workstations
        for crafting_station_name in set(crafting_station_names):
            crafting_station_recipes = data.recipes[crafting_station_name]
            for crafting_station_recipe in crafting_station_recipes:
                blueprint_name: str = crafting_station_recipe.required_recipe_item
                if blueprint_name == '':
                    continue
                if blueprint_name in data.progressive_items_reverse.keys():
                    blueprint_name = data.progressive_items_reverse[blueprint_name].key
                if blueprint_name: # None if no blueprint is required
                    blueprint_item_data = data.items[blueprint_name]
                    self.assertEqual(
                        blueprint_item_data.classification,
                        ItemClassification.progression,
                        f"blueprint {blueprint_name} not progression item"
                    )

    def test_remove_blockages(self):
        self.assertFalse(self.can_reach_region("REGION_FOREST_NEAR_RIVER"))
        self.assertFalse(self.can_reach_region("REGION_ALCHEMY_LAB"))
        self.assertFalse(self.can_reach_region("REGION_SWAMP"))

        necessary_ap_items: set[str] = set()
        for item in [
            "ITEM_WOOD_WEDGE",
            "ITEM_WOODEN_PLANK",
            "ITEM_SIMPLE_IRON_PARTS",
            "ITEM_WOODEN_BEAM",
            "ITEM_FLITCH",
            "ITEM_NAILS"
        ]: necessary_ap_items.update(GraveyardKeeperTestBase.get_required_ap_items_for(item))
        self.collect_by_name([data.items[item_key].label for item_key in necessary_ap_items])

        self.assertTrue(self.can_reach_region("REGION_FOREST_NEAR_RIVER"))
        self.assertTrue(self.can_reach_region("REGION_ALCHEMY_LAB"))
        self.assertTrue(self.can_reach_region("REGION_SWAMP"))

class TestResolveItemLabels(unittest.TestCase):
    def test_resolves_item(self):
        #item_key = "ITEM_GRAVEYARD_SCROLL"
        item_key = "ITEM_LEARN_EXTRACT_BLOOD"
        self.assertEqual(
            {(data.items[item_key].label, 1)},
            resolve_item_labels(item_key)
        )

    def test_progressive_item(self):
        item_key = "ITEM_BP_FURNACE_2"
        self.assertEqual(
            {(data.items["ITEM_BP_PROGRESSIVE_FURNACE"].label, 2)},
            resolve_item_labels(item_key)
        )

    def test_resolves_event_item(self):
        event_item_key = "EVENT_CORPSE_HATCH_REPAIRED"
        self.assertEqual(
            {(data.events[event_item_key].item_label, 1)},
            resolve_item_labels(event_item_key)
        )

    def test_resolves_crafting_event(self):
        crafting_event_item_key = CRAFTING_EVENT_PREFIX + "ITEM_SLOWING_EXTRACT"
        self.assertEqual(
            {(data.events[crafting_event_item_key].item_label, 1)},
            resolve_item_labels(crafting_event_item_key)
        )

    def test_multiple_keys(self):
        keys = ["ITEM_LEARN_EXTRACT_BLOOD", "EVENT_CORPSE_HATCH_REPAIRED",
                "ITEM_BP_ANVIL_2", CRAFTING_EVENT_PREFIX + "ITEM_RAGE_POTION"]
        labels = {
            #(data.items["ITEM_GRAVEYARD_SCROLL"].label, 1),
            (data.items["ITEM_LEARN_EXTRACT_BLOOD"].label, 1),
            (data.events["EVENT_CORPSE_HATCH_REPAIRED"].item_label, 1),
            (data.items["ITEM_BP_PROGRESSIVE_ANVIL"].label, 3),
            (data.events[CRAFTING_EVENT_PREFIX + "ITEM_RAGE_POTION"].item_label, 1)
        }
        self.assertEqual(labels, resolve_item_labels(keys))

    def test_invalid_key_raises_exception(self):
        key = "INVALID_KEY"
        self.assertRaises(AssertionError, resolve_item_labels, key)

class TestCalculateGraveyardPoints(unittest.TestCase):
    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_no_crafting_no_points(self, mock_can_build, mock_church_level, mock_has_graveyard_extension):
        mock_can_build.return_value = False
        mock_church_level.return_value = ChurchLevel.CLOSED
        mock_has_graveyard_extension.return_value = False

        world = FakeWorld()
        state = FakeState([])
        result = get_max_possible_graveyard_points(state, world)

        self.assertEqual(0, result, f"No items should result in max graveyard 0")

    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_lawn_points_when_craftable(self, mock_can_build, mock_church_level, mock_has_graveyard_extension):
        def can_build_side_effect(item):
            return item == "LAWN"

        mock_can_build.side_effect = can_build_side_effect
        mock_church_level.return_value = ChurchLevel.OPEN
        mock_has_graveyard_extension.return_value = False

        world = FakeWorld()
        state = FakeState(["LAWN"])
        result = get_max_possible_graveyard_points(state, world)

        self.assertEqual(145, result, f"Only lawn should result in 145 graveyard points")
        # top row: 20 + 4 + 21 = 45
        # center row: 16 + 12 + 16 = 44
        # bot row: 28 + 12 + 16 = 56

    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_lawn_2x4_via_marble_flagstones(self, mock_can_build, mock_church_level, mock_has_extension):
        def can_build_side_effect(item):
            return item == "MARBLE_FLAGSTONES"

        mock_can_build.side_effect = can_build_side_effect
        mock_church_level.return_value = ChurchLevel.OPEN
        mock_has_extension.return_value = False

        world = FakeWorld()
        state = FakeState([])
        result = get_max_possible_graveyard_points(state, world)

        self.assertEqual(18, result, "2x4 lawns should be replaceable with marble flagstones")
        # r_top_left: 1 lawn 2x4 -> 1 marble flagstones -> 3 points
        # r_top_middle: 3 lawn 2x4 -> 3 marble flagstones -> 9 points
        # r_center_left: 1 lawn 2x4 -> 1 marble flagstones -> 3 points
        # r_center_right: 1 lawn 2x4 -> 1 marble flagstones -> 3 points
        # sum: 3 + 9 + 3 + 3 -> 18

    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_lantern_chooses_best_option(self, mock_can_build, mock_church_level, mock_has_graveyard_extension):
        def can_build_side_effect(item):
            return item in {"FLOWERBED", "LANTERN"}

        mock_can_build.side_effect = can_build_side_effect
        mock_church_level.return_value = ChurchLevel.OPEN
        mock_has_graveyard_extension.return_value = False

        world = FakeWorld()
        state = FakeState(["FLOWERBED", "LANTERN"])
        result = get_max_possible_graveyard_points(state, world)

        self.assertEqual(20, result, f"Expects 5 places with 4 points each")

    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_lantern_no_options(self, mock_can_build, mock_church_level, mock_has_extension):
        mock_can_build.return_value = False
        mock_church_level.return_value = ChurchLevel.OPEN
        mock_has_extension.return_value = False

        world = FakeWorld()
        state = FakeState([])
        result = get_max_possible_graveyard_points(state, world)

        # ensures no crash and lantern contributes 0
        self.assertEqual(0, result, "lantern places should contribute 0")

    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_both_sides_with_extension(self, mock_can_build, mock_church_level, mock_has_graveyard_extension):
        def can_build_side_effect(item):
            return item == "LAWN"

        mock_can_build.side_effect = can_build_side_effect
        mock_church_level.return_value = ChurchLevel.OPEN
        mock_has_graveyard_extension.return_value = True

        world = FakeWorld()
        state = FakeState(["LAWN"])
        result = get_max_possible_graveyard_points(state, world)

        self.assertEqual(322, result, "With graveyard extension, both sides need to be considered")
        # left
        # top row: 20 + 4 + 21 = 45
        # center row: 16 + 12 + 16 = 44
        # bot row: 28 + 12 + 16 = 56
        # right
        # top row: 28 + 21 + 28 = 77
        # center row: 16 + 12 + 16 = 44
        # bot row: 16 + 12 + 28 = 56
        # sum: 45 + 44 + 56 + 77 + 44 + 56 = 145 + 177 = 322

    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_stone_fence_bonus(self, mock_can_build, mock_church_level, mock_has_graveyard_extension):
        def can_build_side_effect(item):
            return item == "STONE_GRAVEYARD_FENCE"

        mock_can_build.side_effect = can_build_side_effect
        mock_church_level.return_value = ChurchLevel.BIG
        mock_has_graveyard_extension.return_value = False

        world = FakeWorld()
        state = FakeState(["STONE_GRAVEYARD_FENCE"])
        result = get_max_possible_graveyard_points(state, world)

        self.assertEqual(20, result, "Only stone fence should be calculated")

    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_wooden_fence_bonus(self, mock_can_build, mock_church_level, mock_has_graveyard_extension):
        def can_build_side_effect(item):
            return item == "WOODEN_GRAVEYARD_FENCE"

        mock_can_build.side_effect = can_build_side_effect
        mock_church_level.return_value = ChurchLevel.OPEN
        mock_has_graveyard_extension.return_value = False

        world = FakeWorld()
        state = FakeState(["WOODEN_GRAVEYARD_FENCE"])
        result = get_max_possible_graveyard_points(state, world)
        self.assertEqual(10, result, "Only wooden fence should be calculated")

    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_wooden_fence_blocked_when_closed(self, mock_can_build, mock_church_level, mock_has_extension):
        def can_build_side_effect(item):
            return item == "WOODEN_GRAVEYARD_FENCE"

        mock_can_build.side_effect = can_build_side_effect
        mock_church_level.return_value = ChurchLevel.CLOSED
        mock_has_extension.return_value = False

        world = FakeWorld()
        state = FakeState([])
        result = get_max_possible_graveyard_points(state, world)

        self.assertEqual(0, result, "fence shouldn't be possible without opening church")

    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_stone_fence_not_applied_when_church_small(self, mock_can_build, mock_church_level, mock_has_extension):
        def can_build_side_effect(item):
            return item == "STONE_GRAVEYARD_FENCE"

        mock_can_build.side_effect = can_build_side_effect
        mock_church_level.return_value = ChurchLevel.OPEN  # not BIG/CATHEDRAL
        mock_has_extension.return_value = False

        world = FakeWorld()
        state = FakeState([])
        result = get_max_possible_graveyard_points(state, world)

        self.assertEqual(0, result, "stone fence not possible with small church")

    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_cathedral_bonus(self, mock_can_build, mock_church_level, mock_has_graveyard_extension):
        mock_can_build.return_value = False
        mock_church_level.return_value = ChurchLevel.CATHEDRAL
        mock_has_graveyard_extension.return_value = False

        world = FakeWorld()

        state = FakeState([])
        result = get_max_possible_graveyard_points(state, world)

        self.assertEqual(5, result, "With only Cathedral accessible, only the bishop statue should be calculated")

    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_all_bonuses_stack(self, mock_can_build, mock_church_level, mock_has_graveyard_extension):
        def can_build_side_effect(item):
            return item == "STONE_GRAVEYARD_FENCE"

        mock_can_build.side_effect = can_build_side_effect
        mock_church_level.return_value = ChurchLevel.CATHEDRAL
        mock_has_graveyard_extension.return_value = False

        world = FakeWorld()
        state = FakeState(["STONE_GRAVEYARD_FENCE"])
        result = get_max_possible_graveyard_points(state, world)

        self.assertEqual(25, result, "Cathedral (bishop statue): 5 + Stone fence: 20")

    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_stone_columbarium_used(self, mock_can_build, mock_church_level, mock_has_extension):
        def can_build_side_effect(item):
            return item == "STONE_COLUMBARIUM"

        mock_can_build.side_effect = can_build_side_effect
        mock_church_level.return_value = ChurchLevel.OPEN
        mock_has_extension.return_value = True

        world = FakeWorld()
        state = FakeState([])
        result = get_max_possible_graveyard_points(state, world)

        self.assertEqual(432, result, "Should use stone columbariums (graveyard has 36 places, so 36*12 = 432")

    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_marble_columbarium_priority(self, mock_can_build, mock_church_level, mock_has_extension):
        def can_build_side_effect(item):
            return item in {"MARBLE_COLUMBARIUM", "STONE_COLUMBARIUM"}

        mock_can_build.side_effect = can_build_side_effect
        mock_church_level.return_value = ChurchLevel.OPEN
        mock_has_extension.return_value = False

        world = FakeWorld()
        state = FakeState([])
        result = get_max_possible_graveyard_points(state, world)

        self.assertEqual(300, result, "Should use marble columbariums over stone ones (right side has 15 places, so 15*20 = 300")

    @patch.object(GravePointCalculator, "calculate")
    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_grave_points_used(self, mock_can_build, mock_church_level, mock_has_extension, mock_grave_points):
        mock_can_build.return_value = False
        mock_church_level.return_value = ChurchLevel.OPEN
        mock_has_extension.return_value = False
        mock_grave_points.return_value = 10

        world = FakeWorld()
        state = FakeState([])
        result = get_max_possible_graveyard_points(state, world)

        self.assertEqual(440, result, "44 grave spots should result in 440 points")

    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_mixed_build_options(self, mock_can_build, mock_church_level, mock_has_extension):
        def side_effect(item):
            return item in {
                "LAWN",
                "STONE_COLUMBARIUM",
                "LANTERN",
                "WOODEN_GRAVEYARD_FENCE",
            }

        mock_can_build.side_effect = side_effect
        mock_church_level.return_value = ChurchLevel.BIG
        mock_has_extension.return_value = True

        world = FakeWorld()
        state = FakeState([])
        result = get_max_possible_graveyard_points(state, world)

        self.assertEqual(492, result)
        '''
        Calculate Graveyard: Chosen configuration for l_top_left: 'dict_keys(['columbarium'])' with 48 points
        Calculate Graveyard: Chosen configuration for l_top_middle: 'dict_keys(['columbarium', 'lawn 2x6', 'lawn 2x4'])' with 31 points
        Calculate Graveyard: Chosen configuration for l_center_left: 'dict_keys(['columbarium'])' with 24 points
        Calculate Graveyard: Chosen configuration for l_center_middle: 'dict_keys(['columbarium', 'lawn 2x6'])' with 16 points
        Calculate Graveyard: Chosen configuration for l_bot_left: 'dict_keys(['columbarium'])' with 24 points
        Calculate Graveyard: Chosen configuration for l_bot_right: 'dict_keys(['columbarium', 'lawn 2x6'])' with 40 points
        Calculate Graveyard: Chosen configuration for r_top_left: 'dict_keys(['columbarium', 'grave', 'lantern'])' with 28 points
        Calculate Graveyard: Chosen configuration for r_top_right: 'dict_keys(['lawn 2x3', 'lantern'])' with 8 points
        Calculate Graveyard: Chosen configuration for l_top_right: 'dict_keys(['columbarium'])' with 48 points
        Calculate Graveyard: Chosen configuration for l_center_right: 'dict_keys(['columbarium'])' with 24 points
        Calculate Graveyard: Chosen configuration for l_bot_middle: 'dict_keys(['columbarium', 'lawn 2x6'])' with 16 points
        Calculate Graveyard: Chosen configuration for r_top_middle: 'dict_keys(['columbarium', 'lawn 2x6', 'lawn 2x4'])' with 31 points
        Calculate Graveyard: Chosen configuration for r_center_left: 'dict_keys(['columbarium'])' with 24 points
        Calculate Graveyard: Chosen configuration for r_center_middle: 'dict_keys(['columbarium', 'lawn 2x6'])' with 16 points
        Calculate Graveyard: Chosen configuration for r_center_right: 'dict_keys(['columbarium'])' with 24 points
        Calculate Graveyard: Chosen configuration for r_bot_left: 'dict_keys(['columbarium', 'lawn 2x6'])' with 40 points
        Calculate Graveyard: Chosen configuration for r_bot_middle: 'dict_keys(['columbarium', 'lawn 2x6'])' with 16 points
        Calculate Graveyard: Chosen configuration for r_bot_right: 'dict_keys(['columbarium'])' with 24 points
        '''

    @patch.object(GravePointCalculator, "calculate")
    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_max_vanilla_old(self, mock_can_build, mock_church_level, mock_has_extension, mock_grave_points):
        mock_can_build.return_value = True
        mock_church_level.return_value = ChurchLevel.CATHEDRAL
        mock_has_extension.return_value = True
        mock_grave_points.return_value = 12

        world = FakeWorld({
            "stranger_sins": False,
            "game_of_crone": False,
            "better_save_soul": False,
        })
        state = FakeState([])
        result = get_max_possible_graveyard_points(state, world)

        self.assertEqual(1258, result)
        # see https://graveyardkeeper.fandom.com/wiki/The_Graveyard#Maximum_Rating


    @patch.object(GravePointCalculator, "calculate")
    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_max_vanilla(self, mock_can_build, mock_church_level, mock_has_extension, mock_grave_points):
        mock_can_build.return_value = True
        mock_church_level.return_value = ChurchLevel.CATHEDRAL
        mock_has_extension.return_value = True
        mock_grave_points.return_value = 16

        world = FakeWorld({
            "stranger_sins": False,
            "game_of_crone": False,
            "better_save_soul": False,
        })
        state = FakeState([])
        result = get_max_possible_graveyard_points(state, world)

        self.assertEqual(1594, result)
        # see https://graveyardkeeper.fandom.com/wiki/The_Graveyard#Maximum_Rating


    @patch.object(GravePointCalculator, "calculate")
    @patch.object(GraveyardPointCalculator, "_has_graveyard_extension")
    @patch.object(GraveyardPointCalculator, "_get_church_level")
    @patch.object(GraveyardPointCalculator, "_can_build")
    def test_max_vanilla_dlcs(self, mock_can_build, mock_church_level, mock_has_extension, mock_grave_points):
        mock_can_build.return_value = True
        mock_church_level.return_value = ChurchLevel.CATHEDRAL
        mock_has_extension.return_value = True
        mock_grave_points.return_value = 26

        world = FakeWorld()
        state = FakeState([])
        result = get_max_possible_graveyard_points(state, world)

        self.assertEqual(1594 + 840 + 48 + 2, result)
        # see https://graveyardkeeper.fandom.com/wiki/The_Graveyard#Maximum_Rating
        # + 10 more per grave (84 graves)
        # + 6 more per columbarium (replaced by grave, 8 columbariums)
        # + 1 for longer lawns occupying freed space from shrinking columbariums to graves (2 lawns can be stretched)
        # = 840 + 48 + 2


'''
@classvar_matrix(
    church_level=[
        ChurchLevel.CLOSED,
        ChurchLevel.OPEN,
        ChurchLevel.BIG,
        ChurchLevel.CATHEDRAL,
    ],
    has_extension=[False, True],
    lawn=[
        False,
        True,
    ],
    marble_flagstones=[
        False,
        True,
    ],
    stone_columbarium=[
        False,
        True,
    ],
    marble_columnbarium=[
        False,
        True,
    ],
    flowerbed=[
        False,
        True,
    ],
    lantern=[
        False,
        True,
    ],
    wooden_prayer_station=[
        False,
        True,
    ],
    stone_prayer_station=[
        False,
        True,
    ],
    wooden_fence=[
        False,
        True,
    ],
    stone_fence=[
        False,
        True,
    ],
    grave_points=[
        0,
        5,
        10,
    ],
)
class TestGraveyardPointsMatrix(unittest.TestCase):
    church_level: ClassVar[ChurchLevel]
    has_extension: ClassVar[bool]
    lawn: ClassVar[bool]
    marble_flagstones: ClassVar[bool]
    stone_columbarium: ClassVar[bool]
    marble_columnbarium: ClassVar[bool]
    flowerbed: ClassVar[bool]
    lantern: ClassVar[bool]
    wooden_prayer_station: ClassVar[bool]
    stone_prayer_station: ClassVar[bool]
    wooden_fence: ClassVar[bool]
    stone_fence: ClassVar[bool]
    grave_points: ClassVar[int]

    @patch("worlds.graveyard_keeper.rules.get_max_grave_points")
    @patch("worlds.graveyard_keeper.rules.has_graveyard_extension")
    @patch("worlds.graveyard_keeper.rules.get_max_church_level")
    @patch("worlds.graveyard_keeper.rules.can_build")
    def test_matrix(
        self,
        mock_can_build,
        mock_church_level,
        mock_has_extension,
        mock_grave_points,
    ):
        # --- configure mocks ---

        def can_build_side_effect(item, state, player):
            # lawn logic
            if item == "LAWN":
                return self.lawn
            if item == "MARBLE_FLAGSTONES":
                return self.marble_flagstones

            # columbarium
            if item == "STONE_COLUMBARIUM":
                return self.stone_columbarium
            if item == "MARBLE_COLUMBARIUM":
                return self.marble_columnbarium

            # lantern group
            if item == "FLOWERBED":
                return self.flowerbed
            if item == "LANTERN":
                return self.lantern
            if item == "WOODEN_PRAYER_STATION":
                return self.wooden_prayer_station
            if item == "STONE_PRAYER_STATION":
                return self.stone_prayer_station

            # fences
            if item == "WOODEN_GRAVEYARD_FENCE":
                return self.wooden_fence
            if item == "STONE_GRAVEYARD_FENCE":
                return self.stone_fence

            return False

        mock_can_build.side_effect = can_build_side_effect
        mock_church_level.return_value = self.church_level
        mock_has_extension.return_value = self.has_extension
        mock_grave_points.return_value = self.grave_points

        world = FakeWorld()
        state = FakeState([])

        result = get_max_possible_graveyard_points(state, world)

        # sanity tests
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)

        if self.church_level == ChurchLevel.CATHEDRAL:
            self.assertGreaterEqual(result, 5, "CATHEDRAL gives at least +5")

        if self.stone_fence and self.church_level in {ChurchLevel.BIG, ChurchLevel.CATHEDRAL}:
            self.assertGreaterEqual(result, 20, "stone fence only applies at BIG+")

        if self.wooden_fence and self.church_level != ChurchLevel.CLOSED:
            self.assertGreaterEqual(result, 10, "wooden fence requires not CLOSED")
'''


class TestGetMaxGravePoints(unittest.TestCase):

    def setUp(self):
        self.fake_items = {k: FakeItem(k) for k in [
        "ITEM_LEARN_CREATE_PROGRESSIVE_WOODEN_GRAVE_MARKER",
        "ITEM_LEARN_CREATE_PROGRESSIVE_STONE_GRAVE_MARKER",
        "ITEM_LEARN_CREATE_PROGRESSIVE_MARBLE_GRAVE_MARKER",
        "ITEM_LEARN_CREATE_WOODEN_GRAVE_FENCE",
        "ITEM_LEARN_CREATE_PROGRESSIVE_STONE_GRAVE_FENCE",
        "ITEM_LEARN_CREATE_PROGRESSIVE_MARBLE_GRAVE_FENCE",
        "ITEM_LEARN_EXTRACT_FAT",
        "ITEM_LEARN_EXTRACT_BLOOD",
    ]}

    @patch("worlds.graveyard_keeper.rules.data")
    @patch.object(GravePointCalculator, "_can_craft")
    def test_returns_zero_without_corpse(self, mock_can_craft, mock_data):
        mock_can_craft.return_value = False
        mock_data.items = self.fake_items

        state = FakeState(items=[])
        world = FakeWorld()

        result = GravePointCalculator(state, world).calculate()
        self.assertEqual(0, result)

    @patch("worlds.graveyard_keeper.rules.data")
    @patch.object(GravePointCalculator, "_can_craft")
    def test_decoration_caps_result(self, mock_can_craft, mock_data):
        mock_can_craft.return_value = True
        mock_data.items = self.fake_items

        state = FakeState(items={"CERAMIC_BOWL"}, counts={})
        world = FakeWorld()

        result = GravePointCalculator(state, world).calculate()
        self.assertEqual(0, result, "Even with strong corpse, result should be capped by decoration.")

    @patch("worlds.graveyard_keeper.rules.data")
    @patch.object(GravePointCalculator, "_can_craft")
    def test_more_decorations_never_reduce_score(self, mock_can_craft, mock_data):
        def can_craft_side_effect(item):
            return item == "ITEM_CORPSE"

        mock_can_craft.side_effect = can_craft_side_effect
        mock_data.items = self.fake_items

        base_state = FakeState([], counts={})
        better_state = FakeState([], counts={
            "ITEM_LEARN_CREATE_PROGRESSIVE_STONE_GRAVE_MARKER": 6
        })

        world = FakeWorld()

        base = GravePointCalculator(base_state, world).calculate()
        better = GravePointCalculator(better_state, world).calculate()

        self.assertGreaterEqual(better, base, "Monotonicity: more decoration should not reduce result.")

    @patch("worlds.graveyard_keeper.rules.data")
    @patch.object(GravePointCalculator, "_can_craft")
    def test_stone_marker_with_dlc(self, mock_can_craft, mock_data):
        def can_craft_side_effect(item):
            return item == "ITEM_CORPSE"

        mock_can_craft.side_effect = can_craft_side_effect
        mock_data.items = self.fake_items

        counts = {
            "ITEM_LEARN_CREATE_PROGRESSIVE_STONE_GRAVE_MARKER": 4
        }
        state = FakeState(items=[], counts=counts)
        world_no_dlc = FakeWorld(options={
            "game_of_crone": False,
            "better_save_soul": False,
        })
        world_with_dlc = FakeWorld(options={
            "game_of_crone": True,
            "better_save_soul": False,
        })

        result_no = GravePointCalculator(state, world_no_dlc).calculate()
        result_yes = GravePointCalculator(state, world_with_dlc).calculate()

        self.assertGreaterEqual(result_yes, result_no)

    @patch("worlds.graveyard_keeper.rules.data")
    @patch.object(GravePointCalculator, "_can_craft")
    def test_red_skulls_clamped_to_zero(self, mock_can_craft, mock_data):
        def can_craft_side_effect(item):
            return item == "ITEM_CORPSE"

        mock_can_craft.side_effect = can_craft_side_effect
        mock_data.items = self.fake_items

        state = FakeState([])
        world = FakeWorld()

        result = GravePointCalculator(state, world).calculate()

        self.assertEqual(0, result)