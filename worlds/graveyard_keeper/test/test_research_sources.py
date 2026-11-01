from BaseClasses import CollectionState
from unittest.mock import patch

from .bases import GraveyardKeeperTestBase
from .fakes import FakeWorld
from .rule_evaluation import make_all_items_state
from ..data import data, load_json_data, active_research_locations
from ..logic.custom_rules import CanComplete


class TestResearchSources(GraveyardKeeperTestBase):
    run_default_tests = False
    options = {'stranger_sins': True, 'game_of_crone': True, 'better_save_soul': True}

    def test_only_active_checks_are_generated_and_pool_still_fits(self):
        locations = [location for location in self.multiworld.get_locations(self.player)
                     if location.address is not None]
        names = {location.name for location in locations}
        self.assertEqual(773, len(locations))
        self.assertEqual(len(locations), len(self.multiworld.itempool))
        for technology in load_json_data('technologies.json').values():
            expected = set(technology['locations']) & active_research_locations()
            self.assertEqual(expected, set(technology['locations']) & names)
        self.assertEqual(28, sum('recipe_item' in value for value in load_json_data('technologies.json').values()))

    def test_public_location_definitions_match_the_actual_checks(self):
        generated = {location.name for location in self.multiworld.get_locations(self.player)
                     if location.address is not None}
        self.assertEqual(generated, set(self.world.location_name_to_id))
        for location in self.multiworld.get_locations(self.player):
            if location.address is not None:
                self.assertEqual(self.world.location_name_to_id[location.name], location.address)
        for technology in load_json_data('technologies.json').values():
            if 'recipe_item' in technology:
                for index in (2, 3):
                    removed = technology['locations'][0].replace(' - Unlock 1', f' - Unlock {index}')
                    self.assertNotIn(removed, self.world.location_name_to_id)
                    self.assertNotIn(removed, {location.label for location in data.locations.values()})
            elif 'quest_reward' in technology:
                label = data.regions[technology['region']].label
                for index in (1, 2, 3):
                    self.assertNotIn(f'{label} - Unlock {index}', self.world.location_name_to_id)

    def test_quest_roots_and_descendants_require_the_native_quest_source(self):
        technologies = load_json_data('technologies.json')
        for root, descendant in [('First slice', 'Hardspares'), ('Iron', 'Steel')]:
            with self.subTest(root=root):
                state = CollectionState(self.multiworld)
                region = data.regions[technologies[descendant]['region']].label
                self.assertFalse(state.can_reach(region, 'Region', self.player))
                source = technologies[root]['quest_reward']
                reward_key = next(key for key, value in data.locations.items() if value.label == source)
                event = next(value for value in data.events.values()
                             if reward_key in getattr(value, 'rewards', ()))
                state.collect(self.world.get_location(event.location_label).item)
                self.assertTrue(state.can_reach(region, 'Region', self.player))

    def test_recipe_books_are_not_gated_by_obsolete_group_items(self):
        state = CollectionState(self.multiworld)
        self.assertTrue(state.can_reach('Simple and Tasty - Unlock 1', 'Location', self.player))
        self.assertFalse(any(item.name.startswith('Unlock: ') for item in self.multiworld.itempool))

    def test_human_soul_healing_requires_native_research_access(self):
        technology = load_json_data('technologies.json')['soul_sins_2']
        region = data.regions[technology['region']].label
        # Use the uncached rule adapter so a previous full-state reachability sweep
        # cannot mask the intentionally unavailable research region in this case.
        state = make_all_items_state()
        rule = CanComplete('EVENT_SMILER_UNLOCK_HUMAN_SOUL_HEALING').resolve(FakeWorld())
        with patch.object(state, 'can_reach_region', side_effect=lambda name, player: name != region):
            self.assertFalse(rule(state))
        with patch.object(state, 'can_reach_region', return_value=True):
            self.assertTrue(rule(state))
