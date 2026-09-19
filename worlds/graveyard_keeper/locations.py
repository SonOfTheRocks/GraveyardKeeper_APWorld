from __future__ import annotations

import pprint
from typing import TYPE_CHECKING

from BaseClasses import Location, Region
from .data import *
from .items import GraveyardKeeperItem

if TYPE_CHECKING:
    from .world import GraveyardKeeperWorld

LOCATION_NAME_TO_ID = {}


class GraveyardKeeperLocation(Location):
    game: str = "Graveyard Keeper"


def create_all_locations(world: GraveyardKeeperWorld, regions: Dict[str, Region]) -> None:

    location_index: int = 1
    for region_data_name, region_data in data.regions.items():
        #if region_data_name not in regions.keys():
        #    continue

        region: Region = regions[region_data_name]
        location_keys: List[str] = region_data.locations
        event_keys: List[str] = region_data.events

        for location_key in location_keys:
            #if location_key not in data.locations:
            #    continue
            location_data = data.locations[location_key]

            location = GraveyardKeeperLocation(
                world.player,
                location_data.label,
                location_index,
                region,
            )
            region.locations.append(location)

            LOCATION_NAME_TO_ID[location_key] = location_index
            location_index += 1

        for event_key in event_keys:
            event_data = data.events[event_key]
            region.add_event(
                event_data.location_label,
                event_data.item_label,
                location_type=GraveyardKeeperLocation,
                item_type=GraveyardKeeperItem,
            )


def create_location_name_to_id_dict() -> Dict[str, int]:
    index: int = 0
    label_to_id_dict: Dict[str, int] = {}

    for region_key, region_data in data.regions.items():
        if not region_key.startswith("REGION_TECH_TREE"):
            for location_key in region_data.locations:
                if location_key not in data.locations:
                    continue
                label_to_id_dict[data.locations[location_key].label] = index
                index += 1

    tech_tree_index = 0
    for tech_tree_name in [
        "REGION_TECH_TREE_ANATOMY_AND_ALCHEMY",
        "REGION_TECH_TREE_THEOLOGY",
        "REGION_TECH_TREE_BOOK_WRITING",
        "REGION_TECH_TREE_FARMING_AND_NATURE",
        "REGION_TECH_TREE_SMITHING",
        "REGION_TECH_TREE_BUILDING",
        "REGION_TECH_TREE_COOKERY",
        "REGION_TECH_TREE_SPIRITUALISM"
    ]:
        for region_key, region_data in data.regions.items():
            if region_key.startswith(tech_tree_name) and '/' in region_key:
                for location_key in region_data.locations:
                    label = data.locations[location_key].label
                    label_to_id_dict[label] = index
                    index+=1

    #pprint.pprint(label_to_id_dict, sort_dicts=False)
    return label_to_id_dict
