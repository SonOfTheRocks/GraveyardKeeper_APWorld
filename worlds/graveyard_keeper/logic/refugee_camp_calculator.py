from dataclasses import dataclass
from typing import override

from .dependencies import optional_dependency_names
from BaseClasses import CollectionState
from rule_builder.rules import And, CanReachRegion, False_, Has, Rule
from ..data import CRAFTING_EVENT_PREFIX, data, load_json_data
from .custom_rules import CanGet, GKRule


REFUGEE_CAMP_RATING = load_json_data("logic/refugee_camp_rating.json")


class RefugeeCampPointCalculator:
    """Attainable happiness capacity through affordable builds; see data/REFUGEE_CAMP_RATING.md."""

    def __init__(self, state: CollectionState, player: int):
        self.state = state
        self.player = player

    @staticmethod
    def dependency_rule() -> Rule:
        buildings = REFUGEE_CAMP_RATING["buildings"]
        events = {REFUGEE_CAMP_RATING["open_event"]}
        events.update(key for building in buildings.values() for key in building.get("required_events", ()))
        items = {key for building in buildings.values() for key in building.get("required_items", ())}
        return And(
            *(Has(data.events[key].item_label) for key in sorted(events)),
            *(CanGet(key) for key in buildings),
            *(CanGet(key) for key in sorted(items)),
        )

    def _has_event(self, key: str) -> bool:
        return self.state.has(data.events[key].item_label, self.player)

    def _can_get(self, key: str) -> bool:
        if key in data.items:
            return self.state.has(data.items[key].label, self.player)
        return self._has_event(CRAFTING_EVENT_PREFIX + key)

    def attainable_buildings(self) -> frozenset[str]:
        if not self._has_event(REFUGEE_CAMP_RATING["open_event"]):
            return frozenset()
        definitions = REFUGEE_CAMP_RATING["buildings"]
        built: set[str] = set()
        capacity = REFUGEE_CAMP_RATING["initial_quality"]
        residents = REFUGEE_CAMP_RATING["initial_residents"]
        while True:
            affordable = {
                key for key, building in definitions.items()
                if key not in built
                and self._has_event(CRAFTING_EVENT_PREFIX + key)
                and capacity >= building["cost"]
                and residents >= building.get("required_residents", 0)
                and built.issuperset(building.get("required_buildings", ()))
                and all(self._has_event(event) for event in building.get("required_events", ()))
                and all(self._can_get(item) for item in building.get("required_items", ()))
            }
            if not affordable:
                return frozenset(built)
            # Happiness can refill between builds. Only existing capacity can
            # pay a cost; new buildings cannot finance their own construction.
            capacity += sum(definitions[key]["points"] for key in affordable)
            if capacity >= REFUGEE_CAMP_RATING["recruit_cost"]:
                residents += sum(definitions[key].get("residents", 0) for key in affordable)
            built.update(affordable)

    def calculate(self) -> int:
        if not self._has_event(REFUGEE_CAMP_RATING["open_event"]):
            return 0
        return REFUGEE_CAMP_RATING["initial_quality"] + sum(
            REFUGEE_CAMP_RATING["buildings"][key]["points"] for key in self.attainable_buildings()
        )


@dataclass
class HasRefugeeCampRating(GKRule, game="Graveyard Keeper"):
    rating: int

    @override
    def _instantiate(self, world) -> Rule.Resolved:
        if not world.options.game_of_crone:
            return False_().resolve(world)
        dependencies = optional_dependency_names(RefugeeCampPointCalculator.dependency_rule(), world)
        return And.from_resolved(world, [
            CanReachRegion(data.regions["REGION_REFUGEE_CAMP"].label).resolve(world),
            Has(data.events[REFUGEE_CAMP_RATING["open_event"]].item_label).resolve(world),
            self.Resolved(self.rating, dependencies,
                          player=world.player, caching_enabled=getattr(world, "rule_caching_enabled", False)),
        ])

    class Resolved(Rule.Resolved):
        rating: int
        dependency_names: tuple[str, ...]

        @override
        def _evaluate(self, state: CollectionState) -> bool:
            return RefugeeCampPointCalculator(state, self.player).calculate() >= self.rating

        @override
        def item_dependencies(self) -> dict[str, set[int]]:
            return {name: {id(self)} for name in self.dependency_names}
