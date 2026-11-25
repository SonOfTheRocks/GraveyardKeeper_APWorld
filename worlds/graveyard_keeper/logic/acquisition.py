from __future__ import annotations

"""Structural acquisition analysis independent of a generated world state."""

from functools import cache
from typing import Collection, TYPE_CHECKING

from ..data import data
from ..models import RecipeData

if TYPE_CHECKING:
    from ..world import GraveyardKeeperWorld


QUALITY_SUFFIXES = ("_COPPER", "_SILVER", "_GOLD")


@cache
def get_vendor_item_keys() -> frozenset[str]:
    return frozenset(
        item_key
        for vendor in data.vendors.values()
        for item_key in vendor.sells_all
    )


def recipe_requirements_are_available(
        recipe: RecipeData,
        available_item_keys: Collection[str],
) -> bool:
    """Check a recipe's AND/OR requirements against structurally available items."""
    has_recipe_unlock = (
        not recipe.required_recipe_item
        or recipe.required_recipe_item in available_item_keys
    )
    has_all_ingredients = all(
        ingredient in available_item_keys
        for ingredient in recipe.ingredients
    )
    has_any_workstation = (
        not recipe.workstations
        or any(
            workstation in available_item_keys
            for workstation in recipe.workstations
        )
    )
    return has_recipe_unlock and has_all_ingredients and has_any_workstation


@cache
def get_structurally_acquirable_item_keys(
        excluded_item_keys: frozenset[str] = frozenset(),
) -> frozenset[str]:
    """Return items with a data-defined acquisition path avoiding excluded items.

    AP items and listed vendor items are treated as possible starting points. This
    function analyzes dependency topology; it does not evaluate options, regions,
    money logic, or a CollectionState.
    """
    available_item_keys = {
        *data.items,
        *data.progressive_items_reverse,
        *get_vendor_item_keys(),
    } - excluded_item_keys

    found_new_item = True
    while found_new_item:
        found_new_item = False
        for output_item_key, recipes in data.recipes.items():
            if (
                    output_item_key in excluded_item_keys
                    or output_item_key in available_item_keys
            ):
                continue

            if any(
                    recipe_requirements_are_available(recipe, available_item_keys)
                    for recipe in recipes
            ):
                available_item_keys.add(output_item_key)
                found_new_item = True

    return frozenset(available_item_keys)


def get_higher_quality_substitutes(item_key: str) -> tuple[str, ...]:
    """Return independently acquirable quality variants above the requested tier."""
    quality_tier = _get_quality_tier(item_key)
    if quality_tier is None:
        return ()

    quality_index, quality_suffix = quality_tier
    base_item_key = item_key.removesuffix(quality_suffix)
    known_acquisition_item_keys = data.recipes.keys() | get_vendor_item_keys()
    independently_acquirable_item_keys = get_structurally_acquirable_item_keys(
        frozenset({item_key})
    )

    substitutes: list[str] = []
    for higher_quality_suffix in QUALITY_SUFFIXES[quality_index + 1:]:
        candidate_item_key = base_item_key + higher_quality_suffix
        if (
                candidate_item_key in known_acquisition_item_keys
                and candidate_item_key in independently_acquirable_item_keys
        ):
            substitutes.append(candidate_item_key)
    return tuple(substitutes)


def get_option_acquirable_item_keys(world: GraveyardKeeperWorld) -> frozenset[str]:
    """Reject acquisition branches excluded by DLC or vendor options.

    This is a structural upper bound, not a replacement for runtime rules:
    enabled regions and money sources are assumed reachable, and quality and
    quest requirements still have to be satisfied by the actual rule.
    Starting from real sources also prevents a recipe cycle from supplying itself.
    """
    from ..options import VendorLogic
    from ..regions import enabled_dlcs

    allowed_dlcs = enabled_dlcs(world)
    available = {key for key, item in data.items.items() if item.dlc in allowed_dlcs}
    available.update(key for key, reverse in data.progressive_items_reverse.items() if reverse.key in available)
    for vendor in data.vendors.values():
        if data.regions[vendor.region].dlc not in allowed_dlcs:
            continue
        for key in vendor.sells_all:
            vendor_only = key not in data.items and key not in data.recipes
            if world.options.vendor_logic.value != VendorLogic.option_out_of_logic or vendor_only:
                available.add(key)

    pending = set(data.recipes) | get_vendor_item_keys()
    while True:
        newly_available = {
            key for key in pending - available
            if any(
                recipe_requirements_are_available(recipe, available)
                for recipe in data.recipes.get(key, ())
            ) or any(substitute in available for substitute in get_higher_quality_substitutes(key))
        }
        if not newly_available:
            return frozenset(available)
        available.update(newly_available)


def _get_quality_tier(item_key: str) -> tuple[int, str] | None:
    for quality_index, quality_suffix in enumerate(QUALITY_SUFFIXES):
        if item_key.endswith(quality_suffix):
            return quality_index, quality_suffix
    return None
