from dataclasses import dataclass
from typing import override

from BaseClasses import CollectionState
from rule_builder.rules import And, CanReachRegion, Has, Rule
from ..data import CRAFTING_EVENT_PREFIX, data, load_json_data
from ..models import ChurchLevel
from .custom_rules import CanGet, GKRule


CHURCH_RATING = load_json_data("logic/church_rating.json")
CHURCH_UPGRADES = {
    ChurchLevel.BIG: "EVENT_BISHOP_UPGRADE_TO_BIG_CHURCH",
    ChurchLevel.CATHEDRAL: "EVENT_BISHOP_REPORT_CATHEDRAL_UPGRADE",
}


class ChurchPointCalculator:
    """Best simultaneously buildable church rating, including renewable consumables.

    Patch alternatives and native object scores are documented in CHURCH_RATING.md.
    Quantities of renewable building materials/consumables are not AP requirements.
    """

    def __init__(self, state: CollectionState, player: int):
        self.state = state
        self.player = player

    @staticmethod
    def dependency_rule() -> Rule:
        return And(
            *(CanGet(key) for key in CHURCH_RATING["furniture"]),
            *(CanGet(key) for key in CHURCH_RATING["consumables"]),
            *(Has(data.events[key].item_label) for key in CHURCH_UPGRADES.values()),
        )

    def calculate(self) -> int:
        level = ChurchLevel.OPEN
        for upgrade, event in CHURCH_UPGRADES.items():
            if self.state.has(data.events[event].item_label, self.player):
                level = upgrade

        def obtainable(key: str) -> bool:
            return self.state.has(data.events[CRAFTING_EVENT_PREFIX + key].item_label, self.player)

        candle = max((points for key, points in CHURCH_RATING["consumables"].items()
                      if key.startswith("ITEM_CANDLE_") and obtainable(key)), default=0)
        incense = max((points for key, points in CHURCH_RATING["consumables"].items()
                       if key.startswith("ITEM_INCENSE") and obtainable(key)), default=0)
        scores: dict[str, int] = {}
        for key, furniture in CHURCH_RATING["furniture"].items():
            if not obtainable(key):
                continue
            points = furniture["points"] + furniture.get("candle_slots", 0) * candle
            if furniture["group"] == "incense":
                points += incense
            group = furniture["group"]
            scores[group] = max(scores.get(group, 0), points)

        # The two original benches remain usable without receiving their blueprint.
        total = CHURCH_RATING["base_points"] + max(
            CHURCH_RATING["starting_benches"],
            CHURCH_RATING["bench_spaces"] * scores.get("bench", 0),
        )
        for patch in CHURCH_RATING["patches"]:
            if level.value < ChurchLevel[patch["minimum_level"]].value:
                continue
            total += patch["count"] * max(
                (sum(count * scores.get(group, 0) for group, count in alternative.items())
                 for alternative in patch["configurations"]), default=0,
            )
        return total


@dataclass
class HasChurchRating(GKRule, game="Graveyard Keeper"):
    rating: int

    @override
    def _instantiate(self, world) -> Rule.Resolved:
        dependencies = ChurchPointCalculator.dependency_rule().resolve(world)
        return And.from_resolved(world, [
            CanReachRegion(data.regions["REGION_CHURCH"].label).resolve(world),
            self.Resolved(self.rating, tuple(sorted(dependencies.item_dependencies())),
                          player=world.player, caching_enabled=getattr(world, "rule_caching_enabled", False)),
        ])

    class Resolved(Rule.Resolved):
        rating: int
        dependency_names: tuple[str, ...]

        @override
        def _evaluate(self, state: CollectionState) -> bool:
            return ChurchPointCalculator(state, self.player).calculate() >= self.rating

        @override
        def item_dependencies(self) -> dict[str, set[int]]:
            return {name: {id(self)} for name in self.dependency_names}
