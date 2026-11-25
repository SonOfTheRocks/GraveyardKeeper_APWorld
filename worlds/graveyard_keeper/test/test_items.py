import unittest
from dataclasses import dataclass
from random import Random

from BaseClasses import ItemClassification

from ..items import _fit_item_pool_to_location_count


@dataclass
class FakeItem:
    name: str
    classification: ItemClassification


class FakeWorld:
    random = Random(0)

    @staticmethod
    def create_filler() -> FakeItem:
        return FakeItem("additional filler", ItemClassification.filler)


class TestFitItemPoolToLocationCount(unittest.TestCase):
    def test_adds_filler_when_there_are_more_locations_than_items(self):
        itempool = [FakeItem("progression", ItemClassification.progression)]

        balanced = _fit_item_pool_to_location_count(FakeWorld(), itempool, 3)

        self.assertEqual(3, len(balanced))
        self.assertEqual(2, sum(
            item.classification == ItemClassification.filler
            for item in balanced
        ))

    def test_removes_only_filler_when_there_are_more_items_than_locations(self):
        progression = FakeItem("progression", ItemClassification.progression)
        useful = FakeItem("useful", ItemClassification.useful)
        itempool = [
            progression,
            useful,
            *(FakeItem(f"filler {index}", ItemClassification.filler) for index in range(4)),
        ]

        balanced = _fit_item_pool_to_location_count(FakeWorld(), itempool, 4)

        self.assertEqual(4, len(balanced))
        self.assertIn(progression, balanced)
        self.assertIn(useful, balanced)

    def test_rejects_removing_progression_or_useful_items(self):
        itempool = [
            FakeItem("progression", ItemClassification.progression),
            FakeItem("useful", ItemClassification.useful),
        ]

        with self.assertRaisesRegex(ValueError, "only 0 filler items"):
            _fit_item_pool_to_location_count(FakeWorld(), itempool, 1)


if __name__ == "__main__":
    unittest.main()
