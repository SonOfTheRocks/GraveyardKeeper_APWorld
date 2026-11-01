from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification
from .data import data

if TYPE_CHECKING:
    from .world import GraveyardKeeperWorld


FILLER_ITEM_NAMES = [
    "Red Research Points",
    "Green Research Points",
    "Blue Research Points",
]

# The former random Monsters Trap remains reserved, but is not generated.
TRAP_WEIGHT_OPTIONS = {
    "ITEM_BATS_TRAP": "bats_trap_weight",
    "ITEM_GREEN_SLIME_TRAP": "green_slime_trap_weight",
}


ITEM_NAME_TO_ID: dict[str, int] = {}
DEFAULT_ITEM_CLASSIFICATIONS: dict[str, ItemClassification] = {}
legacy_item_id = 0
for item_data in data.items.values():
    if item_data.code is None:
        legacy_item_id += 1
    ITEM_NAME_TO_ID[item_data.label] = item_data.code if item_data.code is not None else legacy_item_id
    DEFAULT_ITEM_CLASSIFICATIONS[item_data.label] = item_data.classification
if len(set(ITEM_NAME_TO_ID.values())) != len(ITEM_NAME_TO_ID):
    raise ValueError("Graveyard Keeper item IDs must be unique")


class GraveyardKeeperItem(Item):
    game = "Graveyard Keeper"


def get_random_filler_item_name(world: GraveyardKeeperWorld) -> str:
    return world.random.choice(FILLER_ITEM_NAMES)


def create_item_with_correct_classification(
        world: GraveyardKeeperWorld,
        name: str,
) -> GraveyardKeeperItem:
    classification = get_item_classification(world, name)
    return GraveyardKeeperItem(
        name,
        classification,
        ITEM_NAME_TO_ID[name],
        world.player,
    )


def get_item_classification(world: GraveyardKeeperWorld, name: str) -> ItemClassification:
    from .logic.progression import RECIPE_ITEM_NAMES

    classification = DEFAULT_ITEM_CLASSIFICATIONS[name]
    if name in RECIPE_ITEM_NAMES:
        plan = getattr(world, "progression_plan", None)
        # Start inventory can be created before regions/logic. Its flags and
        # CollectionState are reconciled once the plan is available.
        if plan is None or name in plan.required_items:
            return ItemClassification.progression
    return classification


def _fit_item_pool_to_location_count(
        world: GraveyardKeeperWorld,
        item_pool: list[GraveyardKeeperItem],
        location_count: int,
) -> list[GraveyardKeeperItem]:
    open_location_count = location_count - len(item_pool)
    if open_location_count >= 0:
        additional_filler = [
            world.create_filler()
            for _ in range(open_location_count)
        ]
        return item_pool + additional_filler

    excess_item_count = -open_location_count
    filler_indexes = [
        index
        for index, item in enumerate(item_pool)
        if item.classification == ItemClassification.filler
    ]
    if len(filler_indexes) < excess_item_count:
        raise ValueError(
            f"Item pool has {excess_item_count} more items than locations, but only "
            f"{len(filler_indexes)} filler items can be removed."
        )

    removed_indexes = set(
        world.random.sample(filler_indexes, excess_item_count)
    )
    return [
        item
        for index, item in enumerate(item_pool)
        if index not in removed_indexes
    ]


def _create_declared_item_pool(
        world: GraveyardKeeperWorld,
) -> list[GraveyardKeeperItem]:
    item_pool: list[GraveyardKeeperItem] = []
    from .regions import enabled_dlcs
    allowed_dlcs = enabled_dlcs(world)

    for item_key, item_data in data.items.items():
        if item_data.classification & ItemClassification.trap:
            # Added only by the trap percentage after balancing the normal pool.
            continue
        if item_data.dlc not in allowed_dlcs:
            continue
        # Retain the legacy definitions/IDs for a future availability option.
        # Native research-area access currently remains vanilla.
        if item_key in data.unlocks:
            continue
        if item_key in data.progressive_items_reverse or item_key in data.progressive_items:
            continue
        item_pool.extend(
            world.create_item(item_data.label)
            for _ in range(item_data.amount)
        )

    for progressive_item_key, stages in data.progressive_items.items():
        if data.items[progressive_item_key].dlc not in allowed_dlcs:
            continue
        item_pool.extend(
            world.create_item(data.items[progressive_item_key].label)
            for _ in stages
        )

    return item_pool


def create_all_items(world: GraveyardKeeperWorld) -> None:
    item_pool = _create_declared_item_pool(world)

    unfilled_location_count = len(
        world.multiworld.get_unfilled_locations(world.player)
    )
    item_pool = _fit_item_pool_to_location_count(
        world,
        item_pool,
        unfilled_location_count,
    )

    percentage = world.options.trap_percentage.value
    if percentage:
        from .regions import enabled_dlcs
        allowed_dlcs = enabled_dlcs(world)
        weighted_traps = [(data.items[key].label, getattr(world.options, option).value)
                          for key, option in TRAP_WEIGHT_OPTIONS.items()
                          if data.items[key].dlc in allowed_dlcs and getattr(world.options, option).value > 0]
        if not weighted_traps:
            raise ValueError("trap_percentage is enabled, but bats_trap_weight and green_slime_trap_weight are both 0. "
                             "Set at least one trap weight above 0, or disable traps with trap_percentage: 0.")
        trap_names, weights = zip(*weighted_traps)
        filler_indexes = [index for index, item in enumerate(item_pool)
                          if item.classification == ItemClassification.filler]
        for index in world.random.sample(filler_indexes, len(filler_indexes) * percentage // 100):
            item_pool[index] = world.create_item(world.random.choices(trap_names, weights=weights, k=1)[0])

    world.multiworld.itempool += item_pool
