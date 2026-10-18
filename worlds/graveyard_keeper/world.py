from typing import Dict

from BaseClasses import Region
from rule_builder.cached_world import CachedRuleBuilderWorld
from . import data, items, locations, regions, rules, web_world
from . import options as graveyard_keeper_options


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
            "stranger_sins", "game_of_crone", "better_save_soul"
        )
        enabled_location_names = {
            location.name for location in self.multiworld.get_locations(self.player)
            if location.address is not None
        }
        slot_data["quest_location_triggers"] = {
            "version": 1,
            "locations": {
                location_data.label: [trigger.to_slot_data() for trigger in location_data.triggers]
                for location_data in data.data.locations.values()
                if location_data.triggers and location_data.label in enabled_location_names
            },
        }
        return slot_data
