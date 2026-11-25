"""The generated world must satisfy core reachability checks, including internal events."""
from itertools import product
from unittest.mock import patch

import pytest

from .test_progression import ALL_DLCS, generate_worlds
from .fakes import FakeWorld
from ..data import data
from ..logic.acquisition import get_option_acquirable_item_keys
from ..logic.custom_rules import CanGet
from ..logic.dependencies import optional_dependency_names
from ..models import SimpleRecipeData
from rule_builder.rules import And, Has


def assert_everything_reachable(multiworld):
    state = multiworld.get_all_state()
    assert multiworld.has_beaten_game(state)
    assert not [location.name for location in multiworld.get_locations() if not location.can_reach(state)]
    assert not [region.name for region in multiworld.get_regions() if not region.can_reach(state)]


def test_actual_default_options_have_no_impossible_internal_locations():
    assert_everything_reachable(generate_worlds({}))


@pytest.mark.parametrize("dlcs", list(product((False, True), repeat=3)))
@pytest.mark.parametrize("vendor_logic", (0, 1, 2))
@pytest.mark.parametrize("goal", (0, 1))
def test_all_generated_events_and_regions_are_reachable(dlcs, vendor_logic, goal):
    options = dict(zip(ALL_DLCS, dlcs)) | dict(vendor_logic=vendor_logic, goal=goal)
    assert_everything_reachable(generate_worlds(options))


@pytest.mark.parametrize("has_source", (False, True))
@pytest.mark.parametrize("enabled", (False, True))
def test_acquisition_cycle_needs_an_enabled_external_source(has_source, enabled):
    recipes = {
        "TEST_A": [SimpleRecipeData("TEST_A", 0, frozenset(), None, frozenset({"TEST_B"}), frozenset())],
        "TEST_B": [SimpleRecipeData("TEST_B", 0, frozenset(), None, frozenset({"TEST_A"}), frozenset())],
    }
    if has_source:
        recipes["TEST_B"].append(SimpleRecipeData(
            "TEST_B", 1, frozenset(), "ITEM_BP_ORGAN_WORKBENCH", frozenset(), frozenset()))
    world = FakeWorld({"better_save_soul": enabled})
    with patch.object(data, "recipes", recipes), patch.object(data, "vendors", {}), \
            patch("worlds.graveyard_keeper.logic.acquisition.get_vendor_item_keys", return_value=frozenset()):
        available = get_option_acquirable_item_keys(world)
    assert ("TEST_A" in available) == (has_source and enabled)
    assert ("TEST_B" in available) == (has_source and enabled)


def test_excluded_calculator_input_does_not_erase_other_dependencies():
    world = FakeWorld()
    world.acquirable_item_keys = frozenset()
    declaration = And(CanGet("CRAFTING_STATION_ORGAN_WORKBENCH"), Has("Other rating input"))
    assert optional_dependency_names(declaration, world) == ("Other rating input",)


def test_unknown_crafting_reference_still_raises_instead_of_becoming_false():
    world = FakeWorld()
    world.acquirable_item_keys = frozenset()
    with pytest.raises(ValueError, match="Unknown item or event key"):
        CanGet("EVENT_CAN_GET_MISSING_TEST_ITEM").resolve(world)
