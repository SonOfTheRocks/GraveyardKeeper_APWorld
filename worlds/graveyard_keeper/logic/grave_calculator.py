from __future__ import annotations

from BaseClasses import CollectionState
from ..data import data, CRAFTING_EVENT_PREFIX


class GravePointCalculator:
    def __init__(self, state: CollectionState, world):
        self.state = state
        self.world = world
        self.player = world.player

    def calculate(self) -> int:
        if not self._can_craft("ITEM_CORPSE"):
            return 0

        decoration = self._get_decoration_points()
        white, red = self._get_skulls()

        red = max(0, red)
        max_grave_points = min(white, decoration - red)

        #print(
        #    f"Calculate max grave points: white_skulls: {white}"
        #    + f", red_skulls: {red}"
        #    + f", max_decoration_points: {decoration}"
        #    + f" -> {max_grave_points}"
        #)
        return max_grave_points

    def _get_decoration_points(self) -> int:
        return self._get_tombstone_points() + self._get_fence_points()

    def _get_tombstone_points(self) -> int:
        values = []

        values.append(self._wood_tombstone())
        values.append(self._stone_tombstone())
        values.append(self._marble_tombstone())

        return max(values)

    def _wood_tombstone(self) -> int:
        n = self._count("ITEM_LEARN_CREATE_PROGRESSIVE_WOODEN_GRAVE_MARKER")

        match n:
            case 1 | 2: return n
            case _: return 0

    def _stone_tombstone(self) -> int:
        n = self._count("ITEM_LEARN_CREATE_PROGRESSIVE_STONE_GRAVE_MARKER")
        result = 0

        match n:
            case 1: result = 2
            case 2 | 3: result = 3
            case 5 | 6: result = 4
            case 7 | 8: result = 5

        if self.world.options.game_of_crone:
            match n:
                case 4: result = max(result, 4)
                case 9 | 10: result = max(result, n-3)

        if self.world.options.better_save_soul:
            match n:
                case 11: result = max(result, 10)
                case 12: result = max(result, 12)

        return result

    def _marble_tombstone(self) -> int:
        n = self._count("ITEM_LEARN_CREATE_PROGRESSIVE_MARBLE_GRAVE_MARKER")

        result = 0

        match n:
            case 1: result = 5
            case 2 | 3 | 4: result = 6
            case 5 | 6: result = 7

        if self.world.options.game_of_crone:
            match n:
                case 7 | 8: result = max(result, n+1)

        if self.world.options.better_save_soul:
            match n:
                case 9: result = max(result, 13)
                case 10: result = max(result, 15)

        return result

    def _get_fence_points(self) -> int:
        values = []

        if self._has("ITEM_LEARN_CREATE_WOODEN_GRAVE_FENCE"):
            values.append(1)
        values.append(self._stone_fence())
        values.append(self._marble_fence())

        return max(values)

    def _stone_fence(self) -> int:
        n = self._count("ITEM_LEARN_CREATE_PROGRESSIVE_STONE_GRAVE_FENCE")
        result = 0

        match n:
            case 1 | 2: result = max(result, n+1)

        if self.world.options.game_of_crone:
            match n:
                case 3 | 4 | 5: result = max(result, n)

        if self.world.options.better_save_soul:
            match n:
                case 6 | 7 | 8: result = max(result, n)

        return result

    def _marble_fence(self):
        n = self._count("ITEM_LEARN_CREATE_PROGRESSIVE_MARBLE_GRAVE_FENCE")
        result = 0

        match n:
            case 1 | 2: result = max(result, n+3)

        if self.world.options.game_of_crone:
            match n:
                case 3 | 4 | 5: result = max(result, n+2)

        if self.world.options.better_save_soul:
            match n:
                case 6 | 7 | 8: result = max(result, n+3)

        return result

    def _get_skulls(self) -> tuple[int, int]:
        def _organ(item, success_white, fallback_white, success_red = 0, fallback_red = 0, high_level_corpse = False):
            nonlocal white
            nonlocal red
            if self._can_craft(item) or high_level_corpse:
                white += success_white
                red += success_red
            else:
                white += fallback_white
                red += fallback_red

        def _injection(item, success_white, success_red):
            nonlocal white
            nonlocal red
            if self._can_craft(item):
                white += success_white
                red += success_red

        # corpse tier 0-0: at beginning
        # corpse tier +(1, 1): after 20 bowls@bishop (opening church)
        # corpse tier +(1, 1): during plague
        # corpse tier +(0, 1): after 2nd witch burning (+talking to inquisitor and learning about dark organs)

        white = 0
        red = 0

        # TODO: Use event
        church_opened = self._can_craft("ITEM_CERAMIC_BOWLS")

        _organ("ITEM_MODIFIED_FLESH", +3, +1)
        _organ("ITEM_MODIFIED_SKIN", +3, +1, 0, -1)
        _organ("ITEM_MODIFIED_FAT", +3, -1, 0, +1)
        _organ("ITEM_MODIFIED_BRAIN", +3, +1, -2, 0, church_opened)
        _organ("ITEM_MODIFIED_INTESTINE", +3, +1, -2, 0, church_opened)
        _organ("ITEM_MODIFIED_HEART", +3, +1, -2, 0, church_opened)

        if self._has("ITEM_LEARN_EXTRACT_FAT") and not self._can_craft("ITEM_MODIFIED_FAT"):
            white += 1; red -= 1
        if self._has("ITEM_LEARN_EXTRACT_BLOOD") and not self._can_craft("ITEM_MODIFIED_BLOOD"):
            white += 1; red -= 1

        _injection("ITEM_LYE_INJECTION", +1, +1)
        _injection("ITEM_GLUE_INJECTION", +1, 0)
        _injection("ITEM_SILVER_INJECTION", +1, -1)
        _injection("ITEM_GOLD_INJECTION", +2, -2)

        return white, red

    def _count(self, item_key: str) -> int:
        return self.state.count(data.items[item_key].label, self.player)

    def _has(self, item_key: str) -> bool:
        return self.state.has(data.items[item_key].label, self.player)

    def _can_craft(self, item_key: str) -> bool:
        return self.state.has(data.events[CRAFTING_EVENT_PREFIX + item_key].item_label, self.player)
