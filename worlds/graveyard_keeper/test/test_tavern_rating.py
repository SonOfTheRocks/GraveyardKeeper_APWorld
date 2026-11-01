from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from BaseClasses import CollectionState, ItemClassification
from ..data import CRAFTING_EVENT_PREFIX, data
from ..items import GraveyardKeeperItem
from ..logic.custom_rules import CanComplete, CanCraftRecipe
from ..logic.tavern_calculator import TAVERN_RATING, HasTavernRating, TavernPointCalculator
from ..models import AreaPointData
from .fakes import FakeState, FakeWorld


def tavern_state(*furniture, events=(), artifacts=(), opened=True, upgraded=False):
    labels = [data.events[CRAFTING_EVENT_PREFIX + key].item_label for key in furniture]
    labels.extend(data.events[key].item_label for key in events)
    labels.extend(data.items[key].label for key in artifacts)
    if opened:
        labels.append(data.events[TAVERN_RATING["open_event"]].item_label)
    if upgraded:
        labels.append(data.events[TAVERN_RATING["upgrade_event"]].item_label)
    return FakeState(labels)


TABLE_UNLOCK = "EVENT_KOUKOL_RETURN_WITH_DARK_ORGAN"
RAT_UNLOCK = "EVENT_SNAKE_PERSUADE_TO_STEAL_ANCIENT_AMULET"


class TestTavernRating(TestCase):
    def score(self, *furniture, **kwargs):
        return TavernPointCalculator(tavern_state(*furniture, **kwargs), 1).calculate()

    def test_closed_tavern_has_no_quality(self):
        self.assertEqual(0, self.score(*TAVERN_RATING["furniture"], events=(TABLE_UNLOCK, RAT_UNLOCK),
                                       opened=False, upgraded=True))
        self.assertEqual(0, self.score())

    def test_upgrade_adds_fireplace_and_fixed_barrel_once(self):
        self.assertEqual(8, self.score(upgraded=True))
        self.assertEqual(14, self.score("BUILDABLE_TAVERN_BARREL", upgraded=True))
        self.assertEqual(0, self.score("BUILDABLE_TAVERN_BARREL"))

    def test_two_table_spaces_become_four_after_upgrade(self):
        self.assertEqual(10, self.score("BUILDABLE_TAVERN_TABLE_1"))
        self.assertEqual(28, self.score("BUILDABLE_TAVERN_TABLE_1", upgraded=True))

    def test_table_two_needs_koukols_unlock_and_replaces_table_one(self):
        self.assertEqual(0, self.score("BUILDABLE_TAVERN_TABLE_2"))
        self.assertEqual(20, self.score("BUILDABLE_TAVERN_TABLE_2", events=(TABLE_UNLOCK,)))
        self.assertEqual(20, self.score("BUILDABLE_TAVERN_TABLE_1", "BUILDABLE_TAVERN_TABLE_2",
                                       events=(TABLE_UNLOCK,)))
        self.assertEqual(48, self.score("BUILDABLE_TAVERN_TABLE_2", events=(TABLE_UNLOCK,), upgraded=True))

    def test_rat_race_table_needs_snakes_unlock(self):
        self.assertEqual(0, self.score("BUILDABLE_RAT_RACE_TABLE"))
        self.assertEqual(5, self.score("BUILDABLE_RAT_RACE_TABLE", events=(RAT_UNLOCK,)))

    def test_artifact_bonus_needs_shelves_item_and_vision(self):
        event = "EVENT_TAVERN_USE_STATUETTE_IN_TIME_MACHINE"
        item = "ITEM_STATUETTE"
        self.assertEqual(0, self.score(events=(event,), artifacts=(item,)))
        self.assertEqual(5, self.score("BUILDABLE_TAVERN_ARTIFACTS_SHELVES", events=(event,)))
        self.assertEqual(5, self.score("BUILDABLE_TAVERN_ARTIFACTS_SHELVES", artifacts=(item,)))
        self.assertEqual(6, self.score("BUILDABLE_TAVERN_ARTIFACTS_SHELVES", events=(event,), artifacts=(item,)))

    def test_seventeen_distinct_artifacts_count_once_each(self):
        events = tuple(TAVERN_RATING["artifacts"])
        artifacts = tuple(entry["item"] for entry in TAVERN_RATING["artifacts"].values())
        state = tavern_state("BUILDABLE_TAVERN_ARTIFACTS_SHELVES", events=events, artifacts=artifacts)
        self.assertEqual(22, TavernPointCalculator(state, 1).calculate())
        for item in artifacts:
            state.counts[data.items[item].label] = 5
        self.assertEqual(22, TavernPointCalculator(state, 1).calculate())

    def test_full_quality_is_eighty_one(self):
        self.assertEqual(64, self.score(*TAVERN_RATING["furniture"], events=(TABLE_UNLOCK, RAT_UNLOCK), upgraded=True))
        self.assertEqual(81, self.score(*TAVERN_RATING["furniture"],
                                       events=(TABLE_UNLOCK, RAT_UNLOCK, *TAVERN_RATING["artifacts"]),
                                       artifacts=tuple(entry["item"] for entry in TAVERN_RATING["artifacts"].values()),
                                       upgraded=True))

    def test_threshold_is_inclusive_and_access_is_required(self):
        state = tavern_state("BUILDABLE_TAVERN_TABLE_2", events=(TABLE_UNLOCK,), upgraded=True)
        world = FakeWorld()
        self.assertTrue(HasTavernRating(48).resolve(world)(state))
        self.assertFalse(HasTavernRating(49).resolve(world)(state))
        with patch.object(state, "can_reach_region", return_value=False):
            self.assertFalse(HasTavernRating(1).resolve(world)(state))
        self.assertFalse(HasTavernRating(0).resolve(world)(tavern_state(opened=False)))

    def test_disabled_stranger_sins_returns_false_without_dlc_dependencies(self):
        rule = HasTavernRating(0).resolve(FakeWorld({"stranger_sins": False}))
        self.assertFalse(rule(FakeState()))
        self.assertEqual({}, rule.item_dependencies())
        self.assertFalse(rule.region_dependencies())

    def test_area_point_dispatch_checks_the_requested_tavern_threshold(self):
        key = "EVENT_KOUKOL_APPROVE_TAVERN_UPGRADE"
        quest = replace(data.events[key], required_quests=frozenset(), required_craft_items=frozenset(),
                        required_area_points=frozenset({AreaPointData("TAVERN", 40)}))
        with patch.dict(data.events, {key: quest}):
            rule = CanComplete(key).resolve(FakeWorld())
        self.assertFalse(rule(tavern_state("BUILDABLE_TAVERN_TABLE_1", upgraded=True)))
        self.assertTrue(rule(tavern_state("BUILDABLE_TAVERN_TABLE_2", events=(TABLE_UNLOCK,), upgraded=True)))

    def test_koukol_requires_table_two_even_when_quality_exceeds_forty(self):
        key = "EVENT_KOUKOL_APPROVE_TAVERN_UPGRADE"
        quest = replace(data.events[key], required_quests=frozenset())
        with patch.dict(data.events, {key: quest}):
            rule = CanComplete(key).resolve(FakeWorld())
        # One Table II suffices, even in the original two-table tavern.
        low = tavern_state("BUILDABLE_TAVERN_TABLE_2", events=(TABLE_UNLOCK,))
        self.assertLess(TavernPointCalculator(low, 1).calculate(), 40)
        self.assertTrue(rule(low))
        high = tavern_state("BUILDABLE_TAVERN_TABLE_1", "BUILDABLE_TAVERN_BARREL",
                            "BUILDABLE_TAVERN_ARTIFACTS_SHELVES", "BUILDABLE_RAT_RACE_TABLE",
                            events=(RAT_UNLOCK, *TAVERN_RATING["artifacts"]),
                            artifacts=tuple(entry["item"] for entry in TAVERN_RATING["artifacts"].values()),
                            upgraded=True)
        self.assertGreater(TavernPointCalculator(high, 1).calculate(), 40)
        self.assertFalse(rule(high))

    def test_adam_requires_forty_without_later_story_unlocks(self):
        key = "EVENT_ADAM_EXPLAIN_GHOSTLY_POTTERY"
        self.assertEqual(frozenset({AreaPointData("TAVERN", 40)}),
                         frozenset(data.events[key].required_area_points))
        quest = replace(data.events[key], required_quests=frozenset())
        with patch.dict(data.events, {key: quest}):
            rule = CanComplete(key).resolve(FakeWorld())
        furniture = ("BUILDABLE_TAVERN_TABLE_1", "BUILDABLE_TAVERN_BARREL", "BUILDABLE_TAVERN_ARTIFACTS_SHELVES")
        below = tavern_state(*furniture, upgraded=True)
        exactly = tavern_state(*furniture, upgraded=True,
                               events=("EVENT_TAVERN_USE_STATUETTE_IN_TIME_MACHINE",),
                               artifacts=("ITEM_STATUETTE",))
        self.assertEqual(39, TavernPointCalculator(below, 1).calculate())
        self.assertEqual(40, TavernPointCalculator(exactly, 1).calculate())
        self.assertFalse(rule(below))
        self.assertTrue(rule(exactly))

    def test_furniture_requires_each_native_material(self):
        for key in TAVERN_RATING["furniture"]:
            with self.subTest(furniture=key):
                recipe, = data.recipes[key]
                self.assertEqual(frozenset({"REGION_TAVERN"}), recipe.regions)
                rule = CanCraftRecipe(recipe).resolve(FakeWorld())
                labels = [data.events[CRAFTING_EVENT_PREFIX + item].item_label for item in recipe.ingredients]
                self.assertTrue(rule(FakeState(labels)))
                for missing in labels:
                    self.assertFalse(rule(FakeState([label for label in labels if label != missing])))

    def test_every_observed_input_is_declared(self):
        dependencies = HasTavernRating(40).resolve(FakeWorld()).item_dependencies()
        for key in TAVERN_RATING["furniture"]:
            self.assertIn(data.events[CRAFTING_EVENT_PREFIX + key].item_label, dependencies)
        for key in (TAVERN_RATING["open_event"], TAVERN_RATING["upgrade_event"], TABLE_UNLOCK, RAT_UNLOCK,
                    *TAVERN_RATING["artifacts"]):
            self.assertIn(data.events[key].item_label, dependencies)
        for artifact in TAVERN_RATING["artifacts"].values():
            self.assertIn(data.items[artifact["item"]].label, dependencies)

    def test_cached_quality_updates_when_inputs_are_collected_and_removed(self):
        from .test_progression import generate_worlds
        multiworld = generate_worlds({"stranger_sins": True})
        world = multiworld.worlds[1]
        rule = HasTavernRating(40).resolve(world)
        world.register_rule_dependencies(rule)
        state = CollectionState(multiworld)

        def event_item(key):
            return GraveyardKeeperItem(data.events[key].item_label, ItemClassification.progression, None, 1)

        for key in (TAVERN_RATING["open_event"], TABLE_UNLOCK,
                    CRAFTING_EVENT_PREFIX + "BUILDABLE_TAVERN_TABLE_2"):
            state.collect(event_item(key), prevent_sweep=True)
        upgrade = event_item(TAVERN_RATING["upgrade_event"])
        with patch.object(state, "can_reach_region", return_value=True):
            self.assertFalse(rule(state))
            state.collect(upgrade, prevent_sweep=True)
            self.assertTrue(rule(state))
            self.assertFalse(rule(CollectionState(multiworld)))
            state.remove(upgrade)
            self.assertFalse(rule(state))

    def test_artifact_vision_and_item_mapping_agrees_with_quest_data(self):
        self.assertEqual(17, len(TAVERN_RATING["artifacts"]))
        self.assertEqual(17, len({entry["item"] for entry in TAVERN_RATING["artifacts"].values()}))
        for event, artifact in TAVERN_RATING["artifacts"].items():
            self.assertIn(artifact["item"], data.events[event].required_quest_items)
