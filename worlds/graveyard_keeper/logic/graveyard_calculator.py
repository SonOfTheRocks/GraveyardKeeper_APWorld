from __future__ import annotations

from typing import Dict, List

from BaseClasses import CollectionState
from .custom_rules import CanCraft
from ..data import data, CRAFTING_EVENT_PREFIX
from ..models import ChurchLevel
from .grave_calculator import GravePointCalculator


class GraveyardPointCalculator:
    def __init__(self, state: CollectionState, world):
        self.state = state
        self.world = world
        self.player = world.player

    def calculate(self) -> int:
        church_level = self._get_church_level()

        patches = self._get_patches_configurations()
        points = self._get_base_points()

        total = 0

        for spot_name, configurations in patches.items():
            best = self._get_best_configuration_score(configurations, points)
            total += best

        fence_bonus = self._get_fence_bonus(church_level)
        statue_bonus = self._get_statue_bonus(church_level)

        total += fence_bonus
        total += statue_bonus

        #print(
        #    f"Calculate max graveyard points:"
        #    + f" main: {total - (fence_bonus + statue_bonus)}"
        #    + f", fence: {fence_bonus}"
        #    + f", statue: {statue_bonus}"
        #    + f" -> {total}"
        #)
        return total

    def _get_patches_configurations(self) -> Dict[str, List[Dict[str, int]]]:
        # TODO: Smaller patches if no woodcutter tech
        base = {
            # 8 x 10
            "l_top_left": [
                {"columbarium": 2, "grave": 4, "lawn 2x4": 1, "lantern": 1},
                {"columbarium": 2, "grave": 4, "lawn 2x6": 1},
                {"columbarium": 4},
                {"grave": 6, "lawn 2x6": 1, "lantern": 1},
                {"grave": 6, "lawn 2x6": 1, "lawn 2x4": 1},
                {"lawn 2x6": 4, "lawn 2x4": 4},
            ],
            # 7 x 10
            "l_top_middle": [
                {"columbarium": 2, "grave": 4},
                {"columbarium": 2, "lawn 2x6": 1, "lawn 2x4": 1},
                {"grave": 6},
                {"lawn 2x6": 3, "lawn 2x4": 3},
            ],
            # 8 x 6
            "l_center_left": [
                {"columbarium": 2},
                {"grave": 4, "lawn 2x4": 1, "lantern": 1},
                {"grave": 4, "lawn 2x6": 1},
                {"lawn 2x6": 4},
            ],
            # 7 x 6
            "l_center_middle": [
                {"columbarium": 1, "lawn 2x6": 1},
                {"columbarium": 1, "grave": 2},
                {"grave": 4},
                {"lawn 2x6": 3},
            ],
            # 8 x 6
            "l_bot_left": [
                {"columbarium": 2},
                {"grave": 4, "lawn 2x6": 1},
                {"lawn 2x6": 4},
            ],
            # 15 x 6
            "l_bot_right": [
                {"columbarium": 3, "lawn 2x6": 1},
                {"grave": 10},
                {"lawn 2x6": 7},
            ],
            # 3x3 + 2x2 + 3x3 + 8x6
            "r_top_left": [
                {"grave": 6, "lantern": 2, "lawn 2x4": 1},
                {"columbarium": 2, "grave": 2, "lantern": 1},
                {"lawn 2x3": 2, "lantern": 2, "lawn 2x6": 2, "lawn 2x4": 1},
                {"lawn 2x3": 2, "lantern": 1, "lawn 2x6": 4},
            ],
            # 3x3 + 2x2 + 3x3
            "r_top_right": [
                {"grave": 2, "lantern": 1},
                {"lawn 2x3": 2, "lantern": 1},
            ],
        }

        # mirror regions
        base.update({
            "l_top_right": base["l_top_left"],
            "l_center_right": base["l_center_left"],
            "l_bot_middle": base["l_center_middle"],
            "r_top_middle": base["l_top_middle"],
            "r_center_left": base["l_center_left"],
            "r_center_middle": base["l_center_middle"],
            "r_center_right": base["l_center_left"],
            "r_bot_left": base["l_bot_right"],
            "r_bot_middle": base["l_center_middle"],
            "r_bot_right": base["l_bot_left"],
        })

        if not self._has_graveyard_extension():
            return {k: v for k, v in base.items() if k.startswith("r_")}

        return base

    def _get_base_points(self) -> Dict[str, int]:
        state = self.state
        player = self.player

        points = {
            "lawn 2x6": 4 if self._can_build("LAWN") else 0,
            "lawn 2x4": 3 if self._can_build("LAWN") or self._can_build("MARBLE_FLAGSTONES") else 0,
            "lawn 2x3": 2 if self._can_build("LAWN") else 0,
            "grave": self._get_max_grave_points(),
            "columbarium": self._get_columbarium_points(),
            "lantern": self._get_lantern_points(),
        }

        return points

    def _get_best_configuration_score(self, configurations, points) -> int:
        best = 0

        for config in configurations:
            score = sum(points[item] * count for item, count in config.items())
            best = max(best, score)

        return best

    def _get_lantern_points(self) -> int:
        options = {
            "FLOWERBED": 2,
            "LANTERN": 4,
            "WOODEN_PRAYER_STATION": 2,
            "STONE_PRAYER_STATION": 4,
        }

        return max(
            [pts for key, pts in options.items() if self._can_build(key)],
            default=0
        )

    def _get_columbarium_points(self) -> int:
        if self._can_build("MARBLE_COLUMBARIUM"):
            return 20
        if self._can_build("STONE_COLUMBARIUM"):
            return 12
        return 0

    def _get_fence_bonus(self, church_level: ChurchLevel) -> int:
        if church_level in [ChurchLevel.BIG, ChurchLevel.CATHEDRAL] and self._can_build("STONE_GRAVEYARD_FENCE"):
            return 20
        if church_level != ChurchLevel.CLOSED and self._can_build("WOODEN_GRAVEYARD_FENCE"):
            return 10
        return 0

    def _get_statue_bonus(self, church_level: ChurchLevel) -> int:
        return 5 if church_level == ChurchLevel.CATHEDRAL else 0

    def _can_build(self, item:str) -> bool:
        return CanCraft("BUILDABLE_" + item).resolve(self.world)
        return self.state.has(
            data.events[CRAFTING_EVENT_PREFIX + "BUILDABLE_" + item].item_label,
            self.player
        )

    def _get_max_grave_points(self) -> int:
        return GravePointCalculator(self.state, self.world).calculate()

    def _get_church_level(self) -> int:
        return get_max_church_level(self.state, self.player)

    def _has_graveyard_extension(self) -> bool:
        return has_graveyard_extension()


# TODO: Actually implement
def has_graveyard_extension() -> bool:
    return False

# TODO: Actually implement
def get_max_church_level(state: CollectionState, player: int) -> ChurchLevel:
    return ChurchLevel.BIG

def can_craft(item: str, state: CollectionState, player: int) -> bool:
    return state.has(data.events[CRAFTING_EVENT_PREFIX +  item].item_label, player)

def can_build(item: str, state: CollectionState, player: int) -> bool:
    return state.has(data.events[CRAFTING_EVENT_PREFIX + "BUILDABLE_" + item].item_label, player)
