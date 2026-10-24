import pkgutil
from typing import Dict

import orjson

from BaseClasses import Region
from rule_builder.cached_world import CachedRuleBuilderWorld
from . import items, locations, regions, rules, web_world
from .data import load_json_data
from . import options as graveyard_keeper_options


def _load_world_version() -> str:
    raw_metadata = pkgutil.get_data(__package__, "archipelago.json")
    if raw_metadata is None:
        raise FileNotFoundError("Could not load Graveyard Keeper archipelago.json")
    return orjson.loads(raw_metadata)["world_version"]


WORLD_VERSION = _load_world_version()


class GraveyardKeeperWorld(CachedRuleBuilderWorld):
    game = "Graveyard Keeper"

    web = web_world.GraveyardKeeperWebWorld()

    options_dataclass = graveyard_keeper_options.GraveyardKeeperOptions
    options: graveyard_keeper_options.GraveyardKeeperOptions

    location_name_to_id = locations.create_location_name_to_id_dict()
    item_name_to_id = items.ITEM_NAME_TO_ID

    origin_region_name = "Sweet Home"

    def create_regions(self):
        all_regions: Dict[str, Region] = regions.create_and_connect_regions(self)
        locations.create_all_locations(self, all_regions)

        self.multiworld.regions.extend(all_regions.values())

    def set_rules(self):
        rules.set_all_rules(self)

    def create_items(self):
        items.create_all_items(self)

    def create_item(self, name: str) -> items.GraveyardKeeperItem:
        return items.create_item_with_correct_classification(self, name)

    def get_filler_item_name(self) -> str:
        return items.get_random_filler_item_name(self)

    def fill_slot_data(self):
        slot_data = self.options.as_dict(
            "goal", "stranger_sins", "game_of_crone", "better_save_soul"
        )
        slot_data["client_version"] = WORLD_VERSION
        slot_data["graveyard_keeper_data_version"] = load_json_data("manifest.json")["data_version"]
        return slot_data
