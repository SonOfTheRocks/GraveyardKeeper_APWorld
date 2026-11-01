from __future__ import annotations

from BaseClasses import CollectionState
from rule_builder.rules import And, Has, Rule
from .custom_rules import CanCraft
from ..data import data, CRAFTING_EVENT_PREFIX


class GravePointCalculator:
    CRAFTING_INPUTS = (
        "ITEM_CORPSE", "ITEM_CERAMIC_BOWLS", "ITEM_MODIFIED_FLESH",
        "ITEM_MODIFIED_SKIN", "ITEM_MODIFIED_FAT", "ITEM_MODIFIED_BRAIN",
        "ITEM_MODIFIED_INTESTINE", "ITEM_MODIFIED_HEART", "ITEM_MODIFIED_BLOOD",
        "ITEM_LYE_INJECTION", "ITEM_GLUE_INJECTION", "ITEM_SILVER_INJECTION",
        "ITEM_GOLD_INJECTION",
    )

    @staticmethod
    def dependency_rule() -> Rule:
        """Declare every state input read by calculate, including alternatives."""
        return And(
            *(CanCraft(key) for key in GravePointCalculator.CRAFTING_INPUTS),
            *(Has(data.items[key].label) for key in (
                "ITEM_LEARN_CREATE_PROGRESSIVE_WOODEN_GRAVE_MARKER",
                "ITEM_LEARN_CREATE_PROGRESSIVE_STONE_GRAVE_MARKER",
                "ITEM_LEARN_CREATE_PROGRESSIVE_MARBLE_GRAVE_MARKER",
                "ITEM_LEARN_CREATE_WOODEN_GRAVE_FENCE",
                "ITEM_LEARN_CREATE_PROGRESSIVE_STONE_GRAVE_FENCE",
                "ITEM_LEARN_CREATE_PROGRESSIVE_MARBLE_GRAVE_FENCE",
                "ITEM_LEARN_EXTRACT_FAT", "ITEM_LEARN_EXTRACT_BLOOD",
            )),
        )

    def __init__(self, state: CollectionState, world, crafting_rules=None):
        self.state = state
        self.world = world
        self.player = world.player
        self.crafting_rules = crafting_rules

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

    def _progressive_score(self, item_key, base, game_of_crone=None, better_save_soul=None) -> int:
        # Earlier stages stay unlocked after later receipts, including stages
        # belonging to a DLC that is disabled in this world.
        scores = dict(base)
        if self.world.options.game_of_crone:
            scores.update(game_of_crone or {})
        if self.world.options.better_save_soul:
            scores.update(better_save_soul or {})
        count = self._count(item_key)
        return max((score for stage, score in scores.items() if stage <= count), default=0)

    def _wood_tombstone(self) -> int:
        return self._progressive_score("ITEM_LEARN_CREATE_PROGRESSIVE_WOODEN_GRAVE_MARKER", {1: 1, 2: 2})

    def _stone_tombstone(self) -> int:
        return self._progressive_score(
            "ITEM_LEARN_CREATE_PROGRESSIVE_STONE_GRAVE_MARKER",
            {1: 2, 2: 3, 3: 3, 5: 4, 6: 4, 7: 5, 8: 5},
            {4: 4, 9: 6, 10: 7}, {11: 10, 12: 12},
        )

    def _marble_tombstone(self) -> int:
        return self._progressive_score(
            "ITEM_LEARN_CREATE_PROGRESSIVE_MARBLE_GRAVE_MARKER",
            {1: 5, 2: 6, 3: 6, 4: 6, 5: 7, 6: 7},
            {7: 8, 8: 9}, {9: 13, 10: 15},
        )

    def _get_fence_points(self) -> int:
        return max(1 if self._has("ITEM_LEARN_CREATE_WOODEN_GRAVE_FENCE") else 0,
                   self._stone_fence(), self._marble_fence())

    def _stone_fence(self) -> int:
        return self._progressive_score(
            "ITEM_LEARN_CREATE_PROGRESSIVE_STONE_GRAVE_FENCE",
            {1: 2, 2: 3}, {3: 3, 4: 4, 5: 5}, {6: 6, 7: 7, 8: 8},
        )

    def _marble_fence(self) -> int:
        return self._progressive_score(
            "ITEM_LEARN_CREATE_PROGRESSIVE_MARBLE_GRAVE_FENCE",
            {1: 4, 2: 5}, {3: 5, 4: 6, 5: 7}, {6: 9, 7: 10, 8: 11},
        )

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
        return Has(data.items[item_key].label, self.world).resolve(self.world)

    def _can_craft(self, item_key: str) -> bool:
        if self.crafting_rules is not None:
            return self.crafting_rules[item_key](self.state)
        return CanCraft(item_key).resolve(self.world)(self.state)
