from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Location, Region
from .data import *
from .items import GraveyardKeeperItem
from .regions import enabled_dlcs

if TYPE_CHECKING:
    from .world import GraveyardKeeperWorld

class GraveyardKeeperLocation(Location):
    game: str = "Graveyard Keeper"


def create_all_locations(world: GraveyardKeeperWorld, regions: dict[str, Region]) -> None:

    allowed_dlcs = enabled_dlcs(world)
    disabled_rewards = {
        reward for event in data.events.values()
        if isinstance(event, QuestEventData) and event.dlc not in allowed_dlcs
        for reward in event.rewards
    }
    for region_data_name, region_data in data.regions.items():
        region: Region | None = regions.get(region_data_name)

        for location_key in region_data.locations:
            location_data = data.locations[location_key]

            if region is None or location_key in disabled_rewards:
                continue

            location = GraveyardKeeperLocation(
                world.player,
                location_data.label,
                world.location_name_to_id[location_data.label],
                region,
            )
            region.locations.append(location)


        for event_key in region_data.events:
            if region is None:
                continue
            if event_key.startswith(CRAFTING_EVENT_PREFIX):
                # Instantiated on demand by the per-world progression analysis.
                continue
            event_data = data.events[event_key]
            if isinstance(event_data, QuestEventData) and event_data.dlc not in allowed_dlcs:
                continue
            region.add_event(
                event_data.location_label,
                event_data.item_label,
                location_type=GraveyardKeeperLocation,
                item_type=GraveyardKeeperItem,
            )


def create_location_name_to_id_dict() -> dict[str, int]:
    # Preserve the established ordering. Events have no network address.
    index: int = 1
    label_to_id_dict: dict[str, int] = {}

    for region_key, region_data in data.regions.items():
        if not region_key.startswith("REGION_TECH_TREE"):
            for location_key in region_data.locations:
                if location_key not in data.locations:
                    continue
                label_to_id_dict[data.locations[location_key].label] = index
                index += 1

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
                    index += 1

    return label_to_id_dict
