from collections import Counter
import hashlib
import json
from itertools import product
import pytest

from BaseClasses import ItemClassification, PlandoOptions
from Fill import distribute_items_restrictive
from .test_progression import generate_worlds, ALL_DLCS
from ..data import data, load_json_data
from ..items import ITEM_NAME_TO_ID
from ..options import TrapWeights
from Options import OptionError
from ..world import GraveyardKeeperWorld


@pytest.mark.parametrize("percentage", (0, 1, 25, 50, 100))
@pytest.mark.parametrize("dlcs", list(product((False, True), repeat=3)))
def test_traps_replace_only_filler_and_preserve_pool_size(percentage, dlcs):
    options = dict(zip(ALL_DLCS, dlcs))
    normal = generate_worlds(options)
    trapped = generate_worlds(options | {"trap_percentage": percentage})
    filler_count = sum(item.classification == ItemClassification.filler for item in normal.itempool)
    traps = [item for item in trapped.itempool if item.classification == ItemClassification.trap]
    assert len(traps) == filler_count * percentage // 100
    assert all((item.name, item.code) in {("Bats Trap", 488), ("Green Slime Trap", 489)} for item in traps)
    assert not any(item.name == "Monsters Trap" for item in trapped.itempool)
    assert len(trapped.itempool) == len(normal.itempool)
    for classification in (ItemClassification.progression, ItemClassification.useful):
        assert Counter(item.name for item in normal.itempool if item.classification == classification) == Counter(
            item.name for item in trapped.itempool if item.classification == classification)
    assert trapped.worlds[1].fill_slot_data()["trap_percentage"] == percentage
    assert trapped.has_beaten_game(trapped.get_all_state())


@pytest.mark.parametrize("key,code,trap_id", (
    ("ITEM_BATS_TRAP", 488, "bats"),
    ("ITEM_GREEN_SLIME_TRAP", 489, "green_slimes"),
))
def test_trap_has_an_explicit_id_and_matching_shared_grant(key, code, trap_id):
    trap = data.items[key]
    assert ITEM_NAME_TO_ID[trap.label] == code
    assert trap.classification == ItemClassification.trap
    assert load_json_data("item_grants.json")[key] == {"type": "trap", "trap_id": trap_id}


def test_only_specific_traps_exist_in_the_public_contract():
    expected = {"ITEM_BATS_TRAP", "ITEM_GREEN_SLIME_TRAP"}
    assert {key for key, item in data.items.items() if item.classification == ItemClassification.trap} == expected
    assert "ITEM_MONSTERS_TRAP" not in data.items
    assert "Monsters Trap" not in GraveyardKeeperWorld.item_name_to_id
    assert "ITEM_MONSTERS_TRAP" not in load_json_data("item_grants.json")


def test_current_item_and_location_ids_are_deterministic():
    # Item IDs retain their existing assignments. The location snapshot is the
    # deliberately cleaned pre-release v8 contract, without 65 unused addresses.
    mappings = (
        ({item.label: ITEM_NAME_TO_ID[item.label] for item in data.items.values() if item.classification != ItemClassification.trap},
         "f41fbc1e0adefad186fba4fd21fc1f8769156935b6ba19f236573d2c43dca160"),
        (GraveyardKeeperWorld.location_name_to_id,
         "999a039e2cfaf4b229cb270a12a936b253dcfb6c6ede7fada2d2f68672acc72b"),
    )
    for mapping, expected in mappings:
        serialized = json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode()
        assert hashlib.sha256(serialized).hexdigest() == expected


@pytest.mark.parametrize("dlcs", list(product((False, True), repeat=3)))
@pytest.mark.parametrize("bats,slimes,expected", ((100, 0, "Bats Trap"), (0, 100, "Green Slime Trap")))
def test_zero_weight_excludes_that_trap_type(bats, slimes, expected, dlcs):
    multiworld = generate_worlds(dict(zip(ALL_DLCS, dlcs)) | {
        "trap_percentage": 100, "trap_weights": {"Bats Trap": bats, "Green Slime Trap": slimes}})
    traps = [item.name for item in multiworld.itempool if item.trap]
    assert traps and set(traps) == {expected}
    slot = multiworld.worlds[1].fill_slot_data()
    assert slot["trap_weights"] == {"Bats Trap": bats, "Green Slime Trap": slimes}


def test_relative_weights_change_the_mix_without_changing_total_traps():
    pools = []
    for bats, slimes in ((90, 10), (10, 90)):
        world = generate_worlds(ALL_DLCS | {
            "trap_percentage": 100, "trap_weights": {"Bats Trap": bats, "Green Slime Trap": slimes}})
        pools.append(Counter(item.name for item in world.itempool if item.trap))
    assert pools[0]["Bats Trap"] > pools[0]["Green Slime Trap"] > 0
    assert pools[1]["Green Slime Trap"] > pools[1]["Bats Trap"] > 0
    assert pools[0].total() == pools[1].total()


def test_enabled_traps_require_a_positive_weight_but_disabled_traps_do_not():
    options = ALL_DLCS | {"trap_weights": {"Bats Trap": 0, "Green Slime Trap": 0}}
    with pytest.raises(ValueError, match="no positive weights"):
        generate_worlds(options | {"trap_percentage": 25})
    disabled = generate_worlds(options | {"trap_percentage": 0})
    assert not any(item.trap for item in disabled.itempool)


@pytest.mark.parametrize("weights", ({}, {"Bats Trap": 0}))
def test_empty_or_zero_weights_require_traps_to_be_disabled(weights):
    with pytest.raises(ValueError, match="no positive weights"):
        generate_worlds(ALL_DLCS | {"trap_percentage": 25, "trap_weights": weights})
    disabled = generate_worlds(ALL_DLCS | {"trap_weights": weights})
    assert not any(item.trap for item in disabled.itempool)


def test_omitted_trap_type_is_disabled_and_weights_can_exceed_one_hundred():
    world = generate_worlds(ALL_DLCS | {
        "trap_percentage": 100, "trap_weights": {"Bats Trap": 200},
    })
    assert {item.name for item in world.itempool if item.trap} == {"Bats Trap"}
    assert world.worlds[1].fill_slot_data()["trap_weights"] == {"Bats Trap": 200}


@pytest.mark.parametrize("weights", (
    {"Unknown Trap": 1}, {"Bats Trap": -1},
))
def test_trap_weight_validation_rejects_unknown_types_and_negative_weights(weights):
    option = TrapWeights.from_any(weights)
    with pytest.raises(OptionError):
        option.verify(GraveyardKeeperWorld, "Player 1", PlandoOptions(0))


def test_weights_are_relative_and_do_not_need_to_sum_to_one_hundred():
    pools = []
    for bats, slimes in ((1, 3), (25, 75)):
        world = generate_worlds(ALL_DLCS | {
            "trap_percentage": 100, "trap_weights": {"Bats Trap": bats, "Green Slime Trap": slimes}})
        pools.append([item.name for item in world.itempool])
    assert pools[0] == pools[1]


def test_trap_placement_is_deterministic_and_player_specific():
    options = [ALL_DLCS | {"trap_percentage": 100}, ALL_DLCS | {"trap_percentage": 0}]
    first = generate_worlds(*options)
    second = generate_worlds(*options)
    assert [(item.player, item.name) for item in first.itempool] == [(item.player, item.name) for item in second.itempool]
    assert any(item.player == 1 and item.trap for item in first.itempool)
    assert not any(item.player == 2 and item.trap for item in first.itempool)


@pytest.mark.parametrize("goal", (0, 1))
def test_restrictive_fill_with_all_filler_replaced_by_traps(goal):
    multiworld = generate_worlds(ALL_DLCS | {"goal": goal, "trap_percentage": 100})
    distribute_items_restrictive(multiworld)
    assert not multiworld.get_unfilled_locations()
    assert multiworld.can_beat_game()
