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


ITEM_NAME_TO_ID: dict[str, int] = {}
DEFAULT_ITEM_CLASSIFICATIONS: dict[str, ItemClassification] = {}
for item_id, item_data in enumerate(data.items.values(), start=1):
    ITEM_NAME_TO_ID[item_data.label] = item_id
    DEFAULT_ITEM_CLASSIFICATIONS[item_data.label] = item_data.classification


class GraveyardKeeperItem(Item):
    game = "Graveyard Keeper"


def get_random_filler_item_name(world: GraveyardKeeperWorld) -> str:
    return world.random.choice(FILLER_ITEM_NAMES)


def create_item_with_correct_classification(
        world: GraveyardKeeperWorld,
        name: str,
) -> GraveyardKeeperItem:
    classification = DEFAULT_ITEM_CLASSIFICATIONS[name]
    return GraveyardKeeperItem(
        name,
        classification,
        ITEM_NAME_TO_ID[name],
        world.player,
    )


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

    for item_key, item_data in data.items.items():
        if item_key in data.progressive_items_reverse:
            continue
        item_pool.extend(
            world.create_item(item_data.label)
            for _ in range(item_data.amount)
        )

    for progressive_item_key, stages in data.progressive_items.items():
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

    world.multiworld.itempool += item_pool
