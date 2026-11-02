from dataclasses import replace
from itertools import product
from unittest import TestCase
from unittest.mock import patch

from BaseClasses import CollectionState, ItemClassification
from ..data import CRAFTING_EVENT_PREFIX, data
from ..items import GraveyardKeeperItem
from ..logic.custom_rules import CanComplete
from ..logic.goal_rules import HasGraveyardRating
from ..logic.graveyard_calculator import GRAVEYARD_RATING, GraveyardPointCalculator
from .fakes import FakeState, FakeWorld


def graveyard_state(*buildings, events=(), extended=False):
    labels = [data.events[CRAFTING_EVENT_PREFIX + "BUILDABLE_" + key].item_label for key in buildings]
    labels.extend(data.events[key].item_label for key in events)
    if extended:
        labels.append(data.items[GRAVEYARD_RATING["extension_item"]].label)
    return FakeState(labels)


class TestGraveyardRating(TestCase):
    def score(self, *buildings, **kwargs):
        return GraveyardPointCalculator(graveyard_state(*buildings, **kwargs), FakeWorld()).calculate()

    def test_initial_empty_state_has_no_free_fence_or_statue(self):
        self.assertEqual(0, self.score())
        self.assertEqual(0, self.score(events=("EVENT_CHURCH_OPEN",)))
        self.assertEqual(0, self.score(events=("EVENT_BISHOP_REPORT_CATHEDRAL_UPGRADE",)))

    def test_western_patches_require_received_document_not_permission_reward(self):
        self.assertEqual(145, self.score("LAWN"))
        self.assertEqual(145, self.score("LAWN", events=("EVENT_INQUISITOR_GET_GRAVEYARD_EXPANSION_PERMISSION",)))
        self.assertEqual(322, self.score("LAWN", extended=True))

    def test_fences_require_big_church_and_stone_requires_wooden_upgrade(self):
        wooden = ("WOODEN_GRAVEYARD_FENCE",)
        both = (*wooden, "STONE_GRAVEYARD_FENCE")
        self.assertEqual(0, self.score(*both))
        self.assertEqual(0, self.score(*both, events=("EVENT_CHURCH_OPEN",)))
        events = ("EVENT_BISHOP_UPGRADE_TO_BIG_CHURCH",)
        self.assertEqual(10, self.score(*wooden, events=events))
        self.assertEqual(0, self.score("STONE_GRAVEYARD_FENCE", events=events))
        self.assertEqual(20, self.score(*both, events=events))

    def test_actual_statue_can_score_before_cathedral(self):
        self.assertEqual(5, self.score(events=("EVENT_BISHOP_BUILD_STATUE",)))
        self.assertEqual(25, self.score("WOODEN_GRAVEYARD_FENCE", "STONE_GRAVEYARD_FENCE",
                                       events=("EVENT_BISHOP_UPGRADE_TO_BIG_CHURCH", "EVENT_BISHOP_BUILD_STATUE")))

    def test_alternative_furnishings_do_not_stack_in_same_space(self):
        self.assertEqual(self.score("MARBLE_COLUMBARIUM"), self.score("STONE_COLUMBARIUM", "MARBLE_COLUMBARIUM"))
        self.assertEqual(self.score("LANTERN"), self.score("FLOWERBED", "LANTERN", "WOODEN_PRAYER_STATION"))

    def test_each_authored_quest_enforces_its_graveyard_requirement(self):
        cases = (
            ("EVENT_CHURCH_OPEN", (), ("FLOWERBED",)),
            ("EVENT_BISHOP_IMPROVE_GRAVEYARD", ("FLOWERBED",), ("LAWN",)),
            ("EVENT_BISHOP_IMPROVE_GRAVEYARD_FOR_CATHEDRAL", ("LAWN",), ("MARBLE_COLUMBARIUM",)),
        )
        for key, below, above in cases:
            with self.subTest(quest=key):
                quest = replace(data.events[key], required_quests=frozenset(), required_happiness=frozenset(),
                                required_quest_items=frozenset(), required_craft_items=frozenset())
                with patch.dict(data.events, {key: quest}):
                    rule = CanComplete(key).resolve(FakeWorld())
                self.assertFalse(rule(graveyard_state(*below)))
                self.assertTrue(rule(graveyard_state(*above)))

    def test_thresholds_are_inclusive_and_region_access_is_required(self):
        for threshold in (5, 30, 200):
            with self.subTest(threshold=threshold):
                rule = HasGraveyardRating(threshold).resolve(FakeWorld())
                state = FakeState()
                with patch.object(GraveyardPointCalculator, "calculate", return_value=threshold - 1):
                    self.assertFalse(rule(state))
                with patch.object(GraveyardPointCalculator, "calculate", return_value=threshold):
                    self.assertTrue(rule(state))
                    with patch.object(state, "can_reach_region", return_value=False):
                        self.assertFalse(rule(state))

    def test_first_five_points_do_not_require_church_or_its_rewards(self):
        rule = HasGraveyardRating(5).resolve(FakeWorld())
        state = graveyard_state("FLOWERBED")
        self.assertTrue(rule(state))
        self.assertFalse(state.has(data.events["EVENT_CHURCH_OPEN"].item_label, 1))
        self.assertFalse(state.has(data.items["ITEM_PERK_PREACHER"].label, 1))

    def test_new_state_inputs_are_declared_and_dlc_combinations_work(self):
        for crone, souls in product((False, True), repeat=2):
            with self.subTest(crone=crone, souls=souls):
                world = FakeWorld({"game_of_crone": crone, "better_save_soul": souls})
                dependencies = HasGraveyardRating(5).resolve(world).item_dependencies()
                self.assertIn(data.items[GRAVEYARD_RATING["extension_item"]].label, dependencies)
                for event in (*GRAVEYARD_RATING["church_events"].values(), GRAVEYARD_RATING["statue_event"]):
                    self.assertIn(data.events[event].item_label, dependencies)
                self.assertTrue(HasGraveyardRating(5).resolve(world)(graveyard_state("FLOWERBED")))

    def test_cache_updates_after_expansion_and_statue_collect_and_remove(self):
        from .test_progression import generate_worlds
        world = generate_worlds({}).worlds[1]
        state = CollectionState(world.multiworld)
        rule = HasGraveyardRating(200).resolve(world)
        world.register_rule_dependencies(rule)
        lawn = GraveyardKeeperItem(data.events[CRAFTING_EVENT_PREFIX + "BUILDABLE_LAWN"].item_label,
                                  ItemClassification.progression, None, 1)
        state.collect(lawn, prevent_sweep=True)
        scroll = world.create_item(data.items[GRAVEYARD_RATING["extension_item"]].label)
        with patch.object(state, "can_reach_region", return_value=True):
            self.assertFalse(rule(state))
            state.collect(scroll, prevent_sweep=True)
            self.assertTrue(rule(state))
            self.assertFalse(rule(CollectionState(world.multiworld)))
            state.remove(scroll)
            self.assertFalse(rule(state))

        statue_rule = HasGraveyardRating(5).resolve(world)
        world.register_rule_dependencies(statue_rule)
        empty = CollectionState(world.multiworld)
        statue = GraveyardKeeperItem(data.events[GRAVEYARD_RATING["statue_event"]].item_label,
                                    ItemClassification.progression, None, 1)
        with patch.object(empty, "can_reach_region", return_value=True):
            self.assertFalse(statue_rule(empty))
            empty.collect(statue, prevent_sweep=True)
            self.assertTrue(statue_rule(empty))
            empty.remove(statue)
            self.assertFalse(statue_rule(empty))

    def test_data_references_are_valid_and_all_patches_have_alternatives(self):
        groups = {"grave"}
        for key, scores in GRAVEYARD_RATING["decorations"].items():
            self.assertIn("BUILDABLE_" + key, data.recipes)
            groups.update(scores)
        self.assertEqual(18, len(GRAVEYARD_RATING["patches"]))
        for patch_data in GRAVEYARD_RATING["patches"].values():
            self.assertTrue(patch_data["configurations"])
            for alternative in patch_data["configurations"]:
                self.assertLessEqual(alternative.keys(), groups)
                self.assertTrue(all(count > 0 for count in alternative.values()))
