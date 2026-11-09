import unittest

from test.param import classvar_matrix
from ...data import data


@classvar_matrix(location_key=data.locations.keys())
class TestLocationParent(unittest.TestCase):
    location_key: str

    def test_parent_contains_location(self):
        loc_data = data.locations[self.location_key]
        parent_region_key = loc_data.parent_region
        parent_region = data.regions[parent_region_key]

        self.assertIn(
            self.location_key,
            parent_region.locations,
            f"\nLocation '{loc_data.label}' ({self.location_key}) declares "
            f"'{parent_region_key}' as its parent region, but the location "
            f"is not listed in that region."
        )
