"""Graveyard goal settings and validation at the pre-fill generation boundary."""

from itertools import product
import json
from pathlib import Path

import pytest

from Options import OptionError
from ..logic.graveyard_calculator import GraveyardPointCalculator
from .test_progression import ALL_DLCS, generate_worlds


DLC_COMBINATIONS = list(product((False, True), repeat=3))


def test_graveyard_goal_serializes_the_exact_required_rating():
    world = generate_worlds(ALL_DLCS | {"goal": 1, "graveyard_goal_rating": 700}).worlds[1]
    slot_data = world.fill_slot_data()
    assert slot_data["goal"] == 1
    assert type(slot_data["graveyard_goal_rating"]) is int
    assert slot_data["graveyard_goal_rating"] == 700


@pytest.mark.parametrize("dlcs", DLC_COMBINATIONS)
def test_graveyard_goal_accepts_its_reachable_boundary_and_rejects_the_next_point(dlcs):
    options = dict(zip(ALL_DLCS, dlcs)) | {"goal": 1}
    probe = generate_worlds(options).worlds[1]
    maximum = GraveyardPointCalculator(probe.multiworld.get_all_state(), probe).calculate()
    assert 500 <= maximum < 2484

    reachable = generate_worlds(options | {"graveyard_goal_rating": maximum}).worlds[1]
    reachable.generate_basic()
    assert reachable.multiworld.completion_condition[1](reachable.multiworld.get_all_state())

    unreachable = generate_worlds(options | {"graveyard_goal_rating": maximum + 1}).worlds[1]
    with pytest.raises(OptionError, match=rf"graveyard_goal_rating.*{maximum + 1}.*{maximum}"):
        unreachable.generate_basic()


@pytest.mark.parametrize("dlcs", DLC_COMBINATIONS)
def test_zero_graveyard_goal_is_valid_without_goal_progression(dlcs):
    world = generate_worlds(dict(zip(ALL_DLCS, dlcs)) | {
        "goal": 1, "graveyard_goal_rating": 0,
    }).worlds[1]
    world.generate_basic()
    assert world.fill_slot_data()["graveyard_goal_rating"] == 0


@pytest.mark.parametrize("dlcs", DLC_COMBINATIONS)
def test_portal_goal_ignores_an_unreachable_graveyard_target(dlcs):
    world = generate_worlds(dict(zip(ALL_DLCS, dlcs)) | {
        "goal": 0, "graveyard_goal_rating": 2484,
    }).worlds[1]
    world.generate_basic()
    assert world.multiworld.completion_condition[1](world.multiworld.get_all_state())


def test_metadata_requires_the_verified_archipelago_core():
    metadata = json.loads((Path(__file__).parents[1] / "archipelago.json").read_text())
    assert metadata["minimum_ap_version"] == "0.6.9"
