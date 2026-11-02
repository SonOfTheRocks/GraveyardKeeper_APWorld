from dataclasses import dataclass
from typing import override

from BaseClasses import CollectionState
from rule_builder.rules import And, CanReachRegion, False_, Has, Rule
from ..data import CRAFTING_EVENT_PREFIX, data, load_json_data
from .custom_rules import CanGet, GKRule


TAVERN_RATING = load_json_data("logic/tavern_rating.json")


class TavernPointCalculator:
    """Best attainable Talking Skull quality; see data/TAVERN_RATING.md."""

    def __init__(self, state: CollectionState, player: int):
        self.state = state
        self.player = player

    @staticmethod
    def dependency_rule() -> Rule:
        events = {TAVERN_RATING["open_event"], TAVERN_RATING["upgrade_event"],
                  *TAVERN_RATING["artifacts"]}
        events.update(furniture["required_event"] for furniture in TAVERN_RATING["furniture"].values()
                      if "required_event" in furniture)
        return And(
            *(Has(data.events[key].item_label) for key in sorted(events)),
            *(CanGet(key) for key in TAVERN_RATING["furniture"]),
            *(Has(data.items[artifact["item"]].label) for artifact in TAVERN_RATING["artifacts"].values()),
        )

    def _has_event(self, key: str) -> bool:
        return self.state.has(data.events[key].item_label, self.player)

    def calculate(self) -> int:
        if not self._has_event(TAVERN_RATING["open_event"]):
            return 0

        upgraded = self._has_event(TAVERN_RATING["upgrade_event"])
        total = TAVERN_RATING["upgrade_points"] if upgraded else 0
        table_score = 0
        for key, furniture in TAVERN_RATING["furniture"].items():
            if not self._has_event(CRAFTING_EVENT_PREFIX + key):
                continue
            if "required_event" in furniture and not self._has_event(furniture["required_event"]):
                continue
            if furniture.get("group") == "table":
                table_score = max(table_score, furniture["points"])
            else:
                total += furniture["points"] * furniture["count"]
                if key == "BUILDABLE_TAVERN_ARTIFACTS_SHELVES":
                    # Insertion crafts unlock after the corresponding vision.
                    # Each of the 17 different artifacts contributes once.
                    total += sum(artifact["points"] for event, artifact in TAVERN_RATING["artifacts"].items()
                                 if self._has_event(event)
                                 and self.state.has(data.items[artifact["item"]].label, self.player))

        spaces = TAVERN_RATING["upgraded_table_spaces"] if upgraded else TAVERN_RATING["table_spaces"]
        return total + spaces * table_score


@dataclass
class HasTavernRating(GKRule, game="Graveyard Keeper"):
    rating: int

    @override
    def _instantiate(self, world) -> Rule.Resolved:
        if not world.options.stranger_sins:
            return False_().resolve(world)
        dependencies = TavernPointCalculator.dependency_rule().resolve(world)
        return And.from_resolved(world, [
            CanReachRegion(data.regions["REGION_TAVERN"].label).resolve(world),
            Has(data.events[TAVERN_RATING["open_event"]].item_label).resolve(world),
            self.Resolved(self.rating, tuple(sorted(dependencies.item_dependencies())),
                          player=world.player, caching_enabled=getattr(world, "rule_caching_enabled", False)),
        ])

    class Resolved(Rule.Resolved):
        rating: int
        dependency_names: tuple[str, ...]

        @override
        def _evaluate(self, state: CollectionState) -> bool:
            return TavernPointCalculator(state, self.player).calculate() >= self.rating

        @override
        def item_dependencies(self) -> dict[str, set[int]]:
            return {name: {id(self)} for name in self.dependency_names}
