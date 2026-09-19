import unittest

from test.param import classvar_matrix
from ...data import data


class TestAllRegions(unittest.TestCase):

    def nothing(self):
        pass

    #def test_no_quest_events_require_todo(self):
    #    todo_quest_events = [e for e in data.events if any(
    #        req in data.events.keys() for req in data.events[e].required_quests
    #    )]
    #    self.assertEqual(len(todo_quest_events), 0,
    #                     f"No quest event should require 'TODO', but these do: {todo_quest_events}")


@classvar_matrix(region_key=data.regions.keys())
class TestRegion(unittest.TestCase):
    region_key: str

    def test_region_locations_exist(self):
        region_data = data.regions[self.region_key]
        for location in region_data.locations:
            self.assertTrue(location in data.locations.keys(),
                            f"specified location '{location}' is not defined")

    def test_region_locations_double_linking(self):
        region_data = data.regions[self.region_key]
        for location in region_data.locations:
            location_data = data.locations[location]
            self.assertTrue(self.region_key == location_data.parent_region,
                            f"location '{location}' should have parent region '{self.region_key}'")

    def test_region_connections_exist(self):
        region_data = data.regions[self.region_key]
        for region in region_data.connections:
            self.assertTrue(region in data.regions.keys(),
                            f"specified connection '{region}' is not defined")

    def test_region_double_linking(self):
        region_data = data.regions[self.region_key]
        for connecting_region_key in region_data.connections:
            connecting_region_data = data.regions[connecting_region_key]
            self.assertTrue(self.region_key in connecting_region_data.connections,
                            f"connection to '{connecting_region_key}' is defined, but the reverse is not")

    def test_region_events_exist(self):
        region_data = data.regions[self.region_key]
        for event in region_data.events:
            self.assertTrue(event in data.events.keys(),
                            f"specified event '{event}' is not defined")
