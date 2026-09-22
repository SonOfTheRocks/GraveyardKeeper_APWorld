from __future__ import annotations

from BaseClasses import CollectionState
from rule_builder.rules import Has, Rule, False_
from . import logic
from .locations import *
from .logic.custom_rules import build_collection_rule, build_crafting_event_rule, CanGet, HasPerk, CanComplete, CanCraft
from .models import QuestEventData
from .logic.graveyard_calculator import GraveyardPointCalculator

if TYPE_CHECKING:
    from .world import GraveyardKeeperWorld


def set_all_rules(world: GraveyardKeeperWorld) -> None:
    set_all_entrance_rules(world)
    set_all_crafting_event_location_rules(world)
    set_all_location_rules(world)
    set_completion_condition(world)


def set_all_entrance_rules(world: GraveyardKeeperWorld) -> None:

    def debug_rule(state, mats):
        results = [(m, logic.is_accessible(m, state, world.player)) for m in mats]
        print(results)
        return all(r for _, r in results)

    def _set_entrance_rule(source_key: str, dest_key: str, rule: Rule) -> None:
        assert source_key in data.regions.keys()
        assert dest_key in data.regions.keys()
        source = data.regions[source_key].label
        dest = data.regions[dest_key].label
        world.set_rule(world.get_entrance(f"{source} -> {dest}"), rule)
        world.set_rule(world.get_entrance(f"{dest} -> {source}"), rule)

    # block off unreachable region
    _set_entrance_rule(
        "REGION_SWEET_HOME", UNREACHABLE_REGION_KEY,
        False_()
    )

    # rules for blockages
    blockage_rule_1 = CanCraft("BUILDABLE_REMOVE_BLOCKAGE_BASEMENT")
    blockage_rule_2 = CanCraft("BUILDABLE_REMOVE_BLOCKAGE_ALCHEMY_LAB")
    blockage_rule_3 = CanCraft("BUILDABLE_REMOVE_BLOCKAGE_VINEYARD")
    blockage_rule_4 = CanCraft("BUILDABLE_REMOVE_BLOCKAGE_SWAMP")
    _set_entrance_rule("REGION_UNDERGROUND_TUNNEL", "REGION_CELLAR", blockage_rule_1)
    # access to underground tunnel from the village is synchronized to remove the blockage in the cellar
    _set_entrance_rule("REGION_THE_VILLAGE", "REGION_UNDERGROUND_TUNNEL", blockage_rule_1)
    # access to the trade office is blocked at the start, for now synchronize it to the blockage (TODO)
    _set_entrance_rule("REGION_THE_VILLAGE", "REGION_TRADE_OFFICE", blockage_rule_1)
    _set_entrance_rule("REGION_APIARY", "REGION_FOREST_NEAR_RIVER", blockage_rule_1)
    _set_entrance_rule("REGION_SWAMP", "REGION_FOREST_NEAR_RIVER", blockage_rule_1)
    _set_entrance_rule("REGION_ALCHEMY_LAB", "REGION_UNDERGROUND_TUNNEL", blockage_rule_2)
    _set_entrance_rule("REGION_ALCHEMY_LAB", "REGION_MORGUE", blockage_rule_2)
    _set_entrance_rule("REGION_PLAINS", "REGION_VINEYARD", blockage_rule_3)
    _set_entrance_rule("REGION_PLAINS", "REGION_SWAMP", blockage_rule_4)

    _set_entrance_rule(
        "REGION_SWEET_HOME", "REGION_CELLAR",
        CanComplete("EVENT_TUTORIAL_FINISH")
    )
    _set_entrance_rule(
        "REGION_OLD_GRAVEYARD", "REGION_CHURCH",
        HasPerk("PREACHER")
    )
    _set_entrance_rule(
        "REGION_MORGUE", "REGION_SOULS_ROOM",
        build_collection_rule("EVENT_SOULS_ROOM_OPEN")
    )
    _set_entrance_rule(
        "REGION_SOULS_ROOM", "REGION_EURICS_ROOM",
        build_collection_rule("EVENT_HATCH_REPAIRED")
    )

    # rules for unlocking technologies (not researching them, just unlock)
    for (unlock_name, unlock_data) in data.unlocks.items():
        unlock_item_label = unlock_data.label
        for tech_name in unlock_data.unlocks:
            tech_region_data = data.regions[tech_name]
            assert len(tech_region_data.connections) == 1
            tech_tree_name = tech_region_data.connections[0]

            _set_entrance_rule(
                tech_tree_name, tech_name,
                Has(unlock_item_label),
            )

def set_all_crafting_event_location_rules(world: GraveyardKeeperWorld) -> None:
    for event_key, event_data in data.events.items():
        if not event_key.startswith(CRAFTING_EVENT_PREFIX):
            continue
        world.set_rule(
            world.get_location(event_data.location_label),
            build_crafting_event_rule(event_key.replace(CRAFTING_EVENT_PREFIX, ""))
        )

def set_all_location_rules(world: GraveyardKeeperWorld) -> None:

    # quest event rules
    for quest_key, quest_data in data.events.items():
        if not isinstance(quest_data, QuestEventData):
            continue
        loc = world.get_location(quest_data.location_label)
        world.set_rule(loc, CanComplete(quest_key))
        # make all quest rewards dependent on completion of their quest
        for location_key in quest_data.rewards:
            loc = world.get_location(data.locations[location_key].label)
            world.set_rule(loc, Has(quest_data.item_label))


    # rules for misc stuff
    world.set_rule(
        world.get_location(data.events["EVENT_CORPSE_HATCH_REPAIRED"].location_label),
        CanGet("ITEM_A_PIECE_OF_STONE", "ITEM_SIMPLE_IRON_PARTS")
    )

    '''
    # rules for quests
    world.set_rule(
        world.get_location(data.events["EVENT_EURIC_ARRIVE"].location_label),
        build_collection_rule(
            ["EVENT_CHURCH_OPEN", "EVENT_CORPSE_HATCH_REPAIRED", "ITEM_CORPSE"],
        )
    )
    world.set_rule(
        world.get_location(data.locations["LOCATION_GERRY_REWARD_GIVE_BEER_AND_SAND"].label),
        build_collection_rule(
            ["EVENT_EURIC_ARRIVE", "ITEM_A_MUG_OF_BEER_COPPER", "ITEM_RIVER_SAND"],
        )
    )
    world.set_rule(
        world.get_location(data.events["EVENT_SOULS_ROOM_OPEN"].location_label),
        build_collection_rule(["EVENT_EURIC_ARRIVE", "ITEM_OLD_RUSTY_KEY"])
    )
    world.set_rule(
        world.get_location(data.locations["LOCATION_EURIC_FIND_OUT_MORE_ABOUT_EURIC"].label),
        build_collection_rule("EVENT_SOULS_ROOM_OPEN")
    )
    world.set_rule(
        world.get_location(data.events["EVENT_SMILER_APPEARS"].location_label),
        build_collection_rule("EVENT_SOULS_ROOM_OPEN")
    )
    world.set_rule(
        world.get_location(data.events["EVENT_HATCH_REPAIRED"].location_label),
        build_collection_rule("ITEM_SEED_OIL")
    )
    world.set_rule(
        world.get_location(data.locations["LOCATION_EURIC_REPAIR_FURNITURE"].label),
        build_collection_rule([
            "EVENT_HATCH_REPAIRED",
            "ITEM_FLITCH",
            "ITEM_NAILS",
            "ITEM_WOODEN_PLANK",
            "ITEM_WOODEN_STICK",
            "ITEM_WOODEN_BEAM",
            "ITEM_SKIN"
        ])
    )
    world.set_rule(
        world.get_location(data.events["EVENT_STAINED_GLASS_WINDOW_INSTALLED"].location_label),
        build_collection_rule([
            "EVENT_HATCH_REPAIRED",
            "ITEM_FLITCH",
            "ITEM_NAILS",
            "ITEM_WOODEN_PLANK",
            "ITEM_WOODEN_STICK",
            "ITEM_WOODEN_BEAM",
            "ITEM_SKIN"
        ])
    )
    world.set_rule(
        world.get_location(data.events["EVENT_GERRY_ASK_ABOUT_THE_TOOTH"].location_label),
        build_collection_rule("ITEM_LOST_TOOTH")
    )
    world.set_rule(
        world.get_location(data.locations["LOCATION_ASK_SMILER_ABOUT_HUMAN_HEALING"].label),
        build_collection_rule("ITEM_LEARN_CREATE_REMOTE_CRAFT_CONTROL")
    )
    world.set_rule(
        world.get_location(data.locations["LOCATION_ROYAL_SERVICES_WRITE_A_LETTER_TO_VAGNER"].label),
        build_collection_rule("ITEM_PEN_AND_INK")
    )
    world.set_rule(
        world.get_location(data.locations["LOCATION_BISHOP_REWARD_RECITE_ODE"].label),
        build_collection_rule(["ITEM_ODE_FOR_BISHOP", "ITEM_SIN_SHARD"])
    )
    world.set_rule(
        world.get_location(data.locations["LOCATION_EURIC_HEAL_SINS_1"].label),
        lambda state: all(
            state.has(label, world.player, count ) for (label, count) in
                resolve_item_labels(["CRAFTING_STATION_EXTENSION_HEALING_FROM_PRIDE",
                                     "ITEM_PRIDE_CHARGED_SHARD"])
            )
            #and get_happiness("EURIC", state, world) >=10
    )
    world.set_rule(
        world.get_location(data.locations["LOCATION_CLOTHO_REWARD_GIVE_HONEY"].label),
        lambda state: all([
            True
        ])
    )
    world.set_rule(
        world.get_location(data.locations["LOCATION_INQUISITOR_SHOW_ASH"].label),
        build_collection_rule(["ITEM_UNUSUAL_ASH", "ITEM_SIN_SHARD"])
    )
    world.set_rule(
        world.get_location(data.locations["LOCATION_CLOTHO_ASK_ABOUT_SAUCE"].label),
        lambda state: all([
            True
        ])
    )
    world.set_rule(
        world.get_location(data.locations["LOCATION_MERCHANT_REWARD_GIVE_MYSTERIOUS_FOOD_SAUCE"].label),
        build_collection_rule(["ITEM_MYSTERIOUS_FOOD_SAUCE", "ITEM_SIN_SHARD"])
    )
    world.set_rule(
        world.get_location(data.locations["LOCATION_EURIC_HEAL_SINS_2"].label),
        build_collection_rule([
            "CRAFTING_STATION_EXTENSION_HEALING_FROM_WRATH",
            "CRAFTING_STATION_EXTENSION_HEALING_FROM_GLUTTONY",
            "ITEM_WRATH_CHARGED_SHARD",
            "ITEM_GLUTTONY_CHARGED_SHARD",
        ])
    )
    world.set_rule(
        world.get_location(data.locations["LOCATION_ASTROLOGER_REWARD_ASK_ABOUT_HIS_DAY"].label),
        build_collection_rule("ITEM_SIN_SHARD")
    )
    world.set_rule(
        world.get_location(data.locations["LOCATION_MS_CHARM_REWARD_PERSUADE_TO_DANCE"].label),
        build_collection_rule("ITEM_SIN_SHARD")
    )
    world.set_rule(
        world.get_location(data.locations["LOCATION_SNAKE_GIVE_RUMOR"].label) ,
        build_collection_rule(["ITEM_NOTE_WITH_RUMOR", "ITEM_SIN_SHARD"])
    )
    world.set_rule(
        world.get_location(data.locations["LOCATION_EURIC_HEAL_SINS_3"].label),
        build_collection_rule([
            "CRAFTING_STATION_EXTENSION_HEALING_FROM_SLOTH",
            "CRAFTING_STATION_EXTENSION_HEALING_FROM_LUST",
            "CRAFTING_STATION_EXTENSION_HEALING_FROM_ENVY",
            "ITEM_SLOTH_CHARGED_SHARD",
            "ITEM_LUST_CHARGED_SHARD",
            "ITEM_ENVY_CHARGED_SHARD",
        ])
    )
    world.set_rule(
        world.get_location(data.events["EVENT_EURIC_HEALED"].location_label),
        build_collection_rule([
            #"LOCATION_EURIC_HEAL_SINS_1",
            #"LOCATION_EURIC_HEAL_SINS_2",
            #"LOCATION_EURIC_HEAL_SINS_3",
        ])
    )
    world.set_rule(
        world.get_location(data.events["EVENT_REPAIR_VILLAGE"].location_label),
        build_collection_rule([
            "EVENT_EURIC_HEALED",
            "ITEM_WOODEN_PLANK",
            "ITEM_NAILS",
            "ITEM_FLITCH",
            "ITEM_WOODEN_STICK",
            "ITEM_A_PIECE_OF_STONE",
            "ITEM_HEMP_ROPE",
            "ITEM_ASH",
            "ITEM_SIMPLE_IRON_PARTS",
            "ITEM_COMPLEX_IRON_PARTS",
            "ITEM_WOOD_REPAIR_KIT",
            "ITEM_BEE",
            "ITEM_GLASS",
        ])
    )
    world.set_rule(
        world.get_location(data.locations["LOCATION_TRESS_REWARD_FOR_FIXING_THE_VILLAGE"].label),
        build_collection_rule("EVENT_REPAIR_VILLAGE")
    )
    '''

    world.set_rule(
        world.get_location(data.events["EVENT_ENTER_PORTAL"].location_label),
        CanGet("ITEM_PORTAL_EMITTER", "ITEM_PORTAL_BARREL")
    )


def set_completion_condition(world: GraveyardKeeperWorld) -> None:
    if world.options.goal.value == world.options.goal.option_portal:
        world.set_completion_rule(Has(data.events["EVENT_ENTER_PORTAL"].item_label))

    if world.options.goal.value == world.options.goal.option_graveyard:
        world.multiworld.completion_condition[world.player] = (
            lambda state: get_max_possible_graveyard_points(state, world) >= world.options.graveyard_goal_rating.value
        )
    return

def get_max_possible_graveyard_points(state, world) -> int:
    return GraveyardPointCalculator(state, world).calculate()

def get_happiness(npc: str, state: CollectionState, world: GraveyardKeeperWorld) -> int:
    character_happiness_items = [
        (key, item) for (key, item) in data.items.items()
        if key.startswith(f"ITEM_{npc}_HAPPINESS_")
    ]
    happiness = 0
    for (key, item_data) in character_happiness_items:
        assert item_data.classification == ItemClassification.progression, \
                f"item {key} requires PROGRESSION classification (every happiness item does)"
        count = state.count(item_data.label, world.player)
        amount = int(key.split("_")[-1])
        happiness += count * amount
    return happiness

