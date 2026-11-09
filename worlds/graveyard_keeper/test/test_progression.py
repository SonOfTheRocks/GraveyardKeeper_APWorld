from argparse import Namespace
from itertools import product
from pathlib import Path
from unittest.mock import patch
import json

import pytest

from BaseClasses import CollectionState, ItemClassification, MultiWorld, Region
from Fill import distribute_items_restrictive
from rule_builder.rules import CanReachLocation, Has, Or, Rule, True_
from worlds.AutoWorld import call_all
from ..data import CRAFTING_EVENT_PREFIX, CRAFTING_REGION_KEY, data, load_json_data
from ..items import get_item_classification
from ..locations import GraveyardKeeperLocation
from ..logic.grave_calculator import GravePointCalculator
from ..logic.graveyard_calculator import GraveyardPointCalculator
from ..logic.goal_rules import HasGraveyardRating
from ..logic.progression import RECIPE_ITEM_NAMES, build_progression_plan
from ..logic.custom_rules import CanGet
from ..models import EventData, SimpleRecipeData
from ..regions import enabled_dlcs
from ..world import GraveyardKeeperWorld
from .fakes import FakeWorld


def generate_worlds(*options):
    multiworld = MultiWorld(len(options))
    multiworld.set_seed(12345)
    multiworld.seed_name = "recipe-progression-test"
    multiworld.player_name = {player: f"Player {player}" for player in multiworld.player_ids}
    args = Namespace()
    for player in multiworld.player_ids:
        multiworld.game[player] = GraveyardKeeperWorld.game
    for name, option in GraveyardKeeperWorld.options_dataclass.type_hints.items():
        setattr(args, name, {player: option.from_any(options[player - 1].get(name, option.default))
                             for player in multiworld.player_ids})
    multiworld.set_options(args)
    multiworld.state = CollectionState(multiworld)
    call_all(multiworld, "generate_early")
    for player, values in enumerate(options, 1):
        for option in ("start_inventory", "start_inventory_from_pool"):
            for name, count in values.get(option, {}).items():
                for _ in range(count):
                    multiworld.push_precollected(multiworld.worlds[player].create_item(name))
    for step in ("create_regions", "create_items", "set_rules"):
        call_all(multiworld, step)
    return multiworld


ALL_DLCS = dict(stranger_sins=True, game_of_crone=True, better_save_soul=True)


def assert_active_dependencies_are_progression(world):
    rules = [location.access_rule for location in world.get_locations()]
    rules.extend(entrance.access_rule for entrance in world.multiworld.get_entrances(world.player))
    rules.append(world.multiworld.completion_condition[world.player])
    for rule in rules:
        if isinstance(rule, Rule.Resolved):
            for name in rule.item_dependencies():
                if name in world.item_name_to_id:
                    assert world.create_item(name).advancement, name
                else:
                    assert any(location.item and location.item.name == name
                               for location in world.get_locations()), name


@pytest.mark.parametrize("dlcs", list(product((False, True), repeat=3)))
@pytest.mark.parametrize("vendor_logic", (0, 1, 2))
@pytest.mark.parametrize("goal", (0, 1))
def test_active_dependencies_for_every_option_combination(dlcs, vendor_logic, goal):
    options = dict(zip(ALL_DLCS, dlcs)) | dict(vendor_logic=vendor_logic, goal=goal)
    multiworld = generate_worlds(options)
    world = multiworld.worlds[1]
    assert_active_dependencies_are_progression(world)
    assert len(multiworld.itempool) == len(multiworld.get_unfilled_locations(1))
    assert all(location.address == world.location_name_to_id[location.name]
               for location in world.get_locations() if location.address is not None)
    assert multiworld.has_beaten_game(multiworld.get_all_state())
    allowed = enabled_dlcs(world)
    by_name = {item.label: item for item in data.items.values()}
    assert all(by_name[item.name].dlc in allowed for item in multiworld.itempool)
    assert not {name for name in world.progression_plan.required_items
                if name in by_name and by_name[name].dlc not in allowed}


def test_unused_recipes_use_data_defaults_and_events_are_pruned():
    multiworld = generate_worlds(ALL_DLCS)
    world = multiworld.worlds[1]
    assert world.create_item(data.items["ITEM_LEARN_CREATE_ALCHEMISTS_BAG"].label).classification == ItemClassification.useful
    unused = RECIPE_ITEM_NAMES - world.progression_plan.required_items
    assert unused
    assert any(world.create_item(name).classification == ItemClassification.filler for name in unused)
    for name in unused:
        assert get_item_classification(world, name) in (ItemClassification.filler, ItemClassification.useful)
    generated = {location.name for location in world.get_locations()}
    for key, event in data.events.items():
        if key.startswith(CRAFTING_EVENT_PREFIX):
            assert (event.location_label in generated) == (key in world.progression_plan.required_events)
    assert len(world.progression_plan.required_events) < len(data.events)


def test_progressive_recipe_stages_share_the_required_classification():
    world = generate_worlds(ALL_DLCS).worlds[1]
    name = data.items["ITEM_BP_PROGRESSIVE_FURNACE"].label
    assert name in world.progression_plan.required_items
    copies = [item for item in world.multiworld.itempool if item.name == name]
    assert len(copies) == len(data.progressive_items["ITEM_BP_PROGRESSIVE_FURNACE"])
    assert all(item.advancement for item in copies)


@pytest.mark.parametrize("option", ("start_inventory", "start_inventory_from_pool"))
def test_start_inventory_is_reclassified_and_still_supplies_required_recipes(option):
    required = data.items["ITEM_BP_PROGRESSIVE_FURNACE"].label
    optional = data.items["ITEM_LEARN_CREATE_ALCHEMISTS_BAG"].label
    multiworld = generate_worlds(ALL_DLCS | {option: {required: 1, optional: 1}})
    items = {item.name: item for item in multiworld.precollected_items[1]}
    assert items[required].advancement
    assert items[optional].classification == ItemClassification.useful
    assert multiworld.state.has(required, 1)
    assert not multiworld.state.has(optional, 1)
    assert CollectionState(multiworld).has(required, 1)


def test_world_plans_are_isolated_and_deterministic():
    before = {name: item.classification for name, item in data.items.items()}
    options = [ALL_DLCS | {"goal": 0}, ALL_DLCS | {"goal": 1}]
    first = generate_worlds(*options)
    second = generate_worlds(*options)
    assert first.worlds[1].progression_plan is not first.worlds[2].progression_plan
    assert first.worlds[1].progression_plan != first.worlds[2].progression_plan
    for player in first.player_ids:
        assert first.worlds[player].progression_plan == second.worlds[player].progression_plan
        assert_active_dependencies_are_progression(first.worlds[player])
    assert before == {name: item.classification for name, item in data.items.items()}
    assert [(item.name, item.classification) for item in first.itempool] == [
        (item.name, item.classification) for item in second.itempool]


def test_recipe_defaults_match_the_companion_client():
    root = Path(__file__).resolve().parents[5] / "RiderProjects/GraveyardKeepelago/External/GraveyardKeeperData/items"
    if not root.exists():
        pytest.skip("Companion client checkout is unavailable")
    definitions = {}
    for path in root.rglob("*.json"):
        definitions.update(json.loads(path.read_text(encoding="utf-8-sig")))
    flags = {"FILLER": ItemClassification.filler, "USEFUL": ItemClassification.useful}
    for key, item in data.items.items():
        if item.label in RECIPE_ITEM_NAMES:
            assert item.classification == flags[definitions[key]["classification"]]


def test_graveyard_goal_declares_every_observed_state_input():
    multiworld = generate_worlds(ALL_DLCS | {"goal": 1})
    world = multiworld.worlds[1]
    dependencies = set(multiworld.completion_condition[1].item_dependencies())
    # Exercise empty and full states to cover both branches of score alternatives.
    for state in (CollectionState(multiworld), multiworld.get_all_state()):
        observed = set()
        original_has, original_count = state.has, state.count
        def has(name, player, count=1):
            observed.add(name)
            return original_has(name, player, count)
        def count(name, player):
            observed.add(name)
            return original_count(name, player)
        with patch.object(state, "has", side_effect=has), patch.object(state, "count", side_effect=count):
            GraveyardPointCalculator(state, world).calculate()
        assert observed <= dependencies


def test_grave_crafting_checks_evaluate_the_rule_in_the_current_state():
    world = generate_worlds(ALL_DLCS | {"goal": 1}).worlds[1]
    empty = CollectionState(world.multiworld)
    assert not GravePointCalculator(empty, world)._can_craft("ITEM_GOLD_INJECTION")
    full = world.multiworld.get_all_state()
    assert GravePointCalculator(full, world)._can_craft("ITEM_GOLD_INJECTION")


def test_zero_graveyard_goal_needs_no_goal_dependencies():
    world = generate_worlds(ALL_DLCS | {"goal": 1, "graveyard_goal_rating": 0}).worlds[1]
    rule = world.multiworld.completion_condition[1]
    assert not rule.item_dependencies()
    assert rule(CollectionState(world.multiworld))


def analysis_world():
    multiworld = MultiWorld(1)
    multiworld.game[1] = GraveyardKeeperWorld.game
    world = GraveyardKeeperWorld(multiworld, 1)
    multiworld.worlds[1] = world
    world.options = FakeWorld().options
    home = Region("Sweet Home", 1, multiworld)
    crafting = Region(data.regions[CRAFTING_REGION_KEY].label, 1, multiworld)
    multiworld.regions.extend((home, crafting))
    check = GraveyardKeeperLocation(1, "Test check", 1, home)
    home.locations.append(check)
    world.set_completion_rule(True_())
    return world, home, check


def test_transitive_alternatives_and_cycles_do_not_activate_unrelated_events():
    world, home, check = analysis_world()
    events = {CRAFTING_EVENT_PREFIX + name: EventData("Can obtain " + name, "Can obtain " + name)
              for name in ("TEST_A", "TEST_B", "TEST_UNUSED")}
    events["ORPHAN"] = EventData("Unused quest", "Unused quest item")
    recipes = {
        "TEST_A": [SimpleRecipeData("TEST_A", 0, frozenset(), "ITEM_LEARN_CREATE_ROOF_TILE",
                                    frozenset({"TEST_B"}), frozenset())],
        "TEST_B": [SimpleRecipeData("TEST_B", 0, frozenset(), None, frozenset({"TEST_A"}), frozenset()),
                   SimpleRecipeData("TEST_B", 1, frozenset(), "ITEM_LEARN_CREATE_ALCHEMISTS_BAG",
                                    frozenset(), frozenset())],
        "TEST_UNUSED": [SimpleRecipeData("TEST_UNUSED", 0, frozenset(), "ITEM_LEARN_CREATE_MYSTERIOUS_FOOD_SAUCE",
                                         frozenset(), frozenset())],
    }
    with patch.object(data, "events", events), patch.object(data, "recipes", recipes):
        home.add_event("Unused quest", "Unused quest item")
        world.set_rule(world.get_location("Unused quest"), CanGet("TEST_UNUSED"))
        world.set_rule(check, CanGet("TEST_A"))
        world.progression_plan = build_progression_plan(world)
    assert world.progression_plan.required_events == frozenset({CRAFTING_EVENT_PREFIX + "TEST_A", CRAFTING_EVENT_PREFIX + "TEST_B"})
    assert world.create_item(data.items["ITEM_LEARN_CREATE_ROOF_TILE"].label).advancement
    assert world.create_item(data.items["ITEM_LEARN_CREATE_ALCHEMISTS_BAG"].label).advancement
    assert data.items["ITEM_LEARN_CREATE_MYSTERIOUS_FOOD_SAUCE"].label not in world.progression_plan.required_items
    assert "Unused quest" not in {location.name for location in world.get_locations()}
    assert "Can obtain TEST_UNUSED" not in {location.name for location in world.get_locations()}


def test_both_direct_or_alternatives_are_progression():
    world, _, check = analysis_world()
    names = [data.items[key].label for key in ("ITEM_LEARN_CREATE_ROOF_TILE", "ITEM_LEARN_CREATE_ALCHEMISTS_BAG")]
    world.set_rule(check, Or(*(Has(name) for name in names)))
    world.progression_plan = build_progression_plan(world)
    assert all(world.create_item(name).advancement for name in names)


def test_location_reference_keeps_the_referenced_internal_event():
    world, home, check = analysis_world()
    name = data.items["ITEM_LEARN_CREATE_ROOF_TILE"].label
    with patch.object(data, "events", {"TEST_EVENT": EventData("Test event", "Test event item")}):
        home.add_event("Test event", "Test event item")
        world.set_rule(world.get_location("Test event"), Has(name))
        world.set_rule(check, CanReachLocation("Test event"))
        plan = build_progression_plan(world)
    assert plan.required_events == frozenset({"TEST_EVENT"})
    assert name in plan.required_items


def test_non_recipe_filler_dependencies_fail_loudly():
    world, _, check = analysis_world()
    world.set_rule(check, Has("Red Research Points"))
    with pytest.raises(ValueError, match="Active logic requires non-progression item"):
        build_progression_plan(world)


def test_opaque_rule_dependencies_fail_loudly():
    world, _, check = analysis_world()
    check.access_rule = lambda state: state.has("Create: Roof tile", 1)
    with pytest.raises(TypeError, match="declared Rule Builder dependencies"):
        build_progression_plan(world)


@pytest.mark.parametrize("game_of_crone,better_save_soul", product((False, True), repeat=2))
def test_progressive_grave_scores_retain_earlier_stages(game_of_crone, better_save_soul):
    from .fakes import FakeState
    world = FakeWorld({"game_of_crone": game_of_crone, "better_save_soul": better_save_soul})
    for key, method in (
        ("ITEM_LEARN_CREATE_PROGRESSIVE_WOODEN_GRAVE_MARKER", "_wood_tombstone"),
        ("ITEM_LEARN_CREATE_PROGRESSIVE_STONE_GRAVE_MARKER", "_stone_tombstone"),
        ("ITEM_LEARN_CREATE_PROGRESSIVE_MARBLE_GRAVE_MARKER", "_marble_tombstone"),
        ("ITEM_LEARN_CREATE_PROGRESSIVE_STONE_GRAVE_FENCE", "_stone_fence"),
        ("ITEM_LEARN_CREATE_PROGRESSIVE_MARBLE_GRAVE_FENCE", "_marble_fence"),
    ):
        scores = [getattr(GravePointCalculator(FakeState(counts={data.items[key].label: count}), world), method)()
                  for count in range(len(data.progressive_items[key]) + 2)]
        assert scores == sorted(scores), (key, scores)
        assert scores[-1] > 0


def test_all_progressive_pool_counts_match_client_stage_definitions():
    multiworld = generate_worlds(ALL_DLCS)
    for key, stages in data.progressive_items.items():
        assert sum(item.name == data.items[key].label for item in multiworld.itempool) == len(stages)


def test_graveyard_completion_updates_after_collecting_and_removing_recipes():
    multiworld = generate_worlds(ALL_DLCS | {"goal": 1})
    state = CollectionState(multiworld)
    goal = multiworld.completion_condition[1]
    assert not goal(state)
    for item in multiworld.itempool:
        state.collect(item, prevent_sweep=True)
    state.sweep_for_advancements()
    assert goal(state)
    # A fresh empty state must not share the populated state's cached result.
    assert not goal(CollectionState(multiworld))


def test_graveyard_rule_does_not_keep_generated_worlds_alive():
    import gc
    import weakref
    multiworld = generate_worlds(ALL_DLCS | {"goal": 1})
    reference = weakref.ref(multiworld)
    del multiworld
    gc.collect()
    assert reference() is None


@pytest.mark.parametrize("goal", (0, 1))
def test_restrictive_fill_can_place_the_dynamic_pool(goal):
    multiworld = generate_worlds(ALL_DLCS | {"goal": goal})
    distribute_items_restrictive(multiworld)
    assert not multiworld.get_unfilled_locations(1)
    assert multiworld.can_beat_game()


def test_restrictive_fill_supports_two_players_with_different_goals():
    multiworld = generate_worlds(ALL_DLCS | {"goal": 0}, ALL_DLCS | {"goal": 1})
    distribute_items_restrictive(multiworld)
    assert not multiworld.get_unfilled_locations()
    assert multiworld.can_beat_game()
