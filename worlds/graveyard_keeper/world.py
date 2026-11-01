import pkgutil
from typing import Dict, TYPE_CHECKING

import orjson

from BaseClasses import Region
from Options import OptionError
from rule_builder.cached_world import CachedRuleBuilderWorld
from . import items, locations, regions, rules, web_world
from .data import load_json_data
from . import options as graveyard_keeper_options

if TYPE_CHECKING:
    from .logic.progression import ProgressionPlan


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
    progression_plan: "ProgressionPlan"

    location_name_to_id = locations.create_location_name_to_id_dict()
    item_name_to_id = items.ITEM_NAME_TO_ID

    origin_region_name = "Sweet Home"

    def create_regions(self):
        all_regions: Dict[str, Region] = regions.create_and_connect_regions(self)
        locations.create_all_locations(self, all_regions)

        self.multiworld.regions.extend(all_regions.values())

        # AP creates items before calling set_rules. Resolve the logic now so
        # every item is created with its final, player-specific classification.
        rules.set_all_rules(self)
        from .logic.progression import build_progression_plan
        self.progression_plan = build_progression_plan(self)
        self._update_precollected_classifications()

    def set_rules(self):
        # Core registers cross-rule cache dependencies after this hook.
        pass

    def _update_precollected_classifications(self):
        for item in self.multiworld.precollected_items[self.player]:
            classification = items.get_item_classification(self, item.name)
            if item.classification != classification:
                self.multiworld.state.remove(item)
                item.classification = classification
                self.multiworld.state.collect(item, prevent_sweep=True)

    def create_items(self):
        items.create_all_items(self)

    def generate_basic(self):
        # All players' pools and rules now exist, and entrances are connected.
        # Sweep reachable events instead of assuming every declared event is free.
        if self.options.goal.value != graveyard_keeper_options.Goal.option_graveyard or \
                self.options.graveyard_goal_rating.value == 0:
            return

        state = self.multiworld.get_all_state()
        if self.multiworld.completion_condition[self.player](state):
            return

        from .data import data
        from .logic.graveyard_calculator import GraveyardPointCalculator
        maximum = (GraveyardPointCalculator(state, self).calculate()
                   if state.can_reach_region(data.regions["REGION_OLD_GRAVEYARD"].label, self.player) else 0)
        dlcs = ", ".join(f"{name}={getattr(self.options, name).value}"
                         for name in ("stranger_sins", "game_of_crone", "better_save_soul"))
        raise OptionError(
            f"graveyard_goal_rating={self.options.graveyard_goal_rating.value} is unreachable for "
            f"{self.multiworld.get_player_name(self.player)}: the modeled reachable maximum with all "
            f"available items is {maximum} ({dlcs}). Lower graveyard_goal_rating or change the DLC options."
        )

    def create_item(self, name: str) -> items.GraveyardKeeperItem:
        return items.create_item_with_correct_classification(self, name)

    def get_filler_item_name(self) -> str:
        return items.get_random_filler_item_name(self)

    def fill_slot_data(self):
        slot_data = self.options.as_dict(
            "goal", "graveyard_goal_rating", "stranger_sins", "game_of_crone", "better_save_soul", "trap_percentage",
            "bats_trap_weight", "green_slime_trap_weight"
        )
        slot_data["client_version"] = WORLD_VERSION
        slot_data["graveyard_keeper_data_version"] = load_json_data("manifest.json")["data_version"]
        return slot_data
