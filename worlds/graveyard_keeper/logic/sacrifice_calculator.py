from dataclasses import dataclass
from typing import override

from BaseClasses import CollectionState
from rule_builder.rules import And, CanReachRegion, Has, Rule
from ..data import CRAFTING_EVENT_PREFIX, data, load_json_data
from .custom_rules import CanGet, GKRule


SACRIFICE_RATING = load_json_data("logic/sacrifice_rating.json")


class SacrificePointCalculator:
    """Best attainable ritual-site quality; see data/SACRIFICE_RATING.md."""

    def __init__(self, state: CollectionState, player: int):
        self.state = state
        self.player = player

    @staticmethod
    def dependency_rule() -> Rule:
        furniture = SACRIFICE_RATING["furniture"]
        events = {entry["required_event"] for entry in furniture.values() if "required_event" in entry}
        materials = {entry["activation_material"] for entry in furniture.values() if "activation_material" in entry}
        return And(
            *(Has(data.events[key].item_label) for key in sorted(events)),
            *(CanGet(key) for key in (*furniture, *sorted(materials))),
        )

    def _can_get(self, key: str) -> bool:
        return self.state.has(data.events[CRAFTING_EVENT_PREFIX + key].item_label, self.player)

    def calculate(self) -> int:
        total = 0
        for key, furniture in SACRIFICE_RATING["furniture"].items():
            if not self._can_get(key):
                continue
            if "required_event" in furniture and not self.state.has(
                    data.events[furniture["required_event"]].item_label, self.player):
                continue
            points = furniture["points"]
            if "activation_material" in furniture and self._can_get(furniture["activation_material"]):
                points = furniture["activated_points"]
            total += furniture["count"] * points
        return total


@dataclass
class HasSacrificeRating(GKRule, game="Graveyard Keeper"):
    rating: int

    @override
    def _instantiate(self, world) -> Rule.Resolved:
        dependencies = SacrificePointCalculator.dependency_rule().resolve(world)
        return And.from_resolved(world, [
            CanReachRegion(data.regions["REGION_SACRIFICE_ZONE"].label).resolve(world),
            self.Resolved(self.rating, tuple(sorted(dependencies.item_dependencies())),
                          player=world.player, caching_enabled=getattr(world, "rule_caching_enabled", False)),
        ])

    class Resolved(Rule.Resolved):
        rating: int
        dependency_names: tuple[str, ...]

        @override
        def _evaluate(self, state: CollectionState) -> bool:
            return SacrificePointCalculator(state, self.player).calculate() >= self.rating

        @override
        def item_dependencies(self) -> dict[str, set[int]]:
            return {name: {id(self)} for name in self.dependency_names}
