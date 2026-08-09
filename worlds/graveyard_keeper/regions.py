from __future__ import annotations

from typing import TYPE_CHECKING, Tuple
from BaseClasses import Region
from .data import *
from .models import DLCType

if TYPE_CHECKING:
    from .world import GraveyardKeeperWorld


def create_and_connect_regions(world: GraveyardKeeperWorld) -> Dict[str, Region]:

    allowed_dlcs = [DLCType.BASE_GAME]
    if world.options.stranger_sins:
        allowed_dlcs.append(DLCType.STRANGER_SINS)
    if world.options.game_of_crone:
        allowed_dlcs.append(DLCType.GAME_OF_CRONE)
    if world.options.better_save_soul:
        allowed_dlcs.append(DLCType.BETTER_SAVE_SOUL)

    regions: Dict[str, Region] = {}
    connections: List[Tuple[str, str]] = []
    for region_name, region_data in data.regions.items():
        if region_data.dlc in allowed_dlcs:
            new_region = Region(region_name, world.player, world.multiworld)

            for region_exit_name in region_data.connections:
                if data.regions[region_exit_name].dlc in allowed_dlcs:
                    connections.append((region_name, region_exit_name))

            regions[region_name] = new_region

    for source_key, dest_key in connections:
        source = data.regions[source_key].label
        dest = data.regions[dest_key].label
        regions[source_key].connect(regions[dest_key], f"{source} -> {dest}")

    return regions
