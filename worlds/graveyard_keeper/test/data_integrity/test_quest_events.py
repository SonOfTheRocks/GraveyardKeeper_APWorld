import re
import unittest

from BaseClasses import ItemClassification
from rule_builder.rules import Rule, Has
from test.param import classvar_matrix
from ..fakes import FakeWorld
from ..rule_evaluation import QuestRuleEvaluator
from ...data import data, load_json_data
from ...logic.custom_rules import CanComplete
from ...models import AreaPointData, DLCType, QuestEventData


class TestAllQuestEvents(unittest.TestCase):
    required_fields = {
        "location_label",
        "item_label",
        "dlc",
        "required_quests",
        "required_happiness",
        "required_quest_items",
        "required_craft_items",
        "rewards",
    }
    optional_fields = {"comment", "required_area_points"}
    list_fields = {
        "required_quests",
        "required_happiness",
        "required_quest_items",
        "required_craft_items",
        "required_area_points",
        "rewards",
    }

    def test_raw_quest_event_schema_is_complete_and_has_no_unknown_fields(self):
        raw_events = load_json_data("quest_events.json")
        for event_key, event in raw_events.items():
            with self.subTest(event=event_key):
                self.assertFalse(
                    self.required_fields - event.keys(),
                    f"missing fields: {sorted(self.required_fields - event.keys())}",
                )
                self.assertFalse(
                    event.keys() - self.required_fields - self.optional_fields,
                    f"unknown fields: {sorted(event.keys() - self.required_fields - self.optional_fields)}",
                )
                self.assertIsInstance(event["location_label"], str)
                self.assertIsInstance(event["item_label"], str)
                self.assertIn(event["dlc"], DLCType.__members__)

                for field_name in self.list_fields & event.keys():
                    values = event[field_name]
                    self.assertIsInstance(values, list, f"{field_name} must be a list")
                    self.assertTrue(
                        all(isinstance(value, str) and value for value in values),
                        f"{field_name} must contain only non-empty strings",
                    )
                    self.assertEqual(
                        len(values),
                        len(set(values)),
                        f"{field_name} must not contain duplicates",
                    )

    def test_every_quest_event_belongs_to_exactly_one_region(self):
        containing_regions = {
            event_key: [
                region_key
                for region_key, region in data.regions.items()
                if event_key in region.events
            ]
            for event_key, event in data.events.items()
            if isinstance(event, QuestEventData)
        }
        invalid = {
            event_key: regions
            for event_key, regions in containing_regions.items()
            if len(regions) != 1
        }
        self.assertFalse(invalid, f"Quest events must belong to exactly one region: {invalid}")

    def test_reward_location_keys_follow_reward_naming_convention(self):
        invalid = {
            event_key: sorted(event.rewards)
            for event_key, event in data.events.items()
            if isinstance(event, QuestEventData)
            and any("REWARD" not in reward for reward in event.rewards)
        }
        self.assertFalse(invalid, f"Reward location keys must contain 'REWARD': {invalid}")

    def test_snake_sacrifice_zone_requirement_is_loaded(self):
        event = data.events["EVENT_SNAKE_SHOW_PREPARED_RITUAL_SITE"]
        self.assertEqual(
            list(event.required_area_points),
            [AreaPointData("SACRIFICE_ZONE", 20)],
        )

    def test_area_point_requirement_parser_rejects_invalid_values(self):
        for invalid_value in ("SACRIFICE_ZONE", "_20", "SACRIFICE_ZONE_0", "SACRIFICE_ZONE_-1"):
            with self.subTest(value=invalid_value):
                with self.assertRaises(ValueError):
                    AreaPointData.from_string(invalid_value)

    def test_todo_quest_requirements_name_an_undefined_event(self):
        for event_key, event in data.events.items():
            if not isinstance(event, QuestEventData):
                continue
            for requirement in event.required_quests:
                if not requirement.startswith("TODO"):
                    continue
                with self.subTest(event=event_key, requirement=requirement):
                    match = re.fullmatch(r"TODO\((EVENT_[A-Z0-9_]+)\)", requirement)
                    self.assertIsNotNone(
                        match,
                        "TODO quest requirements must use TODO(EVENT_NAME) so the missing event is explicit",
                    )
                    self.assertNotIn(
                        match.group(1),
                        data.events,
                        "Replace the TODO requirement with the real event key once that event is defined",
                    )

    def test_all_quests_are_completable_with_all_items(self):
        evaluator = QuestRuleEvaluator()
        evaluations = evaluator.evaluate_all()
        root_failures = evaluator.failure_frontier(evaluations)

        diagnostics = "\n\n".join(
            evaluation.format_failed_tree()
            for evaluation in root_failures.values()
        )
        self.assertFalse(
            bool(root_failures),
            "Quest progression has root failures. Quests depending on these failures "
            f"are omitted:\n{diagnostics}",
        )


@classvar_matrix(
    event_key=[
        event_key
        for event_key, event in data.events.items()
        if isinstance(event, QuestEventData)
    ]
)
class TestEvent(unittest.TestCase):
    event_key: str

    def test_quest_is_in_regions(self):
        regions = [
            region_key
            for region_key, region in data.regions.items()
            if self.event_key in region.events
        ]
        self.assertEqual(
            len(regions),
            1,
            f"\nquest must exist in exactly one region, found {regions}",
        )

    def test_required_quests_exist(self):
        event_data = data.events[self.event_key]
        quests = event_data.required_quests
        for quest in quests:
            if not quest.startswith("TODO"): # left-over TODOs are tested in TestAllQuestEvents
                self.assertIn(quest, data.events.keys(), f"\nprerequisite quest '{quest}' is not defined")

    def test_required_happiness_npc_exist(self):
        event_data = data.events[self.event_key]
        happiness_req = event_data.required_happiness
        npcs_with_happiness = [re.match(r"ITEM_(\w+)_HAPPINESS_(\d+)", i).group(1) for i in data.items.keys() if "HAPPINESS" in i]
        for happiness in happiness_req:
            self.assertTrue(happiness.npc in npcs_with_happiness, f"\nprerequisite happiness NPC '{happiness.npc}' is not defined")


    def test_required_happiness_is_valid_value(self):
        event_data = data.events[self.event_key]
        happiness_req = event_data.required_happiness
        for happiness in happiness_req:
            self.assertTrue(0 <= happiness.value <= 100, f"\nprerequisite happiness value should be between 0 and 100")

    def test_required_happiness_item_is_progression(self):
        event_data = data.events[self.event_key]
        for happiness in event_data.required_happiness:
            item_key = f"ITEM_{happiness.npc}_HAPPINESS_10"
            self.assertEqual(
                data.items[item_key].classification,
                ItemClassification.progression,
                f"\n{item_key} is required by quest logic and must be a progression item",
            )

    def test_required_quest_items_exist(self):
        event_data = data.events[self.event_key]
        quest_items = event_data.required_quest_items
        for quest_item in quest_items:
            self.assertIn(quest_item, data.items.keys(), f"\nprerequisite quest item '{quest_item}' is not defined")

    def test_required_craft_items_exist(self):
        event_data = data.events[self.event_key]
        craft_items = event_data.required_craft_items
        all_sold = [i for vendor in data.vendors.values() for i in vendor.sells_all]
        for craft_item in craft_items:
            if craft_item not in all_sold and craft_item not in data.items.keys():
                self.assertIn(craft_item, data.recipes.keys(), f"\nprerequisite craft item '{craft_item}' has no recipe and isn't sold by any vendor")

    def test_required_area_points_are_valid(self):
        event_data = data.events[self.event_key]
        for requirement in event_data.required_area_points:
            self.assertGreater(requirement.value, 0, "\nrequired area points must be positive")
            self.assertIn(
                f"REGION_{requirement.area}",
                data.regions,
                f"\narea point requirement '{requirement.area}' has no matching region",
            )

    def test_reward_locations_exist(self):
        event_data: QuestEventData = data.events[self.event_key]
        reward_locations = event_data.rewards
        for location in reward_locations:
            self.assertIn(location, data.locations.keys(), f"\nreward location '{location}' is not defined")

    def test_item_dependencies_exist(self):
        resolved_rule: Rule.Resolved = CanComplete(self.event_key).resolve(FakeWorld())
        item_dependencies = resolved_rule.item_dependencies()
        item_labels = [i.label for i in data.items.values()]
        item_labels.extend(event.item_label for event in data.events.values())
        unexpected_dependencies = [d for d in item_dependencies if d not in item_labels]
        self.assertFalse(unexpected_dependencies, f"\nnon-valid item requirements: {unexpected_dependencies}")

    def test_region_dependencies_exist(self):
        resolved_rule: Rule.Resolved = CanComplete(self.event_key).resolve(FakeWorld())
        region_dependencies = resolved_rule.region_dependencies()
        region_labels = [i.label for i in data.regions.values()]
        unexpected_dependencies = [d for d in region_dependencies if d not in region_labels]
        self.assertFalse(unexpected_dependencies, f"\nnon-valid region requirements: {unexpected_dependencies}")

    def test_location_dependencies_exist(self):
        resolved_rule: Rule.Resolved = CanComplete(self.event_key).resolve(FakeWorld())
        location_dependencies = resolved_rule.location_dependencies()
        location_labels = [l.label for l in data.locations.values()]
        unexpected_dependencies = [d for d in location_dependencies if d not in location_labels]
        self.assertFalse(unexpected_dependencies, f"\nnon-valid location requirements: {unexpected_dependencies}")

    def test_entrance_dependencies_exist(self):
        resolved_rule: Rule.Resolved = CanComplete(self.event_key).resolve(FakeWorld())
        entrance_dependencies = resolved_rule.entrance_dependencies()
        self.assertFalse(entrance_dependencies, f"\nno entrance dependencies expected, but found: {entrance_dependencies}")
