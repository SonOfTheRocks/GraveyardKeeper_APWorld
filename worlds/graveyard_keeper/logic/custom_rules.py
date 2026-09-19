from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import TYPE_CHECKING, Iterable, override

from BaseClasses import CollectionState, ItemClassification
from rule_builder.options import OptionFilter
from rule_builder.rules import Rule, Has, And, Or, False_, CanReachRegion, True_, HasAllCounts
from ..data import data, CRAFTING_EVENT_PREFIX
from ..models import (
    RecipeData,
    QualityRecipeData,
    CraftingGroup, HappinessData,
)

if TYPE_CHECKING:
    from ..world import GraveyardKeeperWorld


@dataclass
class GKRule(Rule["GraveyardKeeperWorld"], game="Graveyard Keeper"):
    def get_dependencies(self) -> dict[str, int]:
        return {}

    @staticmethod
    def add_dependencies(
            target: dict[str, int],
            dependencies: dict[str, int]
    ) -> None:
        for item, count in dependencies.items():
            target[item] = target.get(item, 0) + count

@dataclass
class CanCraftRecipe(GKRule, game="Graveyard Keeper"):
    recipe: RecipeData

    @override
    def _instantiate(self, world: "GraveyardKeeperWorld") -> Rule.Resolved:
        rules: list[Rule] = []

        # Workstations
        for workstation in self.recipe.workstations:
            rules.append(CanGet(workstation))

        # Required recipe item
        if self.recipe.required_recipe_item:
            rules.append(CanGet(self.recipe.required_recipe_item))

        # Ingredients
        for ingredient in self.recipe.ingredients:
            rules.append(CanGet(ingredient))

        # Quality requirements
        if self.recipe.is_quality:
            assert isinstance(self.recipe, QualityRecipeData)
            rules.append(HasCraftingQuality.from_recipe(self.recipe))

        if not rules:
            return True_().resolve(world)
        else:
            return And(*rules).resolve(world)

@dataclass
class CanCraft(GKRule, game="Graveyard Keeper"):
    """
    Checks whether an item can be obtained through crafting or purchasing.
    """

    item_key: str

    @override
    def _instantiate(self, world: "GraveyardKeeperWorld") -> Rule.Resolved:
        resolved_item_key, resolved_required_count = resolve_item_key(self.item_key)

        # In-game item / progressive item
        if resolved_item_key in data.items:
            item = data.items[resolved_item_key]

            assert item.classification == ItemClassification.progression, (
                f"item '{resolved_item_key}' is used in a rule and therefore "
                f"must have PROGRESSION classification"
            )

            return Has(
                item.label,
                count=resolved_required_count,
            ).resolve(world)

        recipes = data.recipes.get(self.item_key, ())

        return Or(
            *(CanCraftRecipe(recipe) for recipe in recipes),
        ).resolve(world)

@dataclass
class HasCraftingQuality(GKRule, game="Graveyard Keeper"):
    base_modifier: float
    modifiers: tuple[tuple[str, float], ...]

    @override
    def _instantiate(self, world: "Graveyard Keeper") -> Rule.Resolved:
        return self.Resolved(
            self.base_modifier,
            self.modifiers,
            player=world.player,
            caching_enabled=getattr(world, "rule_build_caching_enabled", False),
        )

    @classmethod
    def from_recipe(cls, recipe: QualityRecipeData) -> Rule:
        assert isinstance(recipe, QualityRecipeData)

        modifiers: list[tuple[str, float]] = []

        match recipe.crafting_group:
            case CraftingGroup.WriterOnly:
                modifiers.append((data.items["ITEM_PERK_WRITER"].label, 0.3))
            case CraftingGroup.WritingWithoutIndustriousness | CraftingGroup.Writing:
                modifiers.append((data.items["ITEM_PERK_WRITER"].label, 0.3))
                modifiers.append((data.items["ITEM_PERK_PLAYWRIGHT"].label, 0.5))
            case CraftingGroup.Book:
                modifiers.append((data.items["ITEM_PERK_JEWELER"].label, 0.7))
                if "CRAFTING_STATION_DESK_2" in recipe.workstations:
                    modifiers.append(
                        (data.events[CRAFTING_EVENT_PREFIX + "CRAFTING_STATION_DESK_2"].item_label, 0.2))
            case CraftingGroup.Wine:
                modifiers.append((data.items["ITEM_PERK_WINE_MASTER"].label, 0.8))
            case CraftingGroup.Chisel:
                modifiers.append((data.items["ITEM_PERK_BLACKSMITH"].label, 0.1))
                modifiers.append((data.items["ITEM_PERK_ENGINEER"].label, 0.3))
            case CraftingGroup.Wood:
                modifiers.append((data.items["ITEM_PERK_CARPENTER"].label, 0.5))
                modifiers.append((data.items["ITEM_PERK_ENGINEER"].label, 0.3))
            case CraftingGroup.Marble:
                modifiers.append((data.items["ITEM_PERK_MASON"].label, 0.5))
                modifiers.append((data.items["ITEM_PERK_ENGINEER"].label, 0.3))

        if recipe.crafting_group not in {CraftingGroup.NoGroup, CraftingGroup.WritingWithoutIndustriousness}:
            modifiers.append((data.items["ITEM_PERK_INDUSTRIOUSNESS"].label, 0.2))

        return cls(
            base_modifier=recipe.base_modifier,
            modifiers=tuple(modifiers),
        )

    class Resolved(Rule.Resolved):
        base_modifier: float
        modifiers: tuple[tuple[str, float], ...]

        @override
        def _evaluate(self, state: CollectionState) -> bool:
            chance = self.base_modifier

            for label, modifier in self.modifiers:
                if state.has(label, self.player):
                    chance += modifier

            return 0.5 <= chance <= 1.5

        @override
        def item_dependencies(self) -> dict[str, set[int]]:
            return {
                label: {id(self)}
                for label, _ in self.modifiers
            }

@dataclass
class CanBuy(GKRule, game="Graveyard Keeper"):
    """
    Checks whether an item can be purchased from any vendor
    """

    item_key: str

    @override
    def _instantiate(self, world: "GraveyardKeeperWorld") -> Rule.Resolved:
        vendor_regions = [
            data.regions[vendor.region].label
            for vendor in data.vendors.values()
            if self.item_key in vendor.sells_all
        ]

        if not vendor_regions:
            return False_().resolve(world)

        return Or(
            *(CanReachRegion(region) for region in vendor_regions)
        ).resolve(world)

@dataclass
class CanGet(GKRule, game="Graveyard Keeper"):
    """
    Check whether an item is accessible in general
    """

    item_keys: tuple[str, ...]

    # careful if the API of Rule class changes...
    def __init__(
            self,
            *item_keys: str,
            options: Iterable[OptionFilter] = (),
            filtered_resolution: bool = False
    ) -> None:
        self.item_keys = item_keys
        self.options = options
        self.filtered_resolution = filtered_resolution

        self.__post_init__()

    @override
    def _instantiate(self, world: "GraveyardKeeperWorld") -> Rule.Resolved:
        rules = []
        all_sold = [ item for vendor in data.vendors.values() for item in vendor.sells_all]

        for item_key in self.item_keys:
            resolved_key, resolved_count = resolve_item_key(item_key)
            if resolved_key in all_sold:
                rules.append(CanBuy(item_key))
            elif resolved_key in data.items.keys():
                rules.append(Has(data.items[resolved_key].label, resolved_count))
            else:
                rules.append(CanCraft(item_key))

        return And(*rules).resolve(world)

@dataclass()
class HasPerk(GKRule, game="Graveyard Keeper"):
    """
    Check whether the player has gained a certain perk
    """

    perk_key: str

    @override
    def _instantiate(self, world: "GraveyardKeeperWorld") -> Rule.Resolved:
        if not self.perk_key.startswith("ITEM_PERK_"):
            self.perk_key = "ITEM_PERK_" + self.perk_key
        perk_label = data.items[self.perk_key].label
        return Has(perk_label).resolve(world)

@dataclass
class CanComplete(GKRule, game="Graveyard Keeper"):
    """
    Check whether a quest can be completed
    """

    quest_key: str

    @override
    def _instantiate(self, world: "GraveyardKeeperWorld") -> Rule.Resolved:
        rules: list[Rule] = []

        quest_data = data.events[self.quest_key]

        # required quests
        for quest_key in quest_data.required_quests:
            if not quest_key.startswith("TODO"):
                rules.append(CanComplete(quest_key))

        # required happiness
        for hap in quest_data.required_happiness:
            rules.append(HasHappiness(hap))

        # required quest items
        for quest_item_key in quest_data.required_quest_items:
            rules.append(Has(data.items[quest_item_key].label))

        # required craft items
        for craft_item_key in quest_data.required_craft_items:
            rules.append(CanCraft(craft_item_key))

        if not rules:
            return True_().resolve(world)
        else:
            return And(*rules).resolve(world)

@dataclass
class HasHappiness(GKRule, game="Graveyard Keeper"):
    """
    Check whether the player can get at least the specified amount of happiness for a certain npc
    """

    happiness: HappinessData

    @override
    def _instantiate(self, world: "GraveyardKeeperWorld") -> Rule.Resolved:
        required_count = ceil(self.happiness.value / 10)
        happiness_item = data.items[f"ITEM_{self.happiness.npc}_HAPPINESS_10"].label
        return Has(happiness_item, required_count).resolve(world)


def resolve_item_key(item_key: str) -> tuple[str, int]:
    #item_key = event.replace(CRAFTING_EVENT_PREFIX, "")
    if item_key in data.progressive_items_reverse:
        rev = data.progressive_items_reverse[item_key]
        return rev.key, rev.count
    return item_key, 1

def resolve_item_labels(item_keys: str | Iterable[str]) -> set[tuple[str, int]]:
    if isinstance(item_keys, str):
        item_keys = [item_keys]

    ret: set[tuple[str, int]] = set()
    for key in item_keys:
        # resolve progressive
        resolved_key, count = resolve_item_key(key)

        # item
        item_data = data.items.get(resolved_key, None)
        if item_data:
            ret.add((item_data.label, count))
            continue

        # normal event
        event_data = data.events.get(key, None)
        if event_data:
            ret.add((event_data.item_label, count))
            continue

        # 'can get' event
        event_data = data.events.get(CRAFTING_EVENT_PREFIX + key, None)
        if event_data:
            ret.add((event_data.item_label, count))
            continue

        assert False, f"invalid key '{key}"

    return ret

'''
def build_crafting_event_rule(item_keys: str | Iterable[str],) -> Rule:
    if isinstance(item_keys, str):
        item_keys = [item_keys]

    return CanCraftAll(tuple(item_keys))
'''

def build_collection_rule(item_keys: str | Iterable[str]) -> Rule:
    if isinstance(item_keys, str):
        item_keys = [item_keys]

    counts = {l: c for l, c in resolve_item_labels(item_keys)}
    if not counts:
        return True_()

    return HasAllCounts(counts)
