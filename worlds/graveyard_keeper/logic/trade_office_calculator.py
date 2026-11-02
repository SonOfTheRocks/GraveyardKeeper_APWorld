from dataclasses import dataclass
from typing import override

from BaseClasses import CollectionState
from rule_builder.rules import And, CanReachRegion, Has, Rule
from ..data import CRAFTING_EVENT_PREFIX, data, load_json_data
from .custom_rules import CanGet, GKRule


TRADE_OFFICE_RATING = load_json_data("logic/trade_office_rating.json")


class TradeOfficePointCalculator:
    """Best attainable office quality; see data/TRADE_OFFICE_RATING.md."""

    def __init__(self, state: CollectionState, player: int):
        self.state = state
        self.player = player

    @staticmethod
    def dependency_rule() -> Rule:
        return And(
            Has(data.events[TRADE_OFFICE_RATING["open_event"]].item_label),
            CanGet(TRADE_OFFICE_RATING["marketing_material"]),
            CanGet(TRADE_OFFICE_RATING["pallet_buildable"]),
        )

    def _can_get(self, key: str) -> bool:
        return self.state.has(data.events[CRAFTING_EVENT_PREFIX + key].item_label, self.player)

    def calculate(self) -> int:
        rating = TRADE_OFFICE_RATING
        if not self.state.has(data.events[rating["open_event"]].item_label, self.player):
            return 0
        pallets = rating["initial_pallets"]
        if self._can_get(rating["pallet_buildable"]):
            pallets = rating["pallet_spaces"]
        total = pallets * rating["pallet_points"]
        if self._can_get(rating["marketing_material"]):
            # Repeatable flyer exchange fills the desk; building pallets spends
            # marketing points, but further exchanges can replenish them.
            total += (rating["marketing_inventory_slots"] * rating["marketing_stack_size"]
                      * rating["marketing_point_quality"])
        return total


@dataclass
class HasTradeOfficeRating(GKRule, game="Graveyard Keeper"):
    rating: int

    @override
    def _instantiate(self, world) -> Rule.Resolved:
        dependencies = TradeOfficePointCalculator.dependency_rule().resolve(world)
        return And.from_resolved(world, [
            CanReachRegion(data.regions["REGION_TRADE_OFFICE"].label).resolve(world),
            Has(data.events[TRADE_OFFICE_RATING["open_event"]].item_label).resolve(world),
            self.Resolved(self.rating, tuple(sorted(dependencies.item_dependencies())),
                          player=world.player, caching_enabled=getattr(world, "rule_caching_enabled", False)),
        ])

    class Resolved(Rule.Resolved):
        rating: int
        dependency_names: tuple[str, ...]

        @override
        def _evaluate(self, state: CollectionState) -> bool:
            return TradeOfficePointCalculator(state, self.player).calculate() >= self.rating

        @override
        def item_dependencies(self) -> dict[str, set[int]]:
            return {name: {id(self)} for name in self.dependency_names}
