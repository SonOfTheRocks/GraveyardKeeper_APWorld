from typing import Callable, List, Tuple, Iterable, Counter

from BaseClasses import CollectionState, ItemClassification
from worlds.graveyard_keeper.data import data, CRAFTING_EVENT_PREFIX
from worlds.graveyard_keeper.models import RecipeData, ReverseItemData, RecipeDependencies, Requirement, SimpleRecipeDependencies, \
    QualityRecipeDependencies, QualityRecipeData, CraftingGroup, QualityRequirement


def has_all_or_empty(state, items, player):
    return not items or state.has_all(items, player)

def has_any_or_empty(state, items, player):
    return not items or state.has_any(items, player)

def has_all_or_empty_count(state, items_with_count, player):
    return not items_with_count or all(state.has(i, player, c) for (i, c) in items_with_count)

def has_any_or_empty_count(state, items_with_count, player):
    return not items_with_count or any(state.has(i, player, c) for (i, c) in items_with_count)

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

def _build_recipe_dependencies(recipe: RecipeData) -> list[RecipeDependencies]:
    workstations = [
        data.events[CRAFTING_EVENT_PREFIX + w].item_label
        for w in recipe.workstations
    ]

    requirements: list[Requirement] = []

    # required recipe item
    key = recipe.required_recipe_item
    if key:
        key, count = resolve_item_key(key)
        requirements.append(
            Requirement(data.items[key].label, count)
        )

    # ingredients
    for ing in recipe.ingredients:
        if ing in data.items:
            requirements.append(Requirement(data.items[ing].label))
        else:
            assert CRAFTING_EVENT_PREFIX + ing in data.events, \
                f"{ing} is not obtainable"
            requirements.append(
                Requirement(data.events[CRAFTING_EVENT_PREFIX + ing].item_label)
            )

    if not recipe.is_quality:
        return SimpleRecipeDependencies(workstations, requirements)

    # Quality Recipe, collect more requirements
    assert type(recipe) == QualityRecipeData, f"{recipe} is not a quality recipe"
    recipe: QualityRecipeData = recipe

    quality_requirements = []
    match recipe.crafting_group:
        case CraftingGroup.WriterOnly:
            quality_requirements.append(QualityRequirement(data.items["ITEM_PERK_WRITER"].label, 0.3))
        case CraftingGroup.WritingWithoutIndustriousness | CraftingGroup. Writing:
            quality_requirements.append(QualityRequirement(data.items["ITEM_PERK_WRITER"].label, 0.3))
            quality_requirements.append(QualityRequirement(data.items["ITEM_PERK_PLAYWRIGHT"].label, 0.5))
        case CraftingGroup.Book:
            quality_requirements.append(QualityRequirement(data.items["ITEM_PERK_JEWELER"].label, 0.7))
            if "CRAFTING_STATION_DESK_2" in recipe.workstations:
                quality_requirements.append(QualityRequirement(data.events[CRAFTING_EVENT_PREFIX + "CRAFTING_STATION_DESK_2"].item_label, 0.2))
        case CraftingGroup.Wine:
            quality_requirements.append(QualityRequirement(data.items["ITEM_PERK_WINE_MASTER"].label, 0.8))
        case CraftingGroup.Chisel:
            quality_requirements.append(QualityRequirement(data.items["ITEM_PERK_BLACKSMITH"].label, 0.1))
            quality_requirements.append(QualityRequirement(data.items["ITEM_PERK_ENGINEER"].label, 0.3))
        case CraftingGroup.Wood:
            quality_requirements.append(QualityRequirement(data.items["ITEM_PERK_CARPENTER"].label, 0.5))
            quality_requirements.append(QualityRequirement(data.items["ITEM_PERK_ENGINEER"].label, 0.3))
        case CraftingGroup.Marble:
            quality_requirements.append(QualityRequirement(data.items["ITEM_PERK_MASON"].label, 0.5))
            quality_requirements.append(QualityRequirement(data.items["ITEM_PERK_ENGINEER"].label, 0.3))

    if recipe.crafting_group not in [CraftingGroup.NoGroup, CraftingGroup.WritingWithoutIndustriousness]:
        quality_requirements.append(QualityRequirement(data.items["ITEM_PERK_INDUSTRIOUSNESS"].label, 0.2))

    return QualityRecipeDependencies(workstations, requirements, recipe.base_modifier, quality_requirements)

def build_crafting_event_rule(item_keys: str | Iterable[str], player: int) -> Callable[[CollectionState], bool]:
    if isinstance(item_keys, str):
        item_keys = [item_keys]

    rules = [_build_crafting_event_rule(item_key, player) for item_key in item_keys]

    return lambda state: all(rule(state) for rule in rules)

def _build_crafting_event_rule(item_key: str, player: int) -> Callable[[CollectionState], bool]:

    def is_craftable(c_state: CollectionState, player: int) -> bool:
        return lambda state: any(deps.are_fulfilled(c_state, player) for deps in _build_all_recipe_dependencies(item_key))

    def is_buyable(state: CollectionState, player: int) -> bool:
        return _build_crafting_event_vendor_rule(item_key, player)(state)

    #print(f"building crafting event rule for {item_key}")

    resolved_item_key, resolved_required_count = resolve_item_key(item_key)
    # requested item is AP item
    if resolved_item_key in data.items:
        item = data.items[resolved_item_key]
        assert item.classification == ItemClassification.progression, \
            f"item '{resolved_item_key}' is used in a rule and therefore must have PROGRESSION classification"
        return lambda state, p = player, c = resolved_required_count: state.has(item.label, p, c)

    return lambda state, p=player: is_buyable(state, p) or is_craftable(state, p)

def _build_crafting_event_vendor_rule(item_key: str, player: int) -> Callable[[CollectionState], bool]:
    # TODO: more intricate vendor rules (only level 1 sells, or some money-making-rule)
    vendor_regions = [v.region for v in data.vendors.values() if item_key in v.sells_all]
    if not vendor_regions:
        return lambda state: False
    return lambda state: any(state.can_reach_region(v_r, player) for v_r in vendor_regions)

def _build_all_recipe_dependencies(item_key: str) -> List[RecipeDependencies]:
    all_dependencies = [_build_recipe_dependencies(recipe) for recipe in data.recipes[item_key]]

    assert all_dependencies, f"item '{item_key}' has recipes but no valid rule"
    return all_dependencies

def build_collection_rule(item_keys: str | Iterable[str], player: int) -> Callable[[CollectionState], bool]:
    if isinstance(item_keys, str):
        item_keys = [item_keys]
    item_keys = frozenset(item_keys)

    #return lambda state, keys=item_keys, p=player: state.has_all(resolve_item_labels(keys), p)
    return lambda state, keys=item_keys, p=player: all(state.has(k, p, c) for (k, c) in resolve_item_labels(keys))
