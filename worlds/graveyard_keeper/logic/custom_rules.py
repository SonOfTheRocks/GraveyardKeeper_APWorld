from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import TYPE_CHECKING, Iterable, override

from BaseClasses import CollectionState, ItemClassification
from rule_builder.options import OptionFilter
from rule_builder.rules import Rule, Has, And, Or, False_, CanReachRegion, True_, HasAllCounts
from ..data import data, CRAFTING_EVENT_PREFIX, load_json_data
from ..options import VendorLogic
from ..regions import enabled_dlcs
from ..models import (
    RecipeData,
    QualityRecipeData,
    CraftingGroup, HappinessData,
)
from .acquisition import get_higher_quality_substitutes, get_vendor_item_keys

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
        requirements: list[Rule] = []

        if self.recipe.required_recipe_item:
            recipe_key, _ = resolve_item_key(self.recipe.required_recipe_item)
            if data.items[recipe_key].dlc not in enabled_dlcs(world):
                return False_().resolve(world)

        if self.recipe.workstations:
            workstation_requirement = Or(*(
                CanGet(workstation)
                for workstation in self.recipe.workstations
            ))
            requirements.append(workstation_requirement)

        if self.recipe.required_recipe_item:
            requirements.append(CanGet(self.recipe.required_recipe_item))

        requirements.extend(
            CanGet(ingredient)
            for ingredient in self.recipe.ingredients
        )

        if self.recipe.is_quality:
            assert isinstance(self.recipe, QualityRecipeData)
            requirements.append(HasCraftingQuality.from_recipe(self.recipe))

        if not requirements:
            return True_().resolve(world)
        return And(*requirements).resolve(world)


@dataclass
class CanCraft(GKRule, game="Graveyard Keeper"):
    """
    Checks whether an item can be obtained through crafting or from the AP pool.
    """

    item_key: str

    @override
    def _instantiate(self, world: "GraveyardKeeperWorld") -> Rule.Resolved:
        resolved_item_key, resolved_required_count = resolve_item_key(self.item_key)
        if resolved_item_key in data.items:
            item = data.items[resolved_item_key]
            # Recipe classifications are determined from the active rule closure,
            # after rule resolution and before the item pool is constructed.
            return Has(item.label, count=resolved_required_count).resolve(world)

        return Or(*(
            CanCraftRecipe(recipe)
            for recipe in data.recipes.get(self.item_key, ())
        )).resolve(world)


def _is_vendor_only(item_key: str) -> bool:
    resolved_key, _ = resolve_item_key(item_key)
    return (
        resolved_key not in data.items
        and item_key not in data.recipes
        and item_key in get_vendor_item_keys()
    )


@dataclass
class HasCraftingQuality(GKRule, game="Graveyard Keeper"):
    base_modifier: float
    modifiers: tuple[tuple[str, float], ...]

    @override
    def _instantiate(self, world: "GraveyardKeeperWorld") -> Rule.Resolved:
        disabled_labels = {item.label for item in data.items.values()
                           if item.dlc not in enabled_dlcs(world)}
        return self.Resolved(
            self.base_modifier,
            tuple((label, modifier) for label, modifier in self.modifiers if label not in disabled_labels),
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
    Checks whether buying an item is allowed by vendor logic and a vendor is reachable.
    """

    item_key: str

    @override
    def _instantiate(self, world: "GraveyardKeeperWorld") -> Rule.Resolved:
        vendor_regions = [
            data.regions[vendor.region].label
            for vendor in data.vendors.values()
            if self.item_key in vendor.sells_all
            and data.regions[vendor.region].dlc in enabled_dlcs(world)
        ]

        if not vendor_regions:
            return False_().resolve(world)

        vendor_access_rule = Or(
            *(CanReachRegion(region) for region in vendor_regions)
        )
        vendor_and_money_source_rule = And(
            vendor_access_rule,
            Has(data.events["EVENT_CHURCH_OPEN"].item_label),
        )
        vendor_logic = world.options.vendor_logic.value

        if vendor_logic == VendorLogic.option_always_available:
            return vendor_access_rule.resolve(world)

        if (
                vendor_logic == VendorLogic.option_require_money_source
                or _is_vendor_only(self.item_key)
        ):
            return vendor_and_money_source_rule.resolve(world)

        return False_().resolve(world)


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
        available = getattr(world, "acquirable_item_keys", None)
        if available is not None:
            for key in self.item_keys:
                acquisition_key = key.removeprefix(CRAFTING_EVENT_PREFIX)
                if (key.startswith(CRAFTING_EVENT_PREFIX) or acquisition_key in data.items
                        or CRAFTING_EVENT_PREFIX + acquisition_key in data.events):
                    if acquisition_key not in available:
                        return False_().resolve(world)
        return build_collection_rule(self.item_keys).resolve(world)


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
        requirements: list[Rule] = []

        quest_data = data.events[self.quest_key]

        for quest_key in quest_data.required_quests:
            if not quest_key.startswith("TODO"):
                requirements.append(CanComplete(quest_key))

        for hap in quest_data.required_happiness:
            requirements.append(HasHappiness(hap))

        for quest_item_key in quest_data.required_quest_items:
            requirements.append(Has(data.items[quest_item_key].label))

        for craft_item_key in quest_data.required_craft_items:
            requirements.append(CanGet(craft_item_key))

        for technology_id in quest_data.required_technologies:
            technology = load_json_data("technologies.json")[technology_id]
            requirements.append(CanReachRegion(data.regions[technology["region"]].label))

        for area_points in quest_data.required_area_points:
            if area_points.area == "CHURCH":
                # Import here: the calculator uses CanGet for its input dependencies.
                from .church_calculator import HasChurchRating
                requirements.append(HasChurchRating(area_points.value))
            elif area_points.area == "TAVERN":
                from .tavern_calculator import HasTavernRating
                requirements.append(HasTavernRating(area_points.value))
            elif area_points.area == "OLD_GRAVEYARD":
                from .goal_rules import HasGraveyardRating
                requirements.append(HasGraveyardRating(area_points.value))
            elif area_points.area == "TRADE_OFFICE":
                from .trade_office_calculator import HasTradeOfficeRating
                requirements.append(HasTradeOfficeRating(area_points.value))
            elif area_points.area == "SACRIFICE_ZONE":
                from .sacrifice_calculator import HasSacrificeRating
                requirements.append(HasSacrificeRating(area_points.value))
            elif area_points.area == "REFUGEE_CAMP":
                from .refugee_camp_calculator import HasRefugeeCampRating
                requirements.append(HasRefugeeCampRating(area_points.value))

        if not requirements:
            return True_().resolve(world)
        return And(*requirements).resolve(world)


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
    if item_key in data.progressive_items_reverse:
        rev = data.progressive_items_reverse[item_key]
        return rev.key, rev.count
    return item_key, 1


def resolve_item_labels(item_keys: str | Iterable[str]) -> set[tuple[str, int]]:
    if isinstance(item_keys, str):
        item_keys = [item_keys]

    resolved_labels: set[tuple[str, int]] = set()
    for item_key in item_keys:
        resolved_key, count = resolve_item_key(item_key)

        item_data = data.items.get(resolved_key)
        if item_data:
            resolved_labels.add((item_data.label, count))
            continue

        event_data = data.events.get(item_key)
        if event_data:
            resolved_labels.add((event_data.item_label, count))
            continue

        crafting_event = data.events.get(CRAFTING_EVENT_PREFIX + item_key)
        if crafting_event:
            resolved_labels.add((crafting_event.item_label, count))
            continue

        raise ValueError(f"Unknown item or event key: {item_key}")

    return resolved_labels


def build_crafting_event_rule(item_keys: str | Iterable[str]) -> Rule:
    if isinstance(item_keys, str):
        item_keys = [item_keys]

    per_item_requirements: list[Rule] = []
    for item_key in item_keys:
        acquisition_paths: list[Rule] = []
        if item_key in data.recipes:
            acquisition_paths.append(CanCraft(item_key))
        if item_key in get_vendor_item_keys():
            acquisition_paths.append(CanBuy(item_key))
        acquisition_paths.extend(
            CanGet(higher_quality_key)
            for higher_quality_key in get_higher_quality_substitutes(item_key)
        )
        per_item_requirements.append(Or(*acquisition_paths))

    return And(*per_item_requirements)


def build_collection_rule(item_keys: str | Iterable[str]) -> Rule:
    if isinstance(item_keys, str):
        item_keys = [item_keys]

    required_item_counts = dict(resolve_item_labels(item_keys))
    if not required_item_counts:
        return True_()

    return HasAllCounts(required_item_counts)
