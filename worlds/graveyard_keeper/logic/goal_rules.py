from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, override

from BaseClasses import CollectionState
from rule_builder.rules import And, CanReachRegion, Rule, True_
from ..data import data
from .custom_rules import CanCraft, GKRule
from .grave_calculator import GravePointCalculator
from .graveyard_calculator import GraveyardPointCalculator

if TYPE_CHECKING:
    from ..world import GraveyardKeeperWorld


@dataclass
class HasGraveyardRating(GKRule, game="Graveyard Keeper"):
    rating: int

    @override
    def _instantiate(self, world: "GraveyardKeeperWorld") -> Rule.Resolved:
        if self.rating == 0:
            return True_().resolve(world)
        dependencies = GraveyardPointCalculator.dependency_rule().resolve(world)
        crafting_rules = tuple((key, CanCraft(key).resolve(world)) for key in GravePointCalculator.CRAFTING_INPUTS)
        rating_rule = self.Resolved(self.rating, bool(world.options.game_of_crone), bool(world.options.better_save_soul),
                             crafting_rules, tuple(sorted(dependencies.item_dependencies())),
                             player=world.player, caching_enabled=getattr(world, "rule_caching_enabled", False))
        return And.from_resolved(world, [
            CanReachRegion(data.regions["REGION_OLD_GRAVEYARD"].label).resolve(world), rating_rule,
        ])

    class Resolved(Rule.Resolved):
        rating: int
        game_of_crone: bool
        better_save_soul: bool
        crafting_rules: tuple[tuple[str, Rule.Resolved], ...]
        dependency_names: tuple[str, ...]

        @override
        def _evaluate(self, state: CollectionState) -> bool:
            # Resolved rules are globally interned. Store only immutable inputs,
            # never a World/MultiWorld reference that would retain old seeds.
            context = SimpleNamespace(player=self.player, options=SimpleNamespace(
                game_of_crone=self.game_of_crone, better_save_soul=self.better_save_soul))
            return GraveyardPointCalculator(state, context, dict(self.crafting_rules)).calculate() >= self.rating

        @override
        def item_dependencies(self) -> dict[str, set[int]]:
            dependencies = {name: {id(self)} for name in self.dependency_names}
            for _, rule in self.crafting_rules:
                for name, rule_ids in rule.item_dependencies().items():
                    dependencies.setdefault(name, {id(self)}).update(rule_ids)
            return dependencies
