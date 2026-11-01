from __future__ import annotations

from BaseClasses import CollectionState
from rule_builder.rules import And, Has, Rule
from .custom_rules import CanGet
from ..data import data, CRAFTING_EVENT_PREFIX, load_json_data
from ..models import ChurchLevel
from .grave_calculator import GravePointCalculator


GRAVEYARD_RATING = load_json_data("logic/graveyard_rating.json")


class GraveyardPointCalculator:
    """Best rating among the authored simultaneous patch configurations."""

    @staticmethod
    def dependency_rule() -> Rule:
        return And(
            GravePointCalculator.dependency_rule(),
            *(CanGet("BUILDABLE_" + key) for key in (
                *GRAVEYARD_RATING["decorations"], *GRAVEYARD_RATING["fences"],
            )),
            Has(data.items[GRAVEYARD_RATING["extension_item"]].label),
            *(Has(data.events[key].item_label) for key in (
                *GRAVEYARD_RATING["church_events"].values(), GRAVEYARD_RATING["statue_event"],
            )),
        )

    def __init__(self, state: CollectionState, world, crafting_rules=None):
        self.state = state
        self.world = world
        self.player = world.player
        self.crafting_rules = crafting_rules

    def calculate(self) -> int:
        points = self._get_base_points()
        total = sum(self._get_best_configuration_score(configurations, points)
                    for configurations in self._get_patches_configurations().values())
        church_level = self._get_church_level()
        return total + self._get_fence_bonus(church_level) + self._get_statue_bonus(church_level)

    def _get_patches_configurations(self) -> dict[str, list[dict[str, int]]]:
        extended = self._has_graveyard_extension()
        return {name: patch["configurations"] for name, patch in GRAVEYARD_RATING["patches"].items()
                if extended or not patch["requires_extension"]}

    def _get_base_points(self) -> dict[str, int]:
        points = {"lawn 2x3": 0, "lawn 2x4": 0, "lawn 2x6": 0,
                  "lantern": 0, "columbarium": 0, "grave": self._get_max_grave_points()}
        for key, scores in GRAVEYARD_RATING["decorations"].items():
            if self._can_build(key):
                for group, score in scores.items():
                    points[group] = max(points[group], score)
        return points

    @staticmethod
    def _get_best_configuration_score(configurations, points) -> int:
        return max((sum(points[group] * count for group, count in configuration.items())
                    for configuration in configurations), default=0)

    def _get_fence_bonus(self, church_level: ChurchLevel) -> int:
        # The Bishop unlocks the wooden fence after the big-church upgrade;
        # building that fence unlocks the stone upgrade. Scores replace each other.
        if church_level not in (ChurchLevel.BIG, ChurchLevel.CATHEDRAL):
            return 0
        if not self._can_build("WOODEN_GRAVEYARD_FENCE"):
            return 0
        return GRAVEYARD_RATING["fences"][
            "STONE_GRAVEYARD_FENCE" if self._can_build("STONE_GRAVEYARD_FENCE") else "WOODEN_GRAVEYARD_FENCE"
        ]

    def _get_statue_bonus(self, church_level: ChurchLevel) -> int:
        return (GRAVEYARD_RATING["statue_points"]
                if self.state.has(data.events[GRAVEYARD_RATING["statue_event"]].item_label, self.player) else 0)

    def _can_build(self, key: str) -> bool:
        return self.state.has(data.events[CRAFTING_EVENT_PREFIX + "BUILDABLE_" + key].item_label, self.player)

    def _get_max_grave_points(self) -> int:
        return max(0, GravePointCalculator(self.state, self.world, self.crafting_rules).calculate())

    def _get_church_level(self) -> ChurchLevel:
        return get_max_church_level(self.state, self.player)

    def _has_graveyard_extension(self) -> bool:
        return has_graveyard_extension(self.state, self.player)


def has_graveyard_extension(state: CollectionState, player: int) -> bool:
    return state.has(data.items[GRAVEYARD_RATING["extension_item"]].label, player)


def get_max_church_level(state: CollectionState, player: int) -> ChurchLevel:
    level = ChurchLevel.CLOSED
    for name, event in GRAVEYARD_RATING["church_events"].items():
        if state.has(data.events[event].item_label, player):
            level = ChurchLevel[name]
    return level
