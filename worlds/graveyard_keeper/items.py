from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item
from .data import *

if TYPE_CHECKING:
    from .world import GraveyardKeeperWorld


FILLER_ITEMS = [
    "Red Research Points",
    "Green Research Points",
    "Blue Research Points",
]


ITEM_NAME_TO_ID = {}
DEFAULT_ITEM_CLASSIFICATIONS: Dict[str, ItemClassification] = {}
for (item_id, (item_name, item_data)) in enumerate(data.items.items()):
    ITEM_NAME_TO_ID[item_data.label] = item_id
    DEFAULT_ITEM_CLASSIFICATIONS[item_data.label] = data.items[item_name].classification


class GraveyardKeeperItem(Item):
    game = "Graveyard Keeper"


def get_random_filler_item_name(world: GraveyardKeeperWorld) -> str:
    return world.random.choice(FILLER_ITEMS)


def create_item_with_correct_classification(world: GraveyardKeeperWorld, name: str) -> GraveyardKeeperItem:
    classification = DEFAULT_ITEM_CLASSIFICATIONS[name]
    return GraveyardKeeperItem(name, classification, ITEM_NAME_TO_ID[name], world.player)


def create_all_items(world: GraveyardKeeperWorld) -> None:
    # create non-progressive items
    itempool = []
    for (item_key, item) in data.items.items():
        if item_key in data.progressive_items_reverse.keys():
            continue
        for _ in range(item.amount):
            itempool.append(world.create_item(data.items[item_key].label))

    for (item, value) in data.progressive_items.items():
        count: int = len(value)
        for _ in range(count):
            itempool.append(world.create_item(data.items[item].label))

    number_of_items = len(itempool)
    number_of_unfilled_locations = len(world.multiworld.get_unfilled_locations(world.player))
    needed_number_of_filler_items = number_of_unfilled_locations - number_of_items
    print(f"Creating {needed_number_of_filler_items} filler items to fill up the pool.")
    itempool += [world.create_filler() for _ in range(needed_number_of_filler_items)]

    world.multiworld.itempool += itempool