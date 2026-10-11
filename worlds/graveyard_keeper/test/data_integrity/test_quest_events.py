import re
import unittest
from itertools import product

from BaseClasses import ItemClassification
from rule_builder.rules import Rule, Has
from test.param import classvar_matrix
from ..fakes import FakeWorld
from ..rule_evaluation import QuestRuleEvaluator
from ...data import data, load_json_data
from ...logic.custom_rules import CanComplete
from ...models import AreaPointData, CraftingGroup, DLCType, HappinessData, QualityRecipeData, QuestEventData


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

    def test_snake_dark_heart_includes_all_linear_final_ritual_rewards(self):
        event = data.events["EVENT_SNAKE_GIVE_DARK_HEART"]
        expected_rewards = {
            "LOCATION_SNAKE_REWARD_GIVE_DARK_HEART",
            "LOCATION_SNAKE_REWARD_COMPLETE_FINAL_RITUAL_1",
            "LOCATION_SNAKE_REWARD_COMPLETE_FINAL_RITUAL_2",
            "LOCATION_SNAKE_REWARD_COMPLETE_FINAL_RITUAL_3",
        }

        self.assertEqual(["ITEM_DARK_HEART"], list(event.required_craft_items))
        self.assertEqual(expected_rewards, set(event.rewards))
        sacrifice_zone = data.regions["REGION_SACRIFICE_ZONE"]
        for reward in expected_rewards:
            with self.subTest(reward=reward):
                self.assertIn(reward, sacrifice_zone.locations)
                self.assertEqual("REGION_SACRIFICE_ZONE", data.locations[reward].parent_region)

        node_names = load_json_data("quest_node_names.json")
        for node_id in ("final_ritual:247", "final_ritual:264", "final_ritual:340"):
            with self.subTest(node_id=node_id):
                self.assertEqual("Complete Snake's final ritual", node_names[node_id])

    def test_meeting_snake_is_a_rewardless_region_gated_start_event(self):
        event = data.events["EVENT_SNAKE_MEET"]
        self.assertEqual([], list(event.required_quests))
        self.assertEqual([], list(event.rewards))
        self.assertIn("EVENT_SNAKE_MEET", data.regions["REGION_UNDERGROUND_TUNNEL"].events)

    def test_mill_fix_conversation_chain_matches_phrase_unlocks(self):
        farmer_event = data.events["EVENT_FARMER_ASK_ABOUT_ALISA"]
        miller_event = data.events["EVENT_MILLER_ASK_TO_FIX_MILL"]
        astrologer_event = data.events["EVENT_ASTROLOGER_ASK_ABOUT_MILL_FIX"]

        self.assertEqual(["EVENT_MS_CHARM_GIVE_GOLD_STORY"], list(farmer_event.required_quests))
        self.assertEqual(["EVENT_FARMER_ASK_ABOUT_ALISA"], list(miller_event.required_quests))
        self.assertEqual(["EVENT_MILLER_ASK_TO_FIX_MILL"], list(astrologer_event.required_quests))
        self.assertEqual([], list(farmer_event.rewards))
        self.assertEqual([], list(miller_event.rewards))

    def test_lighthouse_keeper_necronomicon_turn_in_bridges_astrologer_and_snake(self):
        event = data.events["EVENT_LIGHTHOUSE_KEEPER_GET_NECRONOMICON"]

        self.assertEqual(
            ["EVENT_ASTROLOGER_ASK_ABOUT_NECRONOMICON"],
            list(event.required_quests),
        )
        self.assertEqual(["ITEM_MAGGOT"], list(event.required_craft_items))
        self.assertEqual(
            ["LOCATION_LIGHTHOUSE_KEEPER_REWARD_GET_NECRONOMICON"],
            list(event.rewards),
        )
        self.assertIn("EVENT_LIGHTHOUSE_KEEPER_GET_NECRONOMICON", data.regions["REGION_LIGHTHOUSE"].events)
        self.assertIn(event.rewards[0], data.regions["REGION_LIGHTHOUSE"].locations)
        self.assertEqual("REGION_LIGHTHOUSE", data.locations[event.rewards[0]].parent_region)

        node_names = load_json_data("quest_node_names.json")
        self.assertEqual(
            "Ask the Lighthouse Keeper about the Necronomicon",
            node_names["npc_light_keeper:13:option:0"],
        )
        self.assertEqual(event.location_label, node_names["npc_light_keeper:13:option:1"])

    def test_lighthouse_keeper_fishing_rod_trade_matches_flow_requirements(self):
        event = data.events["EVENT_LIGHTHOUSE_KEEPER_TRADE_MOTHS_FOR_FISHING_ROD"]

        self.assertEqual([], list(event.required_quests))
        self.assertEqual([], list(event.required_quest_items))
        self.assertEqual(["ITEM_MOTH"], list(event.required_craft_items))
        self.assertEqual(
            ["LOCATION_LIGHTHOUSE_KEEPER_REWARD_TRADE_MOTHS_FOR_FISHING_ROD"],
            list(event.rewards),
        )

        lighthouse = data.regions["REGION_LIGHTHOUSE"]
        self.assertIn("EVENT_LIGHTHOUSE_KEEPER_TRADE_MOTHS_FOR_FISHING_ROD", lighthouse.events)
        self.assertIn(event.rewards[0], lighthouse.locations)
        self.assertEqual("REGION_LIGHTHOUSE", data.locations[event.rewards[0]].parent_region)

        node_names = load_json_data("quest_node_names.json")
        self.assertEqual(event.location_label, node_names["npc_light_keeper:13:option:4"])

    def test_clotho_lost_memories_long_route_has_three_independent_rewards(self):
        cauldron = data.events["EVENT_CLOTHO_GIVE_CAULDRON"]
        powder = data.events["EVENT_CLOTHO_GIVE_HEALTH_POWDER"]
        bee = data.events["EVENT_CLOTHO_GIVE_BEE"]

        self.assertEqual([], list(cauldron.required_quests))
        self.assertEqual(["ITEM_CAULDRON"], list(cauldron.required_quest_items))
        self.assertEqual(["LOCATION_CLOTHO_REWARD_GIVE_CAULDRON"], list(cauldron.rewards))

        for ingredient_event in (powder, bee):
            self.assertEqual(
                ["EVENT_CLOTHO_GIVE_CAULDRON"],
                list(ingredient_event.required_quests),
            )
        self.assertNotIn("EVENT_CLOTHO_GIVE_BEE", powder.required_quests)
        self.assertNotIn("EVENT_CLOTHO_GIVE_HEALTH_POWDER", bee.required_quests)
        self.assertEqual(["ITEM_HEALTH_POWDER"], list(powder.required_craft_items))
        self.assertEqual(["ITEM_BEE"], list(bee.required_craft_items))
        self.assertEqual(
            ["LOCATION_CLOTHO_REWARD_GIVE_HEALTH_POWDER"],
            list(powder.rewards),
        )
        self.assertEqual(["LOCATION_CLOTHO_REWARD_GIVE_BEE"], list(bee.rewards))

        clotho_lost_memories_rewards = {
            location_key
            for event in (cauldron, powder, bee)
            for location_key in event.rewards
        }
        self.assertEqual(
            {
                "LOCATION_CLOTHO_REWARD_GIVE_CAULDRON",
                "LOCATION_CLOTHO_REWARD_GIVE_HEALTH_POWDER",
                "LOCATION_CLOTHO_REWARD_GIVE_BEE",
            },
            clotho_lost_memories_rewards,
        )
        self.assertFalse(
            any("HEALTH_POTION" in location_key for location_key in data.locations),
            "The exclusive health-potion shortcut must reuse the three long-route checks",
        )

        self.assertEqual(10, data.items["ITEM_CLOTHO_HAPPINESS_10"].amount)
        self.assertEqual(5, data.items["ITEM_CLOTHO_HAPPINESS_5"].amount)
        self.assertEqual(
            ItemClassification.progression,
            data.items["ITEM_CLOTHO_HAPPINESS_10"].classification,
        )
        self.assertEqual(
            ItemClassification.progression,
            data.items["ITEM_CLOTHO_HAPPINESS_5"].classification,
        )

        swamp = data.regions["REGION_SWAMP"]
        for event_name, event in (
            ("EVENT_CLOTHO_GIVE_CAULDRON", cauldron),
            ("EVENT_CLOTHO_GIVE_HEALTH_POWDER", powder),
            ("EVENT_CLOTHO_GIVE_BEE", bee),
        ):
            with self.subTest(event=event_name):
                self.assertIn(event_name, swamp.events)
                self.assertEqual(1, len(event.rewards))
                self.assertIn(event.rewards[0], swamp.locations)
                self.assertEqual("REGION_SWAMP", data.locations[event.rewards[0]].parent_region)

        self.assertNotIn("LOCATION_CLOTHO_MEET", data.locations)
        self.assertNotIn("LOCATION_CLOTHO_ACCEPT_QUEST_LOST_MEMORIES", data.locations)

        node_names = load_json_data("quest_node_names.json")
        self.assertEqual(cauldron.location_label, node_names["npc_witch:9:option:0"])
        self.assertEqual(powder.location_label, node_names["npc_witch:9:option:2"])
        self.assertEqual(bee.location_label, node_names["npc_witch:9:option:3"])

    def test_gerry_drink_turn_ins_follow_the_vanilla_order(self):
        beer = data.events["EVENT_GERRY_GIVE_BEER"]
        wine = data.events["EVENT_GERRY_GIVE_SILVER_WINE"]
        tavern = data.events["EVENT_TAVERN_OPEN"]

        self.assertEqual(["EVENT_TUTORIAL_FINISH"], list(beer.required_quests))
        self.assertEqual(["ITEM_A_MUG_OF_BEER_COPPER"], list(beer.required_craft_items))
        self.assertEqual(["LOCATION_GERRY_REWARD_GIVE_BEER"], list(beer.rewards))

        self.assertEqual(["EVENT_GERRY_GIVE_BEER"], list(wine.required_quests))
        self.assertEqual(["ITEM_RED_WINE_SILVER"], list(wine.required_craft_items))
        self.assertEqual(
            ["LOCATION_GERRY_REWARD_GIVE_SILVER_WINE"],
            list(wine.rewards),
        )
        self.assertEqual(["EVENT_GERRY_GIVE_SILVER_WINE"], list(tavern.required_quests))

        morgue = data.regions["REGION_MORGUE"]
        for event_name, event in (
            ("EVENT_GERRY_GIVE_BEER", beer),
            ("EVENT_GERRY_GIVE_SILVER_WINE", wine),
        ):
            with self.subTest(event=event_name):
                self.assertIn(event_name, morgue.events)
                self.assertIn(event.rewards[0], morgue.locations)
                self.assertEqual(
                    "REGION_MORGUE",
                    data.locations[event.rewards[0]].parent_region,
                )

        self.assertNotIn("EVENT_GERRY_GET_GERRY_BEER", data.events)
        self.assertNotIn("EVENT_GERRY_GET_GERRY_WINE", data.events)
        self.assertNotIn("LOCATION_GERRY_REWARD_GET_GERRY_BEER", data.locations)
        self.assertNotIn("LOCATION_GERRY_REWARD_GET_GERRY_WINE", data.locations)

        node_names = load_json_data("quest_node_names.json")
        self.assertEqual(beer.location_label, node_names["crafting_skull_3:134:option:0"])
        self.assertEqual(wine.location_label, node_names["crafting_skull_3:134:option:2"])

    def test_miss_chain_perfume_chain_matches_flow_requirements(self):
        ask = data.events["EVENT_MISS_CHAIN_ASK_FOR_PERFUME"]
        deliver = data.events["EVENT_CLOTHO_GIVE_BASKET_OF_FOOD"]
        report = data.events["EVENT_MISS_CHAIN_REPORT_FOOD_DELIVERED"]
        frogs = data.events["EVENT_MISS_CHAIN_GIVE_FROGS"]
        perfume = data.events["EVENT_MISS_CHAIN_GET_PERFUME"]
        give_perfume = data.events["EVENT_MS_CHARM_GIVE_PERFUME"]

        self.assertEqual(["EVENT_MS_CHARM_REPORT_FAKE_COINS"], list(ask.required_quests))
        self.assertEqual(["LOCATION_MISS_CHAIN_REWARD_ASK_FOR_PERFUME"], list(ask.rewards))
        self.assertEqual(["EVENT_MISS_CHAIN_ASK_FOR_PERFUME"], list(deliver.required_quests))
        self.assertEqual(["ITEM_BASKET_OF_FOOD"], list(deliver.required_quest_items))
        self.assertEqual([], list(deliver.rewards))
        self.assertEqual(["EVENT_CLOTHO_GIVE_BASKET_OF_FOOD"], list(report.required_quests))
        self.assertEqual(["LOCATION_MISS_CHAIN_REWARD_REPORT_FOOD_DELIVERED"], list(report.rewards))
        self.assertEqual(["EVENT_MISS_CHAIN_ASK_FOR_PERFUME"], list(frogs.required_quests))
        self.assertEqual(["ITEM_FROG"], list(frogs.required_craft_items))
        self.assertEqual(["LOCATION_MISS_CHAIN_REWARD_GIVE_FROGS"], list(frogs.rewards))
        self.assertEqual(["EVENT_CLOTHO_GIVE_BASKET_OF_FOOD"], list(perfume.required_quests))
        self.assertEqual([HappinessData("MISS_CHAIN", 20)], list(perfume.required_happiness))
        self.assertEqual(["LOCATION_MISS_CHAIN_REWARD_GET_PERFUME"], list(perfume.rewards))
        self.assertEqual(["EVENT_MS_CHARM_REPORT_FAKE_COINS"], list(give_perfume.required_quests))
        self.assertEqual(["ITEM_PERFUME"], list(give_perfume.required_quest_items))

        miss_chain_happiness = data.items["ITEM_MISS_CHAIN_HAPPINESS_10"]
        self.assertEqual(ItemClassification.progression, miss_chain_happiness.classification)
        self.assertEqual(10, miss_chain_happiness.amount)

        dead_horse = data.regions["REGION_THE_DEAD_HORSE"]
        for event_name, event in (
            ("EVENT_MISS_CHAIN_ASK_FOR_PERFUME", ask),
            ("EVENT_MISS_CHAIN_REPORT_FOOD_DELIVERED", report),
            ("EVENT_MISS_CHAIN_GIVE_FROGS", frogs),
            ("EVENT_MISS_CHAIN_GET_PERFUME", perfume),
        ):
            with self.subTest(event=event_name):
                self.assertIn(event_name, dead_horse.events)
                for reward in event.rewards:
                    self.assertIn(reward, dead_horse.locations)
                    self.assertEqual("REGION_THE_DEAD_HORSE", data.locations[reward].parent_region)
        self.assertIn("EVENT_CLOTHO_GIVE_BASKET_OF_FOOD", data.regions["REGION_SWAMP"].events)

        node_names = load_json_data("quest_node_names.json")
        expected_names = {
            "npc_mrs chain:13:option:0": ask.location_label,
            "npc_witch:9:option:6": deliver.location_label,
            "npc_mrs chain:13:option:1": report.location_label,
            "npc_mrs chain:13:option:2": frogs.location_label,
            "npc_mrs chain:13:option:3": perfume.location_label,
        }
        for node_id, expected_name in expected_names.items():
            with self.subTest(node_id=node_id):
                self.assertEqual(expected_name, node_names[node_id])

    def test_fixing_the_mill_and_alisa_chain_matches_flow_requirements(self):
        repair_event = data.events["EVENT_REPAIR_MILL"]
        permission_event = data.events["EVENT_FARMER_GET_PERMISSION_FOR_ALISA"]
        papers_event = data.events["EVENT_MS_CHARM_GIVE_ALISAS_PAPERS"]
        aristocrat_event = data.events["EVENT_MS_CHARM_SHOW_ARISTOCRAT_PAPERS"]

        self.assertEqual(
            ["EVENT_ASTROLOGER_ASK_ABOUT_MILL_FIX"],
            list(repair_event.required_quests),
        )
        self.assertEqual(["ITEM_PAPER_WITH_CALCULATIONS"], list(repair_event.required_quest_items))
        self.assertEqual(
            {"ITEM_WOODEN_PLANK", "ITEM_COMPLEX_IRON_PARTS"},
            set(repair_event.required_craft_items),
        )
        self.assertEqual(["EVENT_REPAIR_MILL"], list(permission_event.required_quests))
        self.assertEqual(2, len(permission_event.rewards))
        node_names = load_json_data("quest_node_names.json")
        for node_id in ("npc_farmer:225", "npc_farmer:235"):
            with self.subTest(node_id=node_id):
                self.assertEqual(permission_event.location_label, node_names[node_id])
        self.assertEqual(["ITEM_ALISAS_PAPERS"], list(papers_event.required_quest_items))
        self.assertEqual(["EVENT_MS_CHARM_GIVE_ALISAS_PAPERS"], list(aristocrat_event.required_quests))
        self.assertEqual(["ITEM_ARISTOCRAT_PAPERS"], list(aristocrat_event.required_quest_items))
        self.assertEqual(2, len(aristocrat_event.rewards))

    def test_ms_charm_love_song_chain_matches_flow_requirements(self):
        ask_event = data.events["EVENT_VAGNER_ASK_TO_WRITE_LOVE_SONG"]
        infusion_event = data.events["EVENT_VAGNER_GIVE_INFUSION"]
        note_event = data.events["EVENT_VAGNER_READ_NOTE"]
        cliffs_event = data.events["EVENT_VAGNER_MEET_AT_CLIFFS"]
        song_event = data.events["EVENT_MS_CHARM_GIVE_SONG_LYRICS"]
        rescue_event = data.events["EVENT_ASTROLOGER_ASK_TO_HELP_RESCUE_VAGNER"]
        expedition_event = data.events["EVENT_ASTROLOGER_TALK_ABOUT_EXPEDITION"]

        self.assertEqual(["EVENT_MS_CHARM_SHOW_ARISTOCRAT_PAPERS"], list(ask_event.required_quests))
        self.assertEqual(
            ["ITEM_INFUSION_OF_FLY_AGARIC"],
            list(infusion_event.required_quest_items),
        )
        self.assertEqual([], list(infusion_event.required_craft_items))
        self.assertEqual(["EVENT_VAGNER_GIVE_INFUSION"], list(note_event.required_quests))
        self.assertEqual(["EVENT_VAGNER_READ_NOTE"], list(cliffs_event.required_quests))
        self.assertEqual(["ITEM_SONG_LYRICS"], list(song_event.required_quest_items))
        self.assertEqual(2, len(song_event.rewards))
        self.assertEqual(["EVENT_MS_CHARM_GIVE_SONG_LYRICS"], list(rescue_event.required_quests))
        self.assertEqual(["EVENT_ASTROLOGER_ASK_TO_HELP_RESCUE_VAGNER"], list(expedition_event.required_quests))

    def test_vagner_writing_supplies_and_wine_are_separate_reward_steps(self):
        meeting = data.events["EVENT_VAGNER_MEET"]
        ink = data.events["EVENT_VAGNER_GIVE_INK"]
        paper = data.events["EVENT_VAGNER_GIVE_CLEAN_PAPER"]
        wine = data.events["EVENT_VAGNER_GIVE_SILVER_WINE"]

        self.assertEqual(["EVENT_TUTORIAL_FINISH"], list(meeting.required_quests))
        self.assertEqual(["LOCATION_VAGNER_REWARD_MEET"], list(meeting.rewards))

        for event, required_item, reward in (
            (ink, "ITEM_INK", "LOCATION_VAGNER_REWARD_GIVE_INK"),
            (paper, "ITEM_CLEAN_PAPER", "LOCATION_VAGNER_REWARD_GIVE_CLEAN_PAPER"),
        ):
            with self.subTest(event=event.location_label):
                self.assertEqual(["EVENT_VAGNER_MEET"], list(event.required_quests))
                self.assertEqual([required_item], list(event.required_craft_items))
                self.assertEqual([reward], list(event.rewards))

        self.assertEqual(
            {"EVENT_VAGNER_GIVE_INK", "EVENT_VAGNER_GIVE_CLEAN_PAPER"},
            set(wine.required_quests),
            "Both independently rewarded +10 relation turn-ins are needed to reach Vagner's 20-relation menu",
        )
        self.assertEqual(["ITEM_RED_WINE_SILVER"], list(wine.required_craft_items))
        self.assertEqual(2, len(wine.rewards))

        node_names = load_json_data("quest_node_names.json")
        expected_names = {
            "npc_actor:221": meeting.location_label,
            "npc_actor:17:option:0": ink.location_label,
            "npc_actor:17:option:1": paper.location_label,
            "npc_actor:145:option:0": wine.location_label,
        }
        for node_id, expected_name in expected_names.items():
            with self.subTest(node_id=node_id):
                self.assertEqual(expected_name, node_names[node_id])

        dead_horse = data.regions["REGION_THE_DEAD_HORSE"]
        for event_name, event in (
            ("EVENT_VAGNER_MEET", meeting),
            ("EVENT_VAGNER_GIVE_INK", ink),
            ("EVENT_VAGNER_GIVE_CLEAN_PAPER", paper),
            ("EVENT_VAGNER_GIVE_SILVER_WINE", wine),
        ):
            with self.subTest(region_event=event.location_label):
                self.assertIn(event_name, dead_horse.events)
                for reward in event.rewards:
                    self.assertIn(reward, dead_horse.locations)
                    self.assertEqual("REGION_THE_DEAD_HORSE", data.locations[reward].parent_region)

    def test_astrologer_rescue_expedition_matches_linear_flow_rewards(self):
        papers_event = data.events["EVENT_ASTROLOGER_SHOW_ARISTOCRAT_PAPERS"]
        rescue_event = data.events["EVENT_ASTROLOGER_RESCUE_VAGNER"]

        self.assertEqual(["ITEM_ARISTOCRAT_PAPERS"], list(papers_event.required_quest_items))
        self.assertEqual([], list(papers_event.required_craft_items))
        self.assertEqual(2, len(papers_event.rewards))
        self.assertEqual(
            ["EVENT_ASTROLOGER_SHOW_ARISTOCRAT_PAPERS"],
            list(rescue_event.required_quests),
        )
        self.assertEqual(
            [HappinessData("ASTROLOGER", 90)],
            list(rescue_event.required_happiness),
        )
        self.assertEqual(4, len(rescue_event.rewards))
        self.assertIn("EVENT_ASTROLOGER_RESCUE_VAGNER", data.regions["REGION_LIGHTHOUSE"].events)

        node_names = load_json_data("quest_node_names.json")
        for node_id in (
            "archaeological_excavations:284",
            "archaeological_excavations:286",
            "archaeological_excavations:299",
            "archaeological_excavations:301",
        ):
            with self.subTest(node_id=node_id):
                self.assertEqual(rescue_event.location_label, node_names[node_id])

    def test_royal_services_status_and_document_chain_matches_flow_requirements(self):
        citizen = data.events["EVENT_ROYAL_SERVICES_BUY_CITIZENSHIP"]
        stamp = data.events["EVENT_ROYAL_SERVICES_BUY_ROYAL_STAMP"]
        building = data.events["EVENT_ROYAL_SERVICES_BUY_BUILDING_PERMISSION"]
        rightful = data.events["EVENT_ROYAL_SERVICES_BUY_RIGHTFUL_CITIZENSHIP"]
        rightful_papers = data.events["EVENT_ROYAL_SERVICES_CLAIM_RIGHTFUL_CITIZEN_PAPERS"]
        town_pass = data.events["EVENT_ROYAL_SERVICES_CLAIM_TOWN_PASS"]
        trade_license = data.events["EVENT_ROYAL_SERVICES_BUY_TRADE_LICENSE"]
        aristocrat = data.events["EVENT_ROYAL_SERVICES_BUY_ARISTOCRAT_STATUS"]
        aristocrat_papers = data.events["EVENT_ROYAL_SERVICES_CLAIM_ARISTOCRAT_PAPERS"]

        self.assertEqual([], list(citizen.required_quests))
        self.assertEqual(1, len(citizen.rewards))
        for citizen_purchase in (stamp, building, rightful):
            self.assertEqual(
                ["EVENT_ROYAL_SERVICES_BUY_CITIZENSHIP"],
                list(citizen_purchase.required_quests),
            )
            self.assertEqual(
                [HappinessData("ROYAL_SERVICES", 30)],
                list(citizen_purchase.required_happiness),
            )
            self.assertEqual(1, len(citizen_purchase.rewards))

        for rightful_purchase in (rightful_papers, town_pass, trade_license, aristocrat):
            self.assertEqual(
                ["EVENT_ROYAL_SERVICES_BUY_RIGHTFUL_CITIZENSHIP"],
                list(rightful_purchase.required_quests),
            )
            self.assertEqual(
                [HappinessData("ROYAL_SERVICES", 65)],
                list(rightful_purchase.required_happiness),
            )
            self.assertEqual(1, len(rightful_purchase.rewards))

        self.assertEqual(
            ["EVENT_ROYAL_SERVICES_BUY_ARISTOCRAT_STATUS"],
            list(aristocrat_papers.required_quests),
        )
        self.assertEqual(
            [HappinessData("ROYAL_SERVICES", 100)],
            list(aristocrat_papers.required_happiness),
        )
        self.assertEqual(1, len(aristocrat_papers.rewards))
        self.assertIn("ITEM_TRADE_LICENSE", data.items)
        for event_key in (
            "EVENT_ROYAL_SERVICES_BUY_CITIZENSHIP",
            "EVENT_ROYAL_SERVICES_BUY_ROYAL_STAMP",
            "EVENT_ROYAL_SERVICES_BUY_BUILDING_PERMISSION",
            "EVENT_ROYAL_SERVICES_BUY_RIGHTFUL_CITIZENSHIP",
            "EVENT_ROYAL_SERVICES_CLAIM_RIGHTFUL_CITIZEN_PAPERS",
            "EVENT_ROYAL_SERVICES_CLAIM_TOWN_PASS",
            "EVENT_ROYAL_SERVICES_BUY_TRADE_LICENSE",
            "EVENT_ROYAL_SERVICES_BUY_ARISTOCRAT_STATUS",
            "EVENT_ROYAL_SERVICES_CLAIM_ARISTOCRAT_PAPERS",
        ):
            self.assertIn(event_key, data.regions["REGION_OLD_GRAVEYARD"].events)

    def test_merchant_garden_route_requires_all_three_independent_vegetable_turn_ins(self):
        inspect = data.events["EVENT_INSPECT_KITCHEN_GARDEN"]
        horadric = data.events["EVENT_HORADRIC_ASK_ABOUT_KITCHEN_GARDEN"]
        deal = data.events["EVENT_MERCHANT_ACCEPT_VEGETABLE_DEAL"]
        carrots = data.events["EVENT_MERCHANT_GIVE_CARROTS"]
        cabbages = data.events["EVENT_MERCHANT_GIVE_CABBAGES"]
        beets = data.events["EVENT_MERCHANT_GIVE_BEETS"]
        complete = data.events["EVENT_MERCHANT_COMPLETE_VEGETABLE_DEAL"]

        self.assertEqual([], list(inspect.required_quests))
        self.assertEqual(["EVENT_INSPECT_KITCHEN_GARDEN"], list(horadric.required_quests))
        self.assertEqual(["EVENT_HORADRIC_ASK_ABOUT_KITCHEN_GARDEN"], list(deal.required_quests))
        for turn_in, item_key in (
            (carrots, "ITEM_CARROT"),
            (cabbages, "ITEM_CABBAGE"),
            (beets, "ITEM_BEET"),
        ):
            self.assertEqual(["EVENT_MERCHANT_ACCEPT_VEGETABLE_DEAL"], list(turn_in.required_quests))
            self.assertEqual([item_key], list(turn_in.required_craft_items))
            self.assertEqual([], list(turn_in.rewards))
        self.assertEqual(
            {
                "EVENT_MERCHANT_GIVE_CARROTS",
                "EVENT_MERCHANT_GIVE_CABBAGES",
                "EVENT_MERCHANT_GIVE_BEETS",
            },
            set(complete.required_quests),
        )
        self.assertEqual(["LOCATION_MERCHANT_REWARD_GIVE_HIM_VEGETABLES"], list(complete.rewards))

    def test_merchant_cure_and_dinner_route_matches_flow_requirements(self):
        ask = data.events["EVENT_MERCHANT_ASK_FOR_HICCUP_CURE"]
        grass = data.events["EVENT_MERCHANT_GIVE_HICCUP_GRASS"]
        clotho = data.events["EVENT_CLOTHO_ASK_ABOUT_MERCHANT_CURSE"]
        spices = data.events["EVENT_MERCHANT_GIVE_SPICES"]
        dinner = data.events["EVENT_MERCHANT_GIVE_GOLD_DINNER"]
        strategy = data.events["EVENT_MERCHANT_DISCUSS_ROYAL_DINNER"]

        self.assertEqual(["EVENT_MERCHANT_ACCEPT_VEGETABLE_DEAL"], list(ask.required_quests))
        self.assertEqual(["ITEM_HICCUP_GRASS"], list(grass.required_craft_items))
        self.assertEqual(["EVENT_MERCHANT_GIVE_HICCUP_GRASS"], list(clotho.required_quests))
        self.assertEqual(["ITEM_SPICES"], list(spices.required_craft_items))
        self.assertEqual(["EVENT_MERCHANT_GIVE_SPICES"], list(dinner.required_quests))
        self.assertEqual(["ITEM_DINNER_GOLD"], list(dinner.required_craft_items))
        self.assertEqual([HappinessData("MERCHANT", 70)], list(strategy.required_happiness))

    def test_merchant_loan_is_a_non_missable_rewarding_side_chain(self):
        accept = data.events["EVENT_MERCHANT_ACCEPT_LOAN"]
        repay = data.events["EVENT_MERCHANT_REPAY_LOAN"]

        self.assertEqual(["EVENT_MERCHANT_ASK_FOR_LOAN"], list(accept.required_quests))
        self.assertEqual(["LOCATION_MERCHANT_REWARD_ACCEPT_LOAN"], list(accept.rewards))
        self.assertEqual(["EVENT_MERCHANT_ACCEPT_LOAN"], list(repay.required_quests))
        self.assertFalse(any(
            "EVENT_MERCHANT_ACCEPT_LOAN" in event.required_quests
            for key, event in data.events.items()
            if isinstance(event, QuestEventData) and key != "EVENT_MERCHANT_REPAY_LOAN"
        ))

    def test_merchant_trade_office_tasks_are_independent_after_showing_license(self):
        discuss = data.events["EVENT_MERCHANT_DISCUSS_TRADE_BUSINESS"]
        license_event = data.events["EVENT_MERCHANT_SHOW_TRADE_LICENSE"]
        marketing = data.events["EVENT_MERCHANT_COMPLETE_MARKETING"]
        sales = data.events["EVENT_MERCHANT_COMPLETE_SALES"]

        self.assertEqual(["EVENT_MERCHANT_COMPLETE_VEGETABLE_DEAL"], list(discuss.required_quests))
        self.assertEqual(["ITEM_TRADE_LICENSE"], list(license_event.required_quest_items))
        for task in (marketing, sales):
            self.assertEqual(["EVENT_MERCHANT_SHOW_TRADE_LICENSE"], list(task.required_quests))
            self.assertEqual(1, len(task.rewards))
        self.assertEqual([AreaPointData("TRADE_OFFICE", 3)], list(marketing.required_area_points))
        self.assertEqual(["ITEM_TRADE_CRATE"], list(sales.required_craft_items))

    def test_ms_charm_business_request_and_jewelry_hand_in_are_separate(self):
        request = data.events["EVENT_MS_CHARM_PROMOTE_BUSINESS"]
        jewelry = data.events["EVENT_MS_CHARM_GIVE_JEWELRY_FOR_BUSINESS"]
        report = data.events["EVENT_MERCHANT_REPORT_MS_CHARM_SUPPORT"]

        self.assertEqual(["EVENT_MERCHANT_ASK_FOR_MS_CHARM_SUPPORT"], list(request.required_quests))
        self.assertEqual([HappinessData("MS_CHARM", 40)], list(request.required_happiness))
        self.assertEqual([], list(request.required_craft_items))
        self.assertEqual(["EVENT_MS_CHARM_PROMOTE_BUSINESS"], list(jewelry.required_quests))
        self.assertEqual(["ITEM_JEWELRY"], list(jewelry.required_craft_items))
        self.assertEqual([], list(jewelry.rewards))
        self.assertEqual(["EVENT_MS_CHARM_GIVE_JEWELRY_FOR_BUSINESS"], list(report.required_quests))
        self.assertEqual(1, len(report.rewards))

    def test_merchant_final_ceremony_guarantees_artifact_if_early_dialogue_is_missed(self):
        invitation = data.events["EVENT_MERCHANT_INVITE_TO_FINAL_CEREMONY"]
        ask_artifact = data.events["EVENT_MERCHANT_ASK_ABOUT_PORTAL_ARTIFACT"]
        artifact = data.events["EVENT_MERCHANT_ASK_FOR_PORTAL_ARTIFACT"]

        self.assertEqual(
            {"EVENT_MERCHANT_GIVE_SPICES", "EVENT_INQUISITOR_REFUSE_FINAL_CEREMONY"},
            set(invitation.required_quests),
        )
        self.assertEqual([HappinessData("MERCHANT", 90)], list(invitation.required_happiness))
        self.assertEqual(1, len(invitation.rewards))
        self.assertEqual(
            ["EVENT_SNAKE_IDENTIFY_PORTAL_ARTIFACT_HOLDERS"],
            list(ask_artifact.required_quests),
        )
        self.assertEqual([HappinessData("MERCHANT", 100)], list(artifact.required_happiness))
        self.assertEqual(
            [],
            list(artifact.rewards),
            "Only the early dialogue is missable; the ceremony owns the one guaranteed fork check",
        )

    def test_inquisitor_base_game_questline_matches_flow_requirements(self):
        meet = data.events["EVENT_INQUISITOR_MEET"]
        first_burning = data.events["EVENT_INQUISITOR_ATTEND_FIRST_BURNING"]
        prepare = data.events["EVENT_INQUISITOR_PREPARE_SECOND_BURNING"]
        firewood = data.events["EVENT_INQUISITOR_GIVE_FIREWOOD"]
        flyers = data.events["EVENT_INQUISITOR_GIVE_FLYERS"]
        second_burning = data.events["EVENT_INQUISITOR_ATTEND_SECOND_BURNING"]
        wine = data.events["EVENT_INQUISITOR_GIVE_RED_WINE"]
        ask_tent = data.events["EVENT_INQUISITOR_ASK_TO_BUILD_BUFFET_TENT"]
        build_tent = data.events["EVENT_INQUISITOR_BUILD_BUFFET_TENT"]
        report_tent = data.events["EVENT_INQUISITOR_REPORT_BUFFET_TENT_READY"]
        buffet = data.events["EVENT_INQUISITOR_HOST_FIRST_BUFFET_BURNING"]
        wait_for_organs = data.events["EVENT_INQUISITOR_WAIT_FOR_DARK_ORGAN_REQUEST"]
        dark_heart = data.events["EVENT_INQUISITOR_GIVE_DARK_HEART"]
        dark_brain = data.events["EVENT_INQUISITOR_GIVE_DARK_BRAIN"]
        dark_intestine = data.events["EVENT_INQUISITOR_GIVE_DARK_INTESTINE"]
        evidence = data.events["EVENT_INQUISITOR_RESPOND_TO_FAILED_DARK_ORGAN_EVIDENCE"]

        self.assertEqual([], list(meet.required_quests))
        self.assertEqual([], list(meet.rewards))
        self.assertEqual(["EVENT_INQUISITOR_MEET"], list(first_burning.required_quests))
        self.assertEqual(1, len(first_burning.rewards))
        self.assertEqual(["EVENT_INQUISITOR_ATTEND_FIRST_BURNING"], list(prepare.required_quests))

        for turn_in, item_key in ((firewood, "ITEM_FIREWOOD"), (flyers, "ITEM_FLYER")):
            self.assertEqual(["EVENT_INQUISITOR_PREPARE_SECOND_BURNING"], list(turn_in.required_quests))
            self.assertEqual([item_key], list(turn_in.required_craft_items))
            self.assertEqual(1, len(turn_in.rewards))
        self.assertEqual(
            {"EVENT_INQUISITOR_GIVE_FIREWOOD", "EVENT_INQUISITOR_GIVE_FLYERS"},
            set(second_burning.required_quests),
        )
        self.assertEqual(1, len(second_burning.rewards))

        self.assertEqual(["ITEM_RED_WINE_SILVER"], list(wine.required_craft_items))
        self.assertEqual([HappinessData("INQUISITOR", 50)], list(ask_tent.required_happiness))
        self.assertEqual(
            {"ITEM_HEMP_ROPE", "ITEM_WOODEN_PLANK", "ITEM_NAILS"},
            set(build_tent.required_craft_items),
        )
        self.assertEqual(["EVENT_INQUISITOR_BUILD_BUFFET_TENT"], list(report_tent.required_quests))
        self.assertEqual(
            {"ITEM_A_MUG_OF_BEER_GOLD", "ITEM_BURGER_GOLD"},
            set(buffet.required_craft_items),
        )
        self.assertEqual(["EVENT_INQUISITOR_HOST_FIRST_BUFFET_BURNING"], list(wait_for_organs.required_quests))
        self.assertEqual([], list(wait_for_organs.rewards))

        for turn_in, item_key in (
            (dark_heart, "ITEM_DARK_HEART"),
            (dark_brain, "ITEM_DARK_BRAIN"),
            (dark_intestine, "ITEM_DARK_INTESTINE"),
        ):
            self.assertEqual(["EVENT_INQUISITOR_WAIT_FOR_DARK_ORGAN_REQUEST"], list(turn_in.required_quests))
            self.assertEqual([item_key], list(turn_in.required_craft_items))
            self.assertEqual(1, len(turn_in.rewards))
        self.assertEqual(
            {
                "EVENT_INQUISITOR_GIVE_DARK_HEART",
                "EVENT_INQUISITOR_GIVE_DARK_BRAIN",
                "EVENT_INQUISITOR_GIVE_DARK_INTESTINE",
            },
            set(evidence.required_quests),
        )

    def test_inquisitor_side_routes_match_phrase_and_happiness_gates(self):
        ask_graveyard = data.events["EVENT_INQUISITOR_ASK_TO_EXPAND_GRAVEYARD"]
        graveyard = data.events["EVENT_INQUISITOR_GET_GRAVEYARD_EXPANSION_PERMISSION"]
        ask_guards = data.events["EVENT_INQUISITOR_ASK_TO_REMOVE_PORTAL_GUARDS"]
        guards = data.events["EVENT_INQUISITOR_REPORT_PORTAL_GUARDS_REMOVED"]
        ceremony = data.events["EVENT_INQUISITOR_REFUSE_FINAL_CEREMONY"]
        ask_artifact = data.events["EVENT_INQUISITOR_ASK_ABOUT_PORTAL_ARTIFACT"]
        artifact = data.events["EVENT_INQUISITOR_HAND_OVER_PORTAL_ARTIFACT"]

        self.assertEqual(["EVENT_INQUISITOR_MEET"], list(ask_graveyard.required_quests))
        self.assertEqual([HappinessData("INQUISITOR", 20)], list(graveyard.required_happiness))
        self.assertEqual(1, len(graveyard.rewards))
        self.assertEqual(["EVENT_INQUISITOR_MEET"], list(ask_guards.required_quests))
        self.assertEqual([HappinessData("INQUISITOR", 60)], list(guards.required_happiness))
        self.assertEqual(1, len(guards.rewards))
        self.assertEqual(["EVENT_BISHOP_REPORT_CATHEDRAL_UPGRADE"], list(ceremony.required_quests))
        self.assertEqual([HappinessData("INQUISITOR", 60)], list(ceremony.required_happiness))
        self.assertEqual([], list(ceremony.rewards))
        self.assertEqual(
            ["EVENT_SNAKE_IDENTIFY_PORTAL_ARTIFACT_HOLDERS"],
            list(ask_artifact.required_quests),
        )
        self.assertEqual([HappinessData("INQUISITOR", 100)], list(artifact.required_happiness))
        self.assertEqual(1, len(artifact.rewards))

    def test_gypsy_baron_esmeralda_chain_matches_phrase_and_happiness_gates(self):
        ask_gypsy = data.events["EVENT_GYPSY_BARON_ASK_ABOUT_ESMERALDA"]
        release_friend = data.events["EVENT_INQUISITOR_RELEASE_GYPSY_BARONS_FRIEND"]
        report_release = data.events["EVENT_GYPSY_BARON_REPORT_FRIEND_RELEASED"]
        learn_fate = data.events["EVENT_GYPSY_BARON_LEARN_ESMERALDAS_FATE"]
        tell_astrologer = data.events["EVENT_ASTROLOGER_TELL_ESMERALDAS_FATE"]

        self.assertEqual(
            ["EVENT_ASTROLOGER_LEARN_ABOUT_ESMERALDA"],
            list(ask_gypsy.required_quests),
        )
        self.assertEqual(
            ["EVENT_GYPSY_BARON_ASK_ABOUT_ESMERALDA"],
            list(release_friend.required_quests),
        )
        self.assertEqual(
            [HappinessData("INQUISITOR", 60)],
            list(release_friend.required_happiness),
        )
        self.assertEqual(
            ["EVENT_INQUISITOR_RELEASE_GYPSY_BARONS_FRIEND"],
            list(report_release.required_quests),
        )
        self.assertEqual(
            ["LOCATION_GYPSY_BARON_REWARD_REPORT_FRIEND_RELEASED"],
            list(report_release.rewards),
        )
        self.assertEqual(
            ["EVENT_GYPSY_BARON_REPORT_FRIEND_RELEASED"],
            list(learn_fate.required_quests),
        )
        self.assertEqual(
            [HappinessData("GYPSY_BARON", 10)],
            list(learn_fate.required_happiness),
        )
        self.assertEqual(
            ["EVENT_GYPSY_BARON_LEARN_ESMERALDAS_FATE"],
            list(tell_astrologer.required_quests),
        )
        self.assertEqual(
            ItemClassification.progression,
            data.items["ITEM_GYPSY_BARON_HAPPINESS_10"].classification,
        )
        for event_key in (
            "EVENT_GYPSY_BARON_ASK_ABOUT_ESMERALDA",
            "EVENT_GYPSY_BARON_REPORT_FRIEND_RELEASED",
            "EVENT_GYPSY_BARON_LEARN_ESMERALDAS_FATE",
        ):
            self.assertIn(event_key, data.regions["REGION_CAMP"].events)

    def test_krezvold_tutorial_questline_matches_flow_requirements(self):
        get_letter = data.events["EVENT_HORADRIC_GET_BLACKSMITH_LETTER"]
        give_letter = data.events["EVENT_KREZVOLD_GIVE_BLACKSMITH_LETTER"]
        ask_ore = data.events["EVENT_KREZVOLD_ASK_ABOUT_METAL_ORE"]
        slimes = data.events["EVENT_KREZVOLD_COMPLETE_SLIME_QUEST"]

        self.assertEqual(["EVENT_TUTORIAL_FINISH"], list(get_letter.required_quests))
        self.assertEqual(
            ["LOCATION_HORADRIC_REWARD_GET_BLACKSMITH_LETTER"],
            list(get_letter.rewards),
        )
        self.assertEqual(
            ["EVENT_HORADRIC_GET_BLACKSMITH_LETTER"],
            list(give_letter.required_quests),
        )
        self.assertEqual(
            ["ITEM_LETTER_TO_THE_BLACKSMITH"],
            list(give_letter.required_quest_items),
        )
        self.assertEqual(4, len(give_letter.rewards))

        for branch in (ask_ore, slimes):
            self.assertEqual(
                ["EVENT_KREZVOLD_GIVE_BLACKSMITH_LETTER"],
                list(branch.required_quests),
            )
            self.assertEqual(1, len(branch.rewards))
        self.assertEqual(
            [HappinessData("KREZVOLD", 10)],
            list(ask_ore.required_happiness),
        )
        self.assertEqual(["ITEM_GREEN_JELLY"], list(slimes.required_craft_items))
        self.assertEqual(
            ItemClassification.progression,
            data.items["ITEM_KREZVOLD_HAPPINESS_10"].classification,
        )

    def test_horadric_side_rewards_match_their_interaction_event_sources(self):
        slimes = data.events["EVENT_HORADRIC_COLLECT_SLIME_QUEST_REWARD"]
        church = data.events["EVENT_HORADRIC_TALK_AFTER_CHURCH_UPGRADE"]
        beer = data.events["EVENT_HORADRIC_GIVE_GOLD_BEER"]

        self.assertEqual(
            ["EVENT_KREZVOLD_COMPLETE_SLIME_QUEST"],
            list(slimes.required_quests),
        )
        self.assertEqual(2, len(slimes.rewards))
        self.assertEqual(
            ["EVENT_BISHOP_UPGRADE_TO_BIG_CHURCH"],
            list(church.required_quests),
        )
        self.assertEqual(1, len(church.rewards))
        self.assertEqual(
            ["EVENT_INQUISITOR_HOST_FIRST_BUFFET_BURNING"],
            list(beer.required_quests),
        )
        self.assertEqual(["ITEM_A_MUG_OF_BEER_GOLD"], list(beer.required_craft_items))
        self.assertEqual(1, len(beer.rewards))

        horadric_happiness = data.items["ITEM_HORADRIC_HAPPINESS_10"]
        self.assertEqual(ItemClassification.progression, horadric_happiness.classification)
        self.assertEqual(10, horadric_happiness.amount)

        dead_horse = data.regions["REGION_THE_DEAD_HORSE"]
        for event_name, event in (
            ("EVENT_HORADRIC_COLLECT_SLIME_QUEST_REWARD", slimes),
            ("EVENT_HORADRIC_TALK_AFTER_CHURCH_UPGRADE", church),
            ("EVENT_HORADRIC_GIVE_GOLD_BEER", beer),
        ):
            with self.subTest(event=event_name):
                self.assertIn(event_name, dead_horse.events)
                for reward in event.rewards:
                    self.assertIn(reward, dead_horse.locations)
                    self.assertEqual("REGION_THE_DEAD_HORSE", data.locations[reward].parent_region)

        node_names = load_json_data("quest_node_names.json")
        expected_names = {
            "npc_tavern owner:350": slimes.location_label,
            "npc_tavern owner:361": slimes.location_label,
            "npc_tavern owner:468": church.location_label,
            "npc_tavern owner:13:option:7": beer.location_label,
        }
        for node_id, expected_name in expected_names.items():
            with self.subTest(node_id=node_id):
                self.assertEqual(expected_name, node_names[node_id])

    def test_merchant_quest_craft_abstractions_have_verified_recipes(self):
        dinner = data.recipes["ITEM_DINNER_GOLD"]
        crate = data.recipes["ITEM_TRADE_CRATE"]

        self.assertEqual(20, len(dinner))
        self.assertTrue(all(isinstance(recipe, QualityRecipeData) for recipe in dinner))
        self.assertTrue(all(recipe.crafting_group is CraftingGroup.Food for recipe in dinner))
        self.assertTrue(all(
            set(recipe.workstations) == {"CRAFTING_STATION_COOKING_TABLE"}
            for recipe in dinner
        ))
        categories = ("SNACK", "MEAL", "DESSERT")

        def ingredients_for(qualities):
            return frozenset(
                f"MATERIAL_DINNER_{quality}_{category}"
                for quality, category in zip(qualities, categories)
            )

        quality_values = {"ZERO": 0, "COPPER": 1, "SILVER": 2, "GOLD": 3}
        base_modifiers = {
            6: 0.3,
            7: 0.6333333333333333,
            8: 0.9666666666666667,
            9: 1.3,
        }
        expected_dinner_paths = {
            ingredients_for(qualities): base_modifiers[quality_sum]
            for qualities in product(quality_values, repeat=3)
            if (quality_sum := sum(quality_values[quality] for quality in qualities)) >= 6
        }
        self.assertEqual(
            expected_dinner_paths,
            {frozenset(recipe.ingredients): recipe.base_modifier for recipe in dinner},
        )
        self.assertIn(
            {
                "MATERIAL_DINNER_SILVER_SNACK",
                "MATERIAL_DINNER_GOLD_MEAL",
                "MATERIAL_DINNER_SILVER_DESSERT",
            },
            [set(recipe.ingredients) for recipe in dinner],
        )
        self.assertEqual(
            {"ITEM_ONION_RINGS_GOLD", "ITEM_TOASTS_WITH_ONIONS_GOLD"},
            {next(iter(recipe.ingredients)) for recipe in data.recipes["MATERIAL_DINNER_GOLD_SNACK"]},
        )
        self.assertIn(
            {"ITEM_PANCAKES"},
            [set(recipe.ingredients) for recipe in data.recipes["MATERIAL_DINNER_SILVER_SNACK"]],
        )
        self.assertIn(
            {"ITEM_CAKE"},
            [set(recipe.ingredients) for recipe in data.recipes["MATERIAL_DINNER_GOLD_DESSERT"]],
        )
        self.assertIn(
            {"ITEM_GRAPE_PIE_GOLD"},
            [set(recipe.ingredients) for recipe in data.recipes["MATERIAL_DINNER_GOLD_DESSERT"]],
        )
        self.assertGreaterEqual(len(data.recipes["MATERIAL_DINNER_GOLD_MEAL"]), 10)
        for quality in quality_values:
            for category in categories:
                component_key = f"MATERIAL_DINNER_{quality}_{category}"
                self.assertTrue(all(
                    all(not ingredient.startswith("MATERIAL_DINNER_") for ingredient in recipe.ingredients)
                    for recipe in data.recipes[component_key]
                ), component_key)
        self.assertEqual(1, len(crate))
        self.assertEqual({"ITEM_NAILS", "ITEM_FLITCH"}, set(crate[0].ingredients))
        self.assertEqual({"CRAFTING_STATION_CRATE_FACTORY"}, set(crate[0].workstations))

    def test_bishop_base_game_questline_matches_flow_requirements(self):
        meet = data.events["EVENT_BISHOP_MEET"]
        church_open = data.events["EVENT_CHURCH_OPEN"]
        ask_bowls = data.events["EVENT_BISHOP_ASK_ABOUT_SOUP_KITCHEN"]
        bowls = data.events["EVENT_BISHOP_GIVE_CERAMIC_BOWLS"]
        graveyard = data.events["EVENT_BISHOP_IMPROVE_GRAVEYARD"]
        church = data.events["EVENT_BISHOP_IMPROVE_CHURCH"]
        fish = data.events["EVENT_BISHOP_GIVE_QUALITY_FISH_FILLET"]
        big_church = data.events["EVENT_BISHOP_UPGRADE_TO_BIG_CHURCH"]
        citizen = data.events["EVENT_BISHOP_GIVE_RIGHTFUL_CITIZEN_PAPERS"]
        ask_cathedral = data.events["EVENT_BISHOP_ASK_ABOUT_CATHEDRAL"]
        cathedral_church = data.events["EVENT_BISHOP_IMPROVE_CHURCH_FOR_CATHEDRAL"]
        cathedral_graveyard = data.events["EVENT_BISHOP_IMPROVE_GRAVEYARD_FOR_CATHEDRAL"]
        statue = data.events["EVENT_BISHOP_BUILD_STATUE"]
        report_cathedral = data.events["EVENT_BISHOP_REPORT_CATHEDRAL_UPGRADE"]
        aristocrat = data.events["EVENT_BISHOP_SHOW_ARISTOCRAT_PAPERS"]
        invitation = data.events["EVENT_BISHOP_GIVE_ACCEPTED_INVITATION"]
        ceremony = data.events["EVENT_BISHOP_HOLD_FINAL_CEREMONY"]
        ask_artifact = data.events["EVENT_BISHOP_ASK_ABOUT_PORTAL_ARTIFACT"]
        artifact = data.events["EVENT_BISHOP_HAND_OVER_PORTAL_ARTIFACT"]

        node_names = load_json_data("quest_node_names.json")
        for node_id in ("final_ceremony:170", "final_ceremony:172", "final_ceremony:185", "final_ceremony:187"):
            with self.subTest(node_id=node_id):
                self.assertEqual(ceremony.location_label, node_names[node_id])

        self.assertEqual([], list(meet.required_quests))
        self.assertEqual(1, len(meet.rewards))
        self.assertEqual(["EVENT_BISHOP_MEET"], list(church_open.required_quests))
        self.assertEqual({AreaPointData("OLD_GRAVEYARD", 5)}, set(church_open.required_area_points))
        self.assertEqual(2, len(church_open.rewards))
        self.assertEqual(["EVENT_CHURCH_OPEN"], list(ask_bowls.required_quests))
        self.assertEqual(["ITEM_CERAMIC_BOWLS"], list(bowls.required_craft_items))
        self.assertEqual(2, len(bowls.rewards))

        for branch in (graveyard, church, fish):
            self.assertEqual(["EVENT_BISHOP_GIVE_CERAMIC_BOWLS"], list(branch.required_quests))
            self.assertEqual(1, len(branch.rewards))
        self.assertEqual({AreaPointData("OLD_GRAVEYARD", 30)}, set(graveyard.required_area_points))
        self.assertEqual({AreaPointData("CHURCH", 20)}, set(church.required_area_points))
        self.assertEqual(["ITEM_QUALITY_FISH_FILLET_COPPER"], list(fish.required_craft_items))
        self.assertEqual(
            {
                "EVENT_BISHOP_IMPROVE_GRAVEYARD",
                "EVENT_BISHOP_IMPROVE_CHURCH",
                "EVENT_BISHOP_GIVE_QUALITY_FISH_FILLET",
            },
            set(big_church.required_quests),
        )
        self.assertEqual(["ITEM_BUILDING_PERMISSION"], list(big_church.required_quest_items))
        self.assertEqual(["ITEM_RIGHTFUL_CITIZEN_PAPERS"], list(citizen.required_quest_items))
        self.assertEqual(["EVENT_BISHOP_GIVE_RIGHTFUL_CITIZEN_PAPERS"], list(ask_cathedral.required_quests))

        self.assertEqual({AreaPointData("CHURCH", 50)}, set(cathedral_church.required_area_points))
        self.assertEqual({AreaPointData("OLD_GRAVEYARD", 200)}, set(cathedral_graveyard.required_area_points))
        self.assertEqual(
            ["EVENT_BISHOP_IMPROVE_CHURCH_FOR_CATHEDRAL"],
            list(statue.required_quests),
        )
        self.assertEqual(
            ["ITEM_A_CARVED_PIECE_OF_MARBLE_GOLD"],
            list(statue.required_craft_items),
        )
        self.assertEqual(
            {
                "EVENT_BISHOP_IMPROVE_CHURCH_FOR_CATHEDRAL",
                "EVENT_BISHOP_IMPROVE_GRAVEYARD_FOR_CATHEDRAL",
                "EVENT_BISHOP_BUILD_STATUE",
            },
            set(report_cathedral.required_quests),
        )
        self.assertEqual(
            [HappinessData("BISHOP", 70)],
            list(report_cathedral.required_happiness),
        )

        self.assertEqual(["ITEM_ARISTOCRAT_PAPERS"], list(aristocrat.required_quest_items))
        self.assertEqual(2, len(aristocrat.rewards))
        self.assertIn("EVENT_MERCHANT_INVITE_TO_FINAL_CEREMONY", invitation.required_quests)
        self.assertEqual(["ITEM_ACCEPTED_INVITATION"], list(invitation.required_quest_items))
        self.assertEqual(
            {"EVENT_BISHOP_SHOW_ARISTOCRAT_PAPERS", "EVENT_BISHOP_GIVE_ACCEPTED_INVITATION"},
            set(ceremony.required_quests),
        )
        self.assertEqual([HappinessData("BISHOP", 90)], list(ceremony.required_happiness))
        self.assertEqual(4, len(ceremony.rewards))
        self.assertEqual(
            ["EVENT_SNAKE_IDENTIFY_PORTAL_ARTIFACT_HOLDERS"],
            list(ask_artifact.required_quests),
        )
        self.assertEqual([HappinessData("BISHOP", 100)], list(artifact.required_happiness))
        self.assertEqual(1, len(artifact.rewards))

    def test_area_point_requirement_parser_rejects_invalid_values(self):
        for invalid_value in ("SACRIFICE_ZONE", "_20", "SACRIFICE_ZONE_0", "SACRIFICE_ZONE_-1"):
            with self.subTest(value=invalid_value):
                with self.assertRaises(ValueError):
                    AreaPointData.from_string(invalid_value)

    def test_better_call_soul_opening_chain_matches_flow_requirements(self):
        arrival = data.events["EVENT_EURIC_ARRIVE"]
        ask_key = data.events["EVENT_GERRY_ASK_ABOUT_OLD_RUSTY_KEY"]
        wash_gerry = data.events["EVENT_GERRY_WASH_WITH_BEER_AND_SAND"]
        open_room = data.events["EVENT_SOULS_ROOM_OPEN"]

        self.assertEqual(
            {"EVENT_BISHOP_GIVE_CERAMIC_BOWLS", "EVENT_CORPSE_HATCH_REPAIRED"},
            set(arrival.required_quests),
        )
        self.assertEqual(["ITEM_CORPSE"], list(arrival.required_craft_items))
        self.assertEqual(["EVENT_EURIC_ARRIVE"], list(ask_key.required_quests))
        self.assertEqual(["EVENT_GERRY_ASK_ABOUT_OLD_RUSTY_KEY"], list(wash_gerry.required_quests))
        self.assertEqual(
            {"ITEM_A_MUG_OF_BEER_COPPER", "ITEM_RIVER_SAND"},
            set(wash_gerry.required_craft_items),
        )
        self.assertEqual(
            ["LOCATION_GERRY_REWARD_GIVE_BEER_AND_SAND"],
            list(wash_gerry.rewards),
        )
        self.assertEqual(["EVENT_GERRY_WASH_WITH_BEER_AND_SAND"], list(open_room.required_quests))
        self.assertEqual(["ITEM_OLD_RUSTY_KEY"], list(open_room.required_quest_items))

    def test_better_call_soul_room_tutorial_has_parallel_seed_oil_and_pie_branches(self):
        smiler_appears = data.events["EVENT_SMILER_APPEARS"]
        open_hatch = data.events["EVENT_HATCH_REPAIRED"]
        give_pie = data.events["EVENT_SMILER_GIVE_BERRY_PIE"]

        self.assertEqual(["EVENT_SOULS_ROOM_OPEN"], list(smiler_appears.required_quests))
        self.assertEqual(["EVENT_SMILER_APPEARS"], list(open_hatch.required_quests))
        self.assertEqual(["ITEM_SEED_OIL"], list(open_hatch.required_craft_items))
        self.assertEqual(["EVENT_SMILER_APPEARS"], list(give_pie.required_quests))
        self.assertEqual(["ITEM_BERRY_PIE"], list(give_pie.required_craft_items))
        self.assertEqual([], list(open_hatch.rewards))
        self.assertEqual([], list(give_pie.rewards))

    def test_better_call_soul_euric_room_repairs_preserve_both_rewards(self):
        repair_bed = data.events["EVENT_EURIC_REPAIR_BED"]
        repair_furniture = data.events["EVENT_EURIC_REPAIR_FURNITURE"]
        return_tooth = data.events["EVENT_GERRY_ASK_ABOUT_THE_TOOTH"]

        self.assertEqual(["EVENT_HATCH_REPAIRED"], list(repair_bed.required_quests))
        self.assertEqual({"ITEM_FLITCH", "ITEM_NAILS"}, set(repair_bed.required_craft_items))
        self.assertEqual(["LOCATION_EURIC_REWARD_REPAIR_BED"], list(repair_bed.rewards))

        self.assertEqual(["EVENT_EURIC_REPAIR_BED"], list(repair_furniture.required_quests))
        self.assertEqual(
            {
                "ITEM_FLITCH",
                "ITEM_NAILS",
                "ITEM_WOODEN_PLANK",
                "ITEM_WOODEN_STICK",
                "ITEM_WOODEN_BEAM",
                "ITEM_SKIN",
            },
            set(repair_furniture.required_craft_items),
        )
        self.assertEqual(
            ["LOCATION_EURIC_REWARD_REPAIR_FURNITURE"],
            list(repair_furniture.rewards),
        )

        self.assertEqual(["EVENT_EURIC_REPAIR_BED"], list(return_tooth.required_quests))
        self.assertEqual(["ITEM_LOST_TOOTH"], list(return_tooth.required_quest_items))
        self.assertEqual([], list(return_tooth.rewards))

    def test_better_call_soul_human_soul_healing_blueprint_is_a_reward(self):
        unlock_healing = data.events["EVENT_SMILER_UNLOCK_HUMAN_SOUL_HEALING"]

        self.assertEqual(
            ["EVENT_SMILER_GIVE_BERRY_PIE"],
            list(unlock_healing.required_quests),
        )
        self.assertEqual(
            ["ITEM_UNLOCK_SPIRITUALISM"],
            list(unlock_healing.required_quest_items),
        )
        self.assertEqual([], list(unlock_healing.required_craft_items))
        self.assertEqual(
            ["LOCATION_SMILER_REWARD_ASK_ABOUT_HUMAN_HEALING"],
            list(unlock_healing.rewards),
        )

    def test_better_call_soul_first_healing_models_each_vanilla_reward(self):
        obtain_ode = data.events["EVENT_VAGNER_WRITE_ODE_FOR_BISHOP"]
        charge_shard = data.events["EVENT_BISHOP_CHARGE_PRIDE_SHARD"]
        heal_pride = data.events["EVENT_EURIC_HEAL_PRIDE"]

        self.assertEqual(
            ["EVENT_SMILER_UNLOCK_HUMAN_SOUL_HEALING"],
            list(obtain_ode.required_quests),
        )
        self.assertEqual(
            ["ITEM_BP_HUMAN_SOUL_HEALING"],
            list(obtain_ode.required_quest_items),
        )
        self.assertEqual(
            {
                "ITEM_FLITCH",
                "ITEM_GLASS",
                "ITEM_SIMPLE_IRON_PARTS",
                "ITEM_SKIN",
                "ITEM_WOODEN_PLANK",
                "ITEM_NAILS",
                "ITEM_COMPLEX_IRON_PARTS",
            },
            set(obtain_ode.required_craft_items),
        )
        self.assertEqual(
            ["LOCATION_REWARD_OBTAIN_ODE_FOR_BISHOP"],
            list(obtain_ode.rewards),
        )

        self.assertEqual(
            ["EVENT_VAGNER_WRITE_ODE_FOR_BISHOP"],
            list(charge_shard.required_quests),
        )
        self.assertEqual(["ITEM_ODE_FOR_BISHOP"], list(charge_shard.required_quest_items))
        self.assertEqual(["ITEM_SIN_SHARD"], list(charge_shard.required_craft_items))
        self.assertEqual(
            ["LOCATION_BISHOP_REWARD_RECITE_ODE"],
            list(charge_shard.rewards),
        )

        self.assertEqual(
            ["EVENT_BISHOP_CHARGE_PRIDE_SHARD"],
            list(heal_pride.required_quests),
        )
        self.assertEqual([HappinessData("EURIC", 10)], list(heal_pride.required_happiness))
        self.assertEqual(
            {"ITEM_PRIDE_CHARGED_SHARD", "ITEM_BP_EXTENSION_HEALING_FROM_PRIDE"},
            set(heal_pride.required_quest_items),
        )
        self.assertEqual(
            {"ITEM_CONICAL_FLASKS", "ITEM_SIMPLE_IRON_PARTS"},
            set(heal_pride.required_craft_items),
        )
        self.assertEqual(
            {
                "LOCATION_EURIC_REWARD_FIRST_HEALING_1",
                "LOCATION_EURIC_REWARD_FIRST_HEALING_2",
            },
            set(heal_pride.rewards),
        )

    def test_better_call_soul_second_healing_keeps_both_shard_branches_independent(self):
        give_honey = data.events["EVENT_CLOTHO_GIVE_HONEY_FOR_UNUSUAL_ASH"]
        charge_wrath = data.events["EVENT_INQUISITOR_CHARGE_WRATH_SHARD"]
        learn_sauce = data.events["EVENT_CLOTHO_TEACH_MYSTERIOUS_FOOD_SAUCE"]
        charge_gluttony = data.events["EVENT_MERCHANT_CHARGE_GLUTTONY_SHARD"]
        second_healing = data.events["EVENT_EURIC_HEAL_WRATH_AND_GLUTTONY"]

        self.assertEqual(["EVENT_EURIC_HEAL_PRIDE"], list(give_honey.required_quests))
        self.assertEqual(["ITEM_HONEY"], list(give_honey.required_craft_items))
        self.assertEqual(
            ["LOCATION_CLOTHO_REWARD_GIVE_HONEY"],
            list(give_honey.rewards),
        )
        self.assertEqual(
            ["EVENT_CLOTHO_GIVE_HONEY_FOR_UNUSUAL_ASH"],
            list(charge_wrath.required_quests),
        )
        self.assertEqual(["ITEM_UNUSUAL_ASH"], list(charge_wrath.required_quest_items))
        self.assertEqual(["ITEM_SIN_SHARD"], list(charge_wrath.required_craft_items))
        self.assertEqual(
            ["LOCATION_INQUISITOR_REWARD_SHOW_UNUSUAL_ASH"],
            list(charge_wrath.rewards),
        )

        self.assertEqual(["EVENT_EURIC_HEAL_PRIDE"], list(learn_sauce.required_quests))
        self.assertEqual([], list(learn_sauce.required_quest_items))
        self.assertEqual([], list(learn_sauce.required_craft_items))
        self.assertEqual(
            ["LOCATION_CLOTHO_REWARD_ASK_ABOUT_SAUCE"],
            list(learn_sauce.rewards),
        )
        self.assertEqual(
            ["EVENT_CLOTHO_TEACH_MYSTERIOUS_FOOD_SAUCE"],
            list(charge_gluttony.required_quests),
        )
        self.assertEqual([], list(charge_gluttony.required_quest_items))
        self.assertEqual(
            {"ITEM_MYSTERIOUS_FOOD_SAUCE", "ITEM_SIN_SHARD"},
            set(charge_gluttony.required_craft_items),
        )
        self.assertEqual(
            ["LOCATION_MERCHANT_REWARD_GIVE_MYSTERIOUS_FOOD_SAUCE"],
            list(charge_gluttony.rewards),
        )

        self.assertEqual(
            {
                "EVENT_INQUISITOR_CHARGE_WRATH_SHARD",
                "EVENT_MERCHANT_CHARGE_GLUTTONY_SHARD",
            },
            set(second_healing.required_quests),
        )
        self.assertEqual([], list(second_healing.required_happiness))
        self.assertEqual(
            {
                "ITEM_WRATH_CHARGED_SHARD",
                "ITEM_GLUTTONY_CHARGED_SHARD",
                "ITEM_BP_EXTENSION_HEALING_FROM_WRATH",
                "ITEM_BP_EXTENSION_HEALING_FROM_GLUTTONY",
            },
            set(second_healing.required_quest_items),
        )
        self.assertEqual(
            {"ITEM_CONICAL_FLASKS", "ITEM_SIMPLE_IRON_PARTS"},
            set(second_healing.required_craft_items),
        )
        self.assertEqual(
            ["LOCATION_EURIC_REWARD_SECOND_HEALING"],
            list(second_healing.rewards),
        )

    def test_better_call_soul_third_healing_keeps_all_shard_branches_independent(self):
        charge_sloth = data.events["EVENT_ASTROLOGER_CHARGE_SLOTH_SHARD"]
        charge_lust = data.events["EVENT_MS_CHARM_CHARGE_LUST_SHARD"]
        ask_for_envy = data.events["EVENT_EURIC_ASK_FOR_ENVY_SHARD"]
        charge_envy = data.events["EVENT_SNAKE_CHARGE_ENVY_SHARD"]
        third_healing = data.events["EVENT_EURIC_HEAL_SLOTH_LUST_AND_ENVY"]

        for event in (charge_sloth, charge_lust, ask_for_envy):
            with self.subTest(event=event.location_label):
                self.assertEqual(
                    ["EVENT_EURIC_HEAL_WRATH_AND_GLUTTONY"],
                    list(event.required_quests),
                )

        self.assertEqual(["ITEM_SIN_SHARD"], list(charge_sloth.required_craft_items))
        self.assertEqual(
            ["LOCATION_ASTROLOGER_REWARD_ASK_ABOUT_HIS_DAY"],
            list(charge_sloth.rewards),
        )
        self.assertEqual(["ITEM_SIN_SHARD"], list(charge_lust.required_craft_items))
        self.assertEqual(
            ["LOCATION_MS_CHARM_REWARD_PERSUADE_TO_DANCE"],
            list(charge_lust.rewards),
        )
        self.assertEqual([], list(ask_for_envy.required_quest_items))
        self.assertEqual([], list(ask_for_envy.required_craft_items))
        self.assertEqual(
            ["LOCATION_EURIC_REWARD_ASK_FOR_ENVY_SHARD"],
            list(ask_for_envy.rewards),
        )

        self.assertEqual(
            {"EVENT_EURIC_ASK_FOR_ENVY_SHARD", "EVENT_SNAKE_GIVE_ACTIVE_KEY"},
            set(charge_envy.required_quests),
        )
        self.assertEqual(["ITEM_NOTE_WITH_RUMOR"], list(charge_envy.required_quest_items))
        self.assertEqual(["ITEM_SIN_SHARD"], list(charge_envy.required_craft_items))
        self.assertEqual(
            ["LOCATION_SNAKE_REWARD_CHARGE_ENVY_SHARD"],
            list(charge_envy.rewards),
        )

        self.assertEqual(
            {
                "EVENT_ASTROLOGER_CHARGE_SLOTH_SHARD",
                "EVENT_MS_CHARM_CHARGE_LUST_SHARD",
                "EVENT_SNAKE_CHARGE_ENVY_SHARD",
            },
            set(third_healing.required_quests),
        )
        self.assertEqual([], list(third_healing.required_happiness))
        self.assertEqual(
            {
                "ITEM_SLOTH_CHARGED_SHARD",
                "ITEM_LUST_CHARGED_SHARD",
                "ITEM_ENVY_CHARGED_SHARD",
                "ITEM_BP_EXTENSION_HEALING_FROM_SLOTH",
                "ITEM_BP_EXTENSION_HEALING_FROM_LUST",
                "ITEM_BP_EXTENSION_HEALING_FROM_ENVY",
            },
            set(third_healing.required_quest_items),
        )
        self.assertEqual(
            {"ITEM_CONICAL_FLASKS", "ITEM_SIMPLE_IRON_PARTS"},
            set(third_healing.required_craft_items),
        )
        self.assertEqual(
            ["LOCATION_EURIC_REWARD_THIRD_HEALING"],
            list(third_healing.rewards),
        )

    def test_better_call_soul_smiler_finale_preserves_journal_page_gate(self):
        ask_smiler = data.events["EVENT_SMILER_ASK_ABOUT_HIS_DEATH"]
        ask_snake = data.events["EVENT_SNAKE_ASK_HOW_SMILER_DIED"]
        ask_gerry = data.events["EVENT_GERRY_ASK_ABOUT_PREVIOUS_KEEPERS_JOURNAL"]
        reveal_death = data.events["EVENT_SMILER_LEARN_HOW_HE_DIED"]
        pass_on = data.events["EVENT_SMILER_PASS_ON"]

        self.assertEqual(
            ["EVENT_EURIC_HEAL_SLOTH_LUST_AND_ENVY"],
            list(ask_smiler.required_quests),
        )
        self.assertEqual(
            ["EVENT_SMILER_ASK_ABOUT_HIS_DEATH"],
            list(ask_snake.required_quests),
        )
        self.assertEqual(
            ["EVENT_SNAKE_ASK_HOW_SMILER_DIED"],
            list(ask_gerry.required_quests),
        )
        self.assertEqual(
            ["LOCATION_GERRY_REWARD_ASK_ABOUT_PREVIOUS_KEEPERS_JOURNAL"],
            list(ask_gerry.rewards),
        )
        self.assertEqual(
            ["EVENT_GERRY_ASK_ABOUT_PREVIOUS_KEEPERS_JOURNAL"],
            list(reveal_death.required_quests),
        )
        self.assertEqual(
            ["ITEM_PREVIOUS_KEEPERS_JOURNAL_PAGE"],
            list(reveal_death.required_quest_items),
        )
        self.assertEqual(
            ["EVENT_SMILER_LEARN_HOW_HE_DIED"],
            list(pass_on.required_quests),
        )
        self.assertEqual([], list(pass_on.rewards))

    def test_better_call_soul_village_repairs_require_every_material_type(self):
        collect_gift = data.events["EVENT_TRESS_COLLECT_VILLAGE_REPAIR_GIFT"]

        self.assertEqual(
            ["EVENT_EURIC_HEAL_SLOTH_LUST_AND_ENVY"],
            list(collect_gift.required_quests),
        )
        self.assertEqual([], list(collect_gift.required_happiness))
        self.assertEqual([], list(collect_gift.required_quest_items))
        self.assertEqual(
            {
                "ITEM_FLITCH",
                "ITEM_NAILS",
                "ITEM_COMPLEX_IRON_PARTS",
                "ITEM_WOODEN_PLANK",
                "ITEM_WOOD_REPAIR_KIT",
                "ITEM_WOODEN_STICK",
                "ITEM_A_PIECE_OF_STONE",
                "ITEM_BEE",
                "ITEM_SIMPLE_IRON_PARTS",
                "ITEM_GLASS",
                "ITEM_HEMP_ROPE",
            },
            set(collect_gift.required_craft_items),
        )
        self.assertEqual(
            ["LOCATION_TRESS_REWARD_FOR_FIXING_THE_VILLAGE"],
            list(collect_gift.rewards),
        )

    def test_stained_glass_window_is_not_a_better_call_soul_quest_event(self):
        self.assertNotIn("EVENT_STAINED_GLASS_WINDOW_INSTALLED", data.events)
        self.assertNotIn(
            "EVENT_STAINED_GLASS_WINDOW_INSTALLED",
            data.regions["REGION_CHURCH"].events,
        )

    def test_teodoro_first_camp_expansion_models_actual_reward_triggers(self):
        first_stage = data.events["EVENT_TEODORO_BUILD_FIRST_WELL_AND_TENT"]
        second_stage = data.events["EVENT_TEODORO_BUILD_SECOND_TENT"]
        third_stage = data.events["EVENT_TEODORO_GROW_CAMP_TO_SEVEN_RESIDENTS"]

        self.assertEqual(["EVENT_CHURCH_OPEN"], list(first_stage.required_quests))
        self.assertEqual(
            {
                "ITEM_A_PIECE_OF_STONE",
                "ITEM_SIMPLE_IRON_PARTS",
                "ITEM_WOODEN_STICK",
                "ITEM_SILK",
            },
            set(first_stage.required_craft_items),
        )
        self.assertEqual(
            {AreaPointData("REFUGEE_CAMP", 3)},
            set(first_stage.required_area_points),
        )
        self.assertEqual(
            ["LOCATION_TEODORO_REWARD_BUILD_FIRST_WELL_AND_TENT"],
            list(first_stage.rewards),
        )

        self.assertEqual(
            ["EVENT_TEODORO_BUILD_FIRST_WELL_AND_TENT"],
            list(second_stage.required_quests),
        )
        self.assertEqual(
            {"ITEM_WOODEN_STICK", "ITEM_SILK"},
            set(second_stage.required_craft_items),
        )
        self.assertEqual(
            {AreaPointData("REFUGEE_CAMP", 5)},
            set(second_stage.required_area_points),
        )
        self.assertEqual(
            ["LOCATION_TEODORO_REWARD_BUILD_SECOND_TENT"],
            list(second_stage.rewards),
        )

        self.assertEqual(
            ["EVENT_TEODORO_BUILD_SECOND_TENT"],
            list(third_stage.required_quests),
        )
        self.assertEqual([], list(third_stage.required_craft_items))
        self.assertEqual(
            {AreaPointData("REFUGEE_CAMP", 2)},
            set(third_stage.required_area_points),
        )
        self.assertEqual(
            ["LOCATION_TEODORO_REWARD_GROW_CAMP_TO_SEVEN_RESIDENTS"],
            list(third_stage.rewards),
        )

        node_names = load_json_data("quest_node_names.json")
        self.assertEqual(first_stage.location_label, node_names["npc_teodoro:961"])
        self.assertEqual(second_stage.location_label, node_names["npc_teodoro:1002"])
        for node_id in ("npc_teodoro:1062", "npc_teodoro:1076", "npc_teodoro:1095", "npc_teodoro:1140"):
            with self.subTest(node_id=node_id):
                self.assertEqual(third_stage.location_label, node_names[node_id])

    def test_early_alarich_rewards_fold_mandatory_investigation_and_model_blood_route(self):
        confrontation = data.events["EVENT_ALARICH_CONFRONT_ABOUT_VAMPIRE_ATTACKS"]
        revival = data.events["EVENT_ALARICH_REVIVE_WITH_BLOOD"]

        self.assertEqual(["EVENT_CHURCH_OPEN"], list(confrontation.required_quests))
        self.assertEqual([], list(confrontation.required_quest_items))
        self.assertEqual([], list(confrontation.required_craft_items))
        self.assertEqual(
            ["LOCATION_ALARICH_REWARD_CONFRONT_ABOUT_VAMPIRE_ATTACKS"],
            list(confrontation.rewards),
        )

        self.assertEqual(
            ["EVENT_ALARICH_CONFRONT_ABOUT_VAMPIRE_ATTACKS"],
            list(revival.required_quests),
        )
        self.assertEqual([], list(revival.required_quest_items))
        self.assertEqual(["ITEM_BLOOD"], list(revival.required_craft_items))
        self.assertEqual(
            ["LOCATION_ALARICH_REWARD_REVIVE_WITH_BLOOD"],
            list(revival.rewards),
        )

        node_names = load_json_data("quest_node_names.json")
        self.assertEqual(
            confrontation.location_label,
            node_names["npc_alarich:21:option:9"],
        )
        for node_id in ("npc_alarich:1163", "npc_alarich:1174"):
            with self.subTest(node_id=node_id):
                self.assertEqual(revival.location_label, node_names[node_id])

    def test_teodoro_second_camp_expansion_models_parallel_entry_and_reward_triggers(self):
        first_stage = data.events[
            "EVENT_TEODORO_UPGRADE_DEPOT_CAMPFIRE_AND_BUILD_SIXTH_TENT"
        ]
        second_stage = data.events["EVENT_TEODORO_BUILD_SEVENTH_TENT_AND_WORKPLACE"]
        third_stage = data.events["EVENT_TEODORO_GROW_CAMP_TO_ELEVEN_RESIDENTS"]

        self.assertEqual(
            {
                "EVENT_ALARICH_REVIVE_WITH_BLOOD",
                "EVENT_TEODORO_GROW_CAMP_TO_SEVEN_RESIDENTS",
            },
            set(first_stage.required_quests),
        )
        self.assertEqual(
            {
                "ITEM_FLITCH",
                "ITEM_SILK",
                "ITEM_A_POLISHED_BRICK_OF_STONE",
                "ITEM_WOODEN_STICK",
            },
            set(first_stage.required_craft_items),
        )
        self.assertEqual(
            {AreaPointData("REFUGEE_CAMP", 8)},
            set(first_stage.required_area_points),
        )
        self.assertEqual(
            ["LOCATION_TEODORO_REWARD_UPGRADE_DEPOT_CAMPFIRE_AND_BUILD_SIXTH_TENT"],
            list(first_stage.rewards),
        )

        self.assertEqual(
            ["EVENT_TEODORO_UPGRADE_DEPOT_CAMPFIRE_AND_BUILD_SIXTH_TENT"],
            list(second_stage.required_quests),
        )
        self.assertEqual(
            {"ITEM_WOODEN_STICK", "ITEM_SILK", "ITEM_WOODEN_PLANK", "ITEM_NAILS"},
            set(second_stage.required_craft_items),
        )
        self.assertEqual(
            {AreaPointData("REFUGEE_CAMP", 10)},
            set(second_stage.required_area_points),
        )
        self.assertEqual(
            ["LOCATION_TEODORO_REWARD_BUILD_SEVENTH_TENT_AND_WORKPLACE"],
            list(second_stage.rewards),
        )

        self.assertEqual(
            ["EVENT_TEODORO_BUILD_SEVENTH_TENT_AND_WORKPLACE"],
            list(third_stage.required_quests),
        )
        self.assertEqual([], list(third_stage.required_craft_items))
        self.assertEqual(
            {AreaPointData("REFUGEE_CAMP", 2)},
            set(third_stage.required_area_points),
        )
        self.assertEqual(
            ["LOCATION_TEODORO_REWARD_GROW_CAMP_TO_ELEVEN_RESIDENTS"],
            list(third_stage.rewards),
        )

        node_names = load_json_data("quest_node_names.json")
        self.assertEqual(first_stage.location_label, node_names["npc_teodoro:1241"])
        self.assertEqual(second_stage.location_label, node_names["npc_teodoro:1302"])
        for node_id in (
            "npc_teodoro:1348",
            "npc_teodoro:1362",
            "npc_teodoro:1376",
            "npc_teodoro:1390",
            "npc_teodoro:1406",
            "npc_teodoro:1435",
        ):
            with self.subTest(node_id=node_id):
                self.assertEqual(third_stage.location_label, node_names[node_id])

    def test_clotho_vampire_jaw_reward_folds_memory_search_and_requires_both_quest_items(self):
        event = data.events["EVENT_CLOTHO_EXAMINE_VAMPIRES_JAW"]

        self.assertEqual(
            {
                "EVENT_ALARICH_REVIVE_WITH_BLOOD",
                "EVENT_TEODORO_GROW_CAMP_TO_SEVEN_RESIDENTS",
            },
            set(event.required_quests),
        )
        self.assertEqual(
            {"ITEM_WITCHERS_EYE", "ITEM_VAMPIRES_JAW"},
            set(event.required_quest_items),
        )
        self.assertEqual([], list(event.required_craft_items))
        self.assertEqual(
            ["LOCATION_CLOTHO_REWARD_EXAMINE_VAMPIRES_JAW"],
            list(event.rewards),
        )

        node_names = load_json_data("quest_node_names.json")
        self.assertEqual(event.location_label, node_names["npc_witch:9:option:14"])

    def test_misty_quagmire_models_parallel_clotho_exposition_and_both_dig_rewards(self):
        event = data.events["EVENT_TEODORO_EXPLORE_MISTY_QUAGMIRE"]

        self.assertEqual(DLCType.GAME_OF_CRONE, event.dlc)
        self.assertEqual(
            {
                "EVENT_DONKEY_TAKE_HAIR",
                "EVENT_TEODORO_GROW_CAMP_TO_ELEVEN_RESIDENTS",
            },
            set(event.required_quests),
            "The Pagan-amulet story and second camp finale independently gate Teodoro's trip",
        )
        self.assertNotIn(
            "EVENT_CLOTHO_ASK_ABOUT_MISTY_QUAGMIRE",
            event.required_quests,
            "Clotho's dialogue is optional exposition unlocked in parallel with Teodoro's task",
        )
        self.assertEqual(["ITEM_WITCHERS_EYE"], list(event.required_quest_items))
        self.assertEqual(
            ["ITEM_PAGAN_AMULET_OF_SPIRIT_SUMMONING"],
            list(event.required_craft_items),
        )
        self.assertEqual(
            {
                "LOCATION_MISTY_QUAGMIRE_REWARD_UNEARTH_BONE_LEG",
                "LOCATION_MISTY_QUAGMIRE_REWARD_UNEARTH_CHARRED_VAMPIRE_SHOE",
            },
            set(event.rewards),
            "The two guaranteed dig piles are separate randomized checks",
        )

        raw_quest_items = load_json_data("items/quest/items.json")
        for item_key in ("ITEM_BONE_LEG", "ITEM_CHARRED_VAMPIRE_SHOE"):
            with self.subTest(item=item_key):
                self.assertEqual(
                    ItemClassification.progression,
                    data.items[item_key].classification,
                )
                self.assertEqual("GAME_OF_CRONE", raw_quest_items[item_key]["dlc"])

        for location_key in event.rewards:
            with self.subTest(location=location_key):
                self.assertEqual("REGION_SWAMP", data.locations[location_key].parent_region)

        node_names = load_json_data("quest_node_names.json")
        self.assertEqual(
            "Ask Clotho about Misty Quagmire",
            node_names["npc_witch:9:option:15"],
        )
        self.assertEqual(
            "Travel to Misty Quagmire with Teodoro",
            node_names["npc_teodoro:17:option:3"],
        )
        self.assertEqual(
            "Unearth the bone leg at Misty Quagmire",
            node_names["refugee_purple_cloud:289"],
        )
        self.assertEqual(
            "Unearth the charred vampire shoe at Misty Quagmire",
            node_names["refugee_purple_cloud:358"],
        )

    def test_third_refugee_camp_stage_models_defenses_materials_and_area_points(self):
        stakes = data.events["EVENT_TEODORO_BUILD_DEFENSIVE_STAKES"]
        swords = data.events["EVENT_TEODORO_BUILD_SWORD_RACK"]
        tower = data.events["EVENT_TEODORO_BUILD_OBSERVATION_TOWER"]

        for event in (stakes, swords, tower):
            with self.subTest(event=event.location_label):
                self.assertEqual(DLCType.GAME_OF_CRONE, event.dlc)
                self.assertEqual(1, len(event.rewards))
                self.assertEqual(
                    "REGION_REFUGEE_CAMP",
                    data.locations[next(iter(event.rewards))].parent_region,
                )

        self.assertEqual(
            {
                "EVENT_DONKEY_TAKE_HAIR",
                "EVENT_TEODORO_GROW_CAMP_TO_ELEVEN_RESIDENTS",
            },
            set(stakes.required_quests),
            "The guards require both the Pagan-amulet investigation and city stage two",
        )
        self.assertEqual(
            {
                "ITEM_PAGAN_AMULET_OF_SPIRIT_SUMMONING",
                "ITEM_FLITCH",
                "ITEM_WOODEN_STICK",
            },
            set(stakes.required_craft_items),
        )
        self.assertEqual([AreaPointData("REFUGEE_CAMP", 11)], list(stakes.required_area_points))

        self.assertEqual(
            ["EVENT_TEODORO_BUILD_DEFENSIVE_STAKES"],
            list(swords.required_quests),
        )
        self.assertEqual(
            {"ITEM_STEEL_SWORD", "ITEM_FLITCH"},
            set(swords.required_craft_items),
        )
        self.assertEqual([AreaPointData("REFUGEE_CAMP", 12)], list(swords.required_area_points))

        self.assertEqual(
            ["EVENT_TEODORO_BUILD_SWORD_RACK"],
            list(tower.required_quests),
        )
        self.assertEqual(
            {"ITEM_WOODEN_BEAM", "ITEM_FLITCH"},
            set(tower.required_craft_items),
        )
        self.assertEqual([AreaPointData("REFUGEE_CAMP", 13)], list(tower.required_area_points))

        node_names = load_json_data("quest_node_names.json")
        self.assertEqual(stakes.location_label, node_names["npc_teodoro:1538"])
        self.assertEqual(swords.location_label, node_names["npc_teodoro:1588"])
        for node_id in (
            "refugee_ev_city_3_fin:55",
            "refugee_ev_city_3_fin:69",
            "refugee_ev_city_3_fin:83",
            "refugee_ev_city_3_fin:97",
            "refugee_ev_city_3_fin:111",
            "refugee_ev_city_3_fin:125",
            "refugee_ev_city_3_fin:255",
        ):
            with self.subTest(node_id=node_id):
                self.assertEqual(tower.location_label, node_names[node_id])

    def test_alarich_vampire_clan_report_folds_rewardless_investigation_but_not_bone_leg(self):
        event = data.events["EVENT_ALARICH_REPORT_VAMPIRE_QUEEN_MEMORIES"]

        self.assertEqual(DLCType.GAME_OF_CRONE, event.dlc)
        self.assertEqual(
            ["EVENT_TEODORO_EXPLORE_MISTY_QUAGMIRE"],
            list(event.required_quests),
        )
        self.assertEqual(
            ["ITEM_CHARRED_VAMPIRE_SHOE"],
            list(event.required_quest_items),
            "Only the shoe continues the main story; returning the bone leg is a side task",
        )
        self.assertNotIn("ITEM_BONE_LEG", event.required_quest_items)
        self.assertEqual(["ITEM_MEMORY_TINCTURE"], list(event.required_craft_items))
        self.assertEqual(
            {
                "LOCATION_ALARICH_REWARD_REPORT_VAMPIRE_QUEEN_MEMORIES",
                "LOCATION_ALARICH_REWARD_ACCOMPANY_HIM_TO_CLOTHO",
                "LOCATION_ALARICH_REWARD_ENTER_CLOTHOS_MIND",
                "LOCATION_ALARICH_REWARD_COMPLETE_MEMORY_PUZZLE",
            },
            set(event.rewards),
            "Both item drops and both Alarich relation gains are randomized checks",
        )
        for location_key in event.rewards:
            with self.subTest(location=location_key):
                self.assertEqual(
                    "REGION_REFUGEE_CAMP",
                    data.locations[location_key].parent_region,
                )

        node_names = load_json_data("quest_node_names.json")
        self.assertEqual(
            event.location_label,
            node_names["npc_alarich:21:option:14"],
        )
        self.assertEqual(
            "Reveal the charred vampire shoe's memory",
            node_names["script-call:OnMemoryPotionUse.json:137"],
        )
        self.assertEqual(
            "Find Miss Chain by the sea",
            node_names["unlock:refugee_ev_s34_near_sea.json:120"],
        )
        self.assertEqual(
            "Accompany Alarich to Clotho",
            node_names["refugee_ev_s37:4"],
        )
        self.assertEqual(
            "Enter Clotho's mind with Alarich",
            node_names["refugee_ev_s38:249"],
        )
        self.assertEqual(
            "Complete Clotho's memory puzzle",
            node_names["refugee_ev_s38:142"],
        )

    def test_beatrice_routes_reconverge_before_teodoro_and_alarich_rewards(self):
        teodoro = data.events["EVENT_TEODORO_REPORT_CAMP_FATE"]
        alarich = data.events["EVENT_ALARICH_DISCUSS_CAMP_FATE"]

        self.assertEqual(
            {
                "EVENT_ALARICH_REPORT_VAMPIRE_QUEEN_MEMORIES",
                "EVENT_TEODORO_BUILD_OBSERVATION_TOWER",
            },
            set(teodoro.required_quests),
            "refugee_ev_s39 joins the completed memory and camp-building branches",
        )
        self.assertEqual([], list(teodoro.required_quest_items))
        self.assertEqual([], list(teodoro.required_craft_items))
        self.assertEqual(
            ["LOCATION_TEODORO_REWARD_REPORT_CAMP_FATE"],
            list(teodoro.rewards),
            "The simultaneous relation and item bundle is one AP check",
        )

        self.assertEqual(
            ["EVENT_TEODORO_REPORT_CAMP_FATE"],
            list(alarich.required_quests),
        )
        self.assertEqual(
            ["LOCATION_ALARICH_REWARD_DISCUSS_CAMP_FATE"],
            list(alarich.rewards),
        )
        for event in (teodoro, alarich):
            with self.subTest(event=event.location_label):
                self.assertEqual(DLCType.GAME_OF_CRONE, event.dlc)
                self.assertEqual(
                    "REGION_REFUGEE_CAMP",
                    data.locations[next(iter(event.rewards))].parent_region,
                )

        node_names = load_json_data("quest_node_names.json")
        self.assertEqual(teodoro.location_label, node_names["npc_teodoro:17:option:6"])
        self.assertEqual(alarich.location_label, node_names["npc_alarich:21:option:16"])

    def test_game_of_crone_repeatable_and_ending_rewards_have_graph_names(self):
        node_names = load_json_data("quest_node_names.json")
        expected_names = {
            "npc_alarich:21:option:11": "Trade a bucket of blood with Alarich",
            "npc_witch:9:option:18": "Buy memory powder from Clotho",
            "npc_hunchback:90:option:11": "Ask Koukol to steal Lady Beatrice's magic scroll",
            "npc_teodoro:17:option:11": "Tell Teodoro the refugees are safe",
            "npc_teodoro:1685:option:0": "Tell Teodoro the refugees are safe",
            "refugee_ev_s53_try_give_tech_scrolls:97": "Tell Teodoro the refugees are safe",
            "npc_alarich:21:option:18": "Say goodbye to Alarich after saving the refugees",
            "refugee_ev_s47_spawn_bodies:14": "Find Lady Beatrice's victims in the morgue",
        }

        for node_id, expected_name in expected_names.items():
            with self.subTest(node_id=node_id):
                self.assertEqual(expected_name, node_names[node_id])

    def test_game_of_crone_endings_share_one_reward_location(self):
        ending = data.events["EVENT_COMPLETE_GAME_OF_CRONE"]

        self.assertEqual(DLCType.GAME_OF_CRONE, ending.dlc)
        self.assertEqual(
            ["EVENT_TEODORO_REPORT_CAMP_FATE"],
            list(ending.required_quests),
            "Only requirements shared by all three endings belong on the combined check",
        )
        self.assertEqual([], list(ending.required_quest_items))
        self.assertEqual([], list(ending.required_craft_items))
        self.assertEqual(
            ["LOCATION_GAME_OF_CRONE_REWARD_COMPLETE_STORY"],
            list(ending.rewards),
        )
        self.assertEqual(
            "REGION_REFUGEE_CAMP",
            data.locations["LOCATION_GAME_OF_CRONE_REWARD_COMPLETE_STORY"].parent_region,
        )

    def test_donkey_revolution_through_second_shipment_and_hair_join_matches_flow(self):
        cookbook = data.events["EVENT_DONKEY_SEND_COOKBOOK"]
        apples = data.events["EVENT_DONKEY_SEND_RED_APPLES"]
        first_shipment = data.events["EVENT_DONKEY_COLLECT_FIRST_REVOLUTIONARY_SHIPMENT"]
        aphorisms = data.events["EVENT_DONKEY_SEND_APHORISMS"]
        faith = data.events["EVENT_DONKEY_SEND_FAITH"]
        second_shipment = data.events["EVENT_DONKEY_COLLECT_SECOND_REVOLUTIONARY_SHIPMENT"]
        hair = data.events["EVENT_DONKEY_TAKE_HAIR"]

        for delivery, supplied_item, reward in (
            (
                cookbook,
                "ITEM_COOKBOOK",
                "LOCATION_DONKEY_REWARD_SEND_COOKBOOK",
            ),
            (
                apples,
                "ITEM_RED_APPLE",
                "LOCATION_DONKEY_REWARD_SEND_RED_APPLES",
            ),
        ):
            with self.subTest(delivery=delivery.item_label):
                self.assertEqual(["EVENT_CHURCH_OPEN"], list(delivery.required_quests))
                self.assertEqual(
                    {"ITEM_SEED_OIL", "ITEM_CARROT", supplied_item},
                    set(delivery.required_craft_items),
                    "Donkey's DLC quest starts only after both halves of his base-game strike",
                )
                self.assertEqual([reward], list(delivery.rewards))

        self.assertEqual(
            {"EVENT_DONKEY_SEND_COOKBOOK", "EVENT_DONKEY_SEND_RED_APPLES"},
            set(first_shipment.required_quests),
            "Both parallel deliveries increment the counter that unlocks the first message",
        )
        self.assertEqual([], list(first_shipment.required_quest_items))
        self.assertEqual([], list(first_shipment.required_craft_items))
        self.assertEqual(
            {
                "LOCATION_DONKEY_REWARD_COLLECT_FIRST_REVOLUTIONARY_MESSAGE",
                "LOCATION_DONKEY_REWARD_COLLECT_GOLD_JEWELRY",
                "LOCATION_DONKEY_REWARD_COLLECT_BANK_CHECKS",
            },
            set(first_shipment.rewards),
        )

        for delivery, supplied_item, reward in (
            (
                aphorisms,
                "ITEM_APHORISMS_ABOUT_THE_EVILS_OF_MONEY",
                "LOCATION_DONKEY_REWARD_SEND_APHORISMS",
            ),
            (faith, "ITEM_FAITH", "LOCATION_DONKEY_REWARD_SEND_FAITH"),
        ):
            with self.subTest(delivery=delivery.item_label):
                self.assertEqual(
                    ["EVENT_DONKEY_COLLECT_FIRST_REVOLUTIONARY_SHIPMENT"],
                    list(delivery.required_quests),
                )
                self.assertEqual(
                    ["ITEM_REVOLUTIONARY_MESSAGE_1"],
                    list(delivery.required_quest_items),
                )
                self.assertEqual([supplied_item], list(delivery.required_craft_items))
                self.assertEqual([reward], list(delivery.rewards))

        self.assertEqual(
            {"EVENT_DONKEY_SEND_APHORISMS", "EVENT_DONKEY_SEND_FAITH"},
            set(second_shipment.required_quests),
            "Both parallel deliveries increment the counter that unlocks the second message",
        )
        self.assertEqual(
            {
                "LOCATION_DONKEY_REWARD_COLLECT_SECOND_REVOLUTIONARY_MESSAGE",
                "LOCATION_DONKEY_REWARD_COLLECT_COMPONENTS",
            },
            set(second_shipment.rewards),
        )

        self.assertEqual(
            {
                "EVENT_CLOTHO_EXAMINE_VAMPIRES_JAW",
                "EVENT_DONKEY_COLLECT_SECOND_REVOLUTIONARY_SHIPMENT",
            },
            set(hair.required_quests),
            "The hair drops only after both the vampire investigation and Donkey's D6 milestone",
        )
        self.assertEqual(
            {"ITEM_VAMPIRES_JAW", "ITEM_REVOLUTIONARY_MESSAGE_2"},
            set(hair.required_quest_items),
        )
        self.assertEqual(["ITEM_MEMORY_TINCTURE"], list(hair.required_craft_items))
        self.assertEqual(["LOCATION_DONKEY_REWARD_TAKE_HAIR"], list(hair.rewards))

        node_names = load_json_data("quest_node_names.json")
        for node_id in ("refugee_ev_s22:35", "refugee_ev_d6:76"):
            with self.subTest(node_id=node_id):
                self.assertEqual(hair.location_label, node_names[node_id])
        self.assertEqual(
            first_shipment.location_label,
            node_names["contraband_box:12"],
        )
        self.assertEqual(
            second_shipment.location_label,
            node_names["contraband_box:63"],
        )

    def test_donkey_revolution_from_second_shipment_to_finale_matches_flow(self):
        enchant_pumpkin = data.events["EVENT_CLOTHO_ENCHANT_DONKEYS_PUMPKIN"]
        make_equipment = data.events["EVENT_KREZVOLD_MAKE_DONKEY_COMBAT_EQUIPMENT"]
        send_pumpkin = data.events["EVENT_DONKEY_SEND_MAGIC_PUMPKIN"]
        send_equipment = data.events["EVENT_DONKEY_SEND_COMBAT_EQUIPMENT"]
        third_message = data.events["EVENT_DONKEY_COLLECT_THIRD_REVOLUTIONARY_MESSAGE"]
        send_paint = data.events["EVENT_DONKEY_SEND_PAINT_CANS"]
        send_jelly = data.events["EVENT_DONKEY_SEND_JELLY_OF_INCREDIBLE_POWER"]
        send_banner = data.events["EVENT_DONKEY_SEND_REVOLUTIONARY_BANNER"]
        finale = data.events["EVENT_DONKEY_FINISH_REVOLUTION"]

        self.assertEqual(
            ["EVENT_DONKEY_COLLECT_SECOND_REVOLUTIONARY_SHIPMENT"],
            list(enchant_pumpkin.required_quests),
        )
        self.assertEqual(
            ["ITEM_REVOLUTIONARY_MESSAGE_2"],
            list(enchant_pumpkin.required_quest_items),
        )
        self.assertEqual(["ITEM_PUMPKIN_GOLD"], list(enchant_pumpkin.required_craft_items))
        self.assertEqual(
            ["LOCATION_CLOTHO_REWARD_ENCHANT_DONKEYS_PUMPKIN"],
            list(enchant_pumpkin.rewards),
        )

        self.assertEqual(
            ["EVENT_DONKEY_COLLECT_SECOND_REVOLUTIONARY_SHIPMENT"],
            list(make_equipment.required_quests),
        )
        self.assertEqual(
            {"ITEM_REVOLUTIONARY_MESSAGE_2", "ITEM_PILE_OF_COMPONENTS"},
            set(make_equipment.required_quest_items),
        )
        self.assertEqual([], list(make_equipment.required_craft_items))
        self.assertEqual(
            {
                "LOCATION_KREZVOLD_REWARD_MAKE_DONKEY_UNICORN_HORNS",
                "LOCATION_KREZVOLD_REWARD_MAKE_DONKEY_BATTLE_HORSESHOES",
            },
            set(make_equipment.rewards),
        )

        for delivery, predecessor, quest_items, reward in (
            (
                send_pumpkin,
                "EVENT_CLOTHO_ENCHANT_DONKEYS_PUMPKIN",
                {"ITEM_MAGIC_PUMPKIN"},
                "LOCATION_DONKEY_REWARD_SEND_MAGIC_PUMPKIN",
            ),
            (
                send_equipment,
                "EVENT_KREZVOLD_MAKE_DONKEY_COMBAT_EQUIPMENT",
                {"ITEM_BATTLE_HORSESHOES", "ITEM_IRON_UNICORN_HORNS"},
                "LOCATION_DONKEY_REWARD_SEND_COMBAT_EQUIPMENT",
            ),
        ):
            with self.subTest(delivery=delivery.item_label):
                self.assertEqual([predecessor], list(delivery.required_quests))
                self.assertEqual(quest_items, set(delivery.required_quest_items))
                self.assertEqual([], list(delivery.required_craft_items))
                self.assertEqual([reward], list(delivery.rewards))

        self.assertEqual(
            {"EVENT_DONKEY_SEND_MAGIC_PUMPKIN", "EVENT_DONKEY_SEND_COMBAT_EQUIPMENT"},
            set(third_message.required_quests),
            "Both second-phase deliveries increment the counter that unlocks the third message",
        )
        self.assertEqual([], list(third_message.required_quest_items))
        self.assertEqual(
            ["LOCATION_DONKEY_REWARD_COLLECT_THIRD_REVOLUTIONARY_MESSAGE"],
            list(third_message.rewards),
        )

        for delivery, craft_items, reward in (
            (
                send_paint,
                {"ITEM_BLACK_PAINT", "ITEM_WHITE_PAINT"},
                "LOCATION_DONKEY_REWARD_SEND_PAINT_CANS",
            ),
            (
                send_jelly,
                {"ITEM_JELLY_OF_INCREDIBLE_POWER"},
                "LOCATION_DONKEY_REWARD_SEND_JELLY_OF_INCREDIBLE_POWER",
            ),
            (
                send_banner,
                {"ITEM_REVOLUTIONARY_DONKEY_BANNER"},
                "LOCATION_DONKEY_REWARD_SEND_REVOLUTIONARY_BANNER",
            ),
        ):
            with self.subTest(delivery=delivery.item_label):
                self.assertEqual(
                    ["EVENT_DONKEY_COLLECT_THIRD_REVOLUTIONARY_MESSAGE"],
                    list(delivery.required_quests),
                )
                self.assertEqual(
                    ["ITEM_REVOLUTIONARY_MESSAGE_3"],
                    list(delivery.required_quest_items),
                )
                self.assertEqual(craft_items, set(delivery.required_craft_items))
                self.assertEqual([reward], list(delivery.rewards))

        self.assertEqual(
            {
                "EVENT_DONKEY_SEND_PAINT_CANS",
                "EVENT_DONKEY_SEND_JELLY_OF_INCREDIBLE_POWER",
                "EVENT_DONKEY_SEND_REVOLUTIONARY_BANNER",
            },
            set(finale.required_quests),
            "All three final deliveries increment the counter that starts the finale",
        )
        self.assertEqual([], list(finale.required_quest_items))
        self.assertEqual([], list(finale.required_craft_items))
        self.assertEqual(
            {
                "LOCATION_DONKEY_REWARD_FINISH_REVOLUTION_ICE_AXE",
                "LOCATION_DONKEY_REWARD_FINISH_REVOLUTION_RELATION",
            },
            set(finale.rewards),
        )

        for item_key in ("ITEM_MAGIC_PUMPKIN", "ITEM_PILE_OF_COMPONENTS", "ITEM_ICE_AXE"):
            with self.subTest(item=item_key):
                self.assertEqual(
                    ItemClassification.progression,
                    data.items[item_key].classification,
                )

        node_names = load_json_data("quest_node_names.json")
        expected_node_events = {
            "npc_witch:9:option:17": enchant_pumpkin,
            "npc_blacksmith:11:option:9": make_equipment,
            "check_contraband_box:368": send_pumpkin,
            "check_contraband_box:338": send_equipment,
            "contraband_box:125": third_message,
            "check_contraband_box:200": send_paint,
            "check_contraband_box:276": send_jelly,
            "check_contraband_box:257": send_banner,
            "refugee_ev_d16:24": finale,
            "refugee_ev_d16:59": finale,
        }
        for node_id, event in expected_node_events.items():
            with self.subTest(node_id=node_id):
                self.assertEqual(event.location_label, node_names[node_id])

    def test_refugee_cook_rewards_model_kitchen_and_beehive_builds(self):
        kitchen = data.events["EVENT_REFUGEE_COOK_BUILD_KITCHEN"]
        upgraded_kitchen = data.events["EVENT_REFUGEE_COOK_UPGRADE_KITCHEN"]
        beehives = data.events["EVENT_REFUGEE_COOK_BUILD_BEEHIVES"]

        self.assertEqual(
            ["EVENT_TEODORO_BUILD_FIRST_WELL_AND_TENT"],
            list(kitchen.required_quests),
        )
        self.assertEqual(
            {
                "ITEM_FLITCH",
                "ITEM_WOOD_BILLET",
                "ITEM_NAILS",
            },
            set(kitchen.required_craft_items),
        )
        self.assertEqual({AreaPointData("REFUGEE_CAMP", 6)}, set(kitchen.required_area_points))
        self.assertEqual(
            ["LOCATION_REFUGEE_COOK_REWARD_BUILD_KITCHEN"],
            list(kitchen.rewards),
        )

        self.assertEqual(
            ["EVENT_REFUGEE_COOK_BUILD_KITCHEN"],
            list(upgraded_kitchen.required_quests),
        )
        self.assertEqual(
            {"ITEM_WOODEN_PLANK", "ITEM_NAILS"},
            set(upgraded_kitchen.required_craft_items),
        )
        self.assertEqual(
            {AreaPointData("REFUGEE_CAMP", 8)},
            set(upgraded_kitchen.required_area_points),
        )
        self.assertEqual(
            ["LOCATION_REFUGEE_COOK_REWARD_UPGRADE_KITCHEN"],
            list(upgraded_kitchen.rewards),
        )

        self.assertEqual(
            ["EVENT_REFUGEE_COOK_UPGRADE_KITCHEN"],
            list(beehives.required_quests),
        )
        self.assertEqual({"ITEM_FLITCH", "ITEM_BEE"}, set(beehives.required_craft_items))
        self.assertEqual({AreaPointData("REFUGEE_CAMP", 2)}, set(beehives.required_area_points))
        self.assertEqual(
            ["LOCATION_REFUGEE_COOK_REWARD_BUILD_BEEHIVES"],
            list(beehives.rewards),
        )

        node_names = load_json_data("quest_node_names.json")
        self.assertEqual(
            node_names["npc_refugee_cook:282"],
            node_names["npc_refugee_cook:15:option:0"],
            "The prebuilt-kitchen and post-build dialogue paths are one reward",
        )

    def test_refugee_tanner_rewards_model_workplace_fence_and_livestock(self):
        workplace = data.events["EVENT_REFUGEE_TANNER_BUILD_WORKPLACE"]
        fence = data.events["EVENT_REFUGEE_TANNER_BUILD_FARM_FENCE"]
        livestock = data.events["EVENT_REFUGEE_TANNER_ARRANGE_LIVESTOCK"]

        self.assertEqual(
            ["EVENT_CHURCH_OPEN"],
            list(workplace.required_quests),
        )
        self.assertEqual(
            {"ITEM_WOODEN_STICK", "ITEM_SILK", "ITEM_WOODEN_PLANK", "ITEM_NAILS"},
            set(workplace.required_craft_items),
        )
        self.assertEqual(
            {AreaPointData("REFUGEE_CAMP", 12)},
            set(workplace.required_area_points),
        )
        self.assertEqual(
            ["LOCATION_REFUGEE_TANNER_REWARD_BUILD_WORKPLACE"],
            list(workplace.rewards),
        )

        self.assertEqual(
            ["EVENT_REFUGEE_TANNER_BUILD_WORKPLACE"],
            list(fence.required_quests),
        )
        self.assertEqual(
            {"ITEM_FLITCH", "ITEM_WOOD_BILLET"},
            set(fence.required_craft_items),
        )
        self.assertEqual(
            {AreaPointData("REFUGEE_CAMP", 12)},
            set(fence.required_area_points),
        )
        self.assertEqual(
            ["LOCATION_REFUGEE_TANNER_REWARD_BUILD_FARM_FENCE"],
            list(fence.rewards),
        )

        self.assertEqual(
            ["EVENT_REFUGEE_TANNER_BUILD_FARM_FENCE"],
            list(livestock.required_quests),
        )
        self.assertEqual([], list(livestock.required_quest_items))
        self.assertEqual([], list(livestock.required_craft_items))
        self.assertEqual([], list(livestock.required_area_points))
        self.assertEqual(
            ["LOCATION_REFUGEE_TANNER_REWARD_ARRANGE_LIVESTOCK"],
            list(livestock.rewards),
        )

        node_names = load_json_data("quest_node_names.json")
        self.assertEqual(
            "Arrange chickens for the Refugee Tanner",
            node_names["egg_seller:13:option:0"],
        )
        self.assertEqual(
            "Arrange cows for the Refugee Tanner",
            node_names["npc_shepherds_wife:13:option:1"],
        )
        self.assertEqual(
            "Finish arranging livestock for the Refugee Tanner",
            node_names["unlock:macro__check_and_set_refugee_tanner_4_1_start.json:8"],
        )

    def test_refugee_coffin_maker_rewards_require_both_supply_requests(self):
        iron_chisels = data.events["EVENT_REFUGEE_COFFIN_MAKER_GIVE_IRON_CHISELS"]
        wood_wedges = data.events["EVENT_REFUGEE_COFFIN_MAKER_GIVE_WOOD_WEDGES"]
        workplace = data.events["EVENT_REFUGEE_COFFIN_MAKER_BUILD_WORKPLACE"]
        gold_chisels = data.events[
            "EVENT_REFUGEE_COFFIN_MAKER_GIVE_GOLD_STEEL_CHISELS"
        ]

        for request, craft_item, reward in (
            (
                iron_chisels,
                "ITEM_IRON_CHISEL",
                "LOCATION_REFUGEE_COFFIN_MAKER_REWARD_GIVE_IRON_CHISELS",
            ),
            (
                wood_wedges,
                "ITEM_WOOD_WEDGE",
                "LOCATION_REFUGEE_COFFIN_MAKER_REWARD_GIVE_WOOD_WEDGES",
            ),
        ):
            with self.subTest(event=request.item_label):
                self.assertEqual(
                    ["EVENT_CHURCH_OPEN"],
                    list(request.required_quests),
                )
                self.assertEqual(
                    {"ITEM_WOODEN_STICK", "ITEM_SILK", craft_item},
                    set(request.required_craft_items),
                )
                self.assertEqual(
                    {AreaPointData("REFUGEE_CAMP", 8)},
                    set(request.required_area_points),
                )
                self.assertEqual([reward], list(request.rewards))

        self.assertEqual(
            {
                "EVENT_REFUGEE_COFFIN_MAKER_GIVE_IRON_CHISELS",
                "EVENT_REFUGEE_COFFIN_MAKER_GIVE_WOOD_WEDGES",
            },
            set(workplace.required_quests),
            "The workplace craft unlocks only after both supply requests increment the counter",
        )
        self.assertEqual(
            {"ITEM_WOODEN_PLANK", "ITEM_NAILS"},
            set(workplace.required_craft_items),
        )
        self.assertEqual(
            {AreaPointData("REFUGEE_CAMP", 10)},
            set(workplace.required_area_points),
        )
        self.assertEqual(
            ["LOCATION_REFUGEE_COFFIN_MAKER_REWARD_BUILD_WORKPLACE"],
            list(workplace.rewards),
        )

        self.assertEqual(
            ["EVENT_REFUGEE_COFFIN_MAKER_BUILD_WORKPLACE"],
            list(gold_chisels.required_quests),
        )
        self.assertEqual(
            ["ITEM_STEEL_CHISEL_GOLD"],
            list(gold_chisels.required_craft_items),
        )
        self.assertEqual(
            ["LOCATION_REFUGEE_COFFIN_MAKER_REWARD_GIVE_GOLD_STEEL_CHISELS"],
            list(gold_chisels.rewards),
        )

        node_names = load_json_data("quest_node_names.json")
        self.assertEqual(
            "Give iron chisels to the Refugee Coffin Maker",
            node_names["npc_refugee_coffin_maker:15:option:0"],
        )
        self.assertEqual(
            "Give wood wedges to the Refugee Coffin Maker",
            node_names["npc_refugee_coffin_maker:15:option:1"],
        )
        self.assertEqual(
            "Build the Refugee Coffin Maker's workplace",
            node_names["unlock:place_coffin_workplace.json:6"],
        )

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

    def test_stranger_sins_time_machine_chain_uses_named_player_actions(self):
        self.assertFalse(
            [key for key in data.events if key.startswith("EVENT_GET_TIME_MACHINE_ITEM_")],
            "Artifact acquisition events must describe the player's action, not an artifact number",
        )
        self.assertFalse(
            [key for key in data.events if key.startswith("EVENT_TAVERN_TIME_MACHINE_CUTSCENE_")],
            "Time-machine events must identify the artifact the player uses",
        )

        artifact_events = {
            "EVENT_TAVERN_USE_STATUETTE_IN_TIME_MACHINE": "ITEM_STATUETTE",
            "EVENT_TAVERN_USE_FLASK_IN_TIME_MACHINE": "ITEM_FLASK",
            "EVENT_TAVERN_USE_DOOR_HINGE_IN_TIME_MACHINE": "ITEM_DOOR_HINGE",
            "EVENT_TAVERN_USE_LEGIONARY_HELM_IN_TIME_MACHINE": "ITEM_LEGIONARY_HELM",
            "EVENT_TAVERN_USE_ANCIENT_LOCKPICKS_IN_TIME_MACHINE": "ITEM_ANCIENT_LOCKPICKS",
            "EVENT_TAVERN_USE_PRIESTS_MEDALLION_IN_TIME_MACHINE": "ITEM_PRIESTS_MEDALLION",
            "EVENT_TAVERN_USE_LEGIONARY_DAGGER_IN_TIME_MACHINE": "ITEM_THE_LEGIONARY_DAGGER",
            "EVENT_TAVERN_USE_BELT_BUCKLE_IN_TIME_MACHINE": "ITEM_BELT_BUCKLE",
            "EVENT_TAVERN_USE_CLAY_SHARDS_IN_TIME_MACHINE": "ITEM_CLAY_SHARDS",
            "EVENT_TAVERN_USE_ANCIENT_GOD_AMULET_IN_TIME_MACHINE": "ITEM_AMULET_OF_THE_ANCIENT_GOD",
            "EVENT_TAVERN_USE_ANCIENT_SHACKLES_IN_TIME_MACHINE": "ITEM_ANCIENT_SHACKLES",
            "EVENT_TAVERN_USE_ANCIENT_PICKAXE_IN_TIME_MACHINE": "ITEM_ANCIENT_PICKAXE",
            "EVENT_TAVERN_USE_ANCIENT_KEYS_IN_TIME_MACHINE": "ITEM_ANCIENT_KEYS",
            "EVENT_TAVERN_USE_CLAY_POT_OF_TAR_IN_TIME_MACHINE": "ITEM_CLAY_POT_OF_TAR",
            "EVENT_TAVERN_USE_PRIESTS_SIGNET_IN_TIME_MACHINE": "ITEM_PRIESTS_SIGNET",
            "EVENT_TAVERN_USE_PRIESTESS_RING_IN_TIME_MACHINE": "ITEM_PRIESTESS_RING",
            "EVENT_TAVERN_USE_CHURCH_BRICK_IN_TIME_MACHINE": "ITEM_A_BRICK_FROM_THE_CHURCH",
        }
        for event_key, artifact_key in artifact_events.items():
            with self.subTest(event=event_key):
                self.assertEqual([artifact_key], list(data.events[event_key].required_quest_items))

        visions_without_rewards = {
            "EVENT_TAVERN_USE_DOOR_HINGE_IN_TIME_MACHINE",
            "EVENT_TAVERN_USE_ANCIENT_SHACKLES_IN_TIME_MACHINE",
            "EVENT_TAVERN_USE_CLAY_POT_OF_TAR_IN_TIME_MACHINE",
        }
        for event_key in artifact_events:
            with self.subTest(event=event_key):
                expected_rewards = [] if event_key in visions_without_rewards else [
                    event_key.replace("EVENT_", "LOCATION_").replace(
                        "TAVERN_USE_", "TAVERN_REWARD_USE_"
                    )
                ]
                self.assertEqual(expected_rewards, list(data.events[event_key].rewards))

    def test_farmer_flask_reaction_is_separate_from_farmers_son_reward(self):
        son_event = data.events["EVENT_FARMERS_SON_CONFESS_SECRET_DRINKING"]
        farmer_event = data.events["EVENT_FARMER_REACT_TO_SONS_SECRET_DRINKING"]

        self.assertEqual(
            ["LOCATION_FARMERS_SON_REWARD_CONFESS_SECRET_DRINKING"],
            list(son_event.rewards),
        )
        self.assertEqual(
            ["EVENT_FARMERS_SON_CONFESS_SECRET_DRINKING"],
            list(farmer_event.required_quests),
        )
        self.assertEqual(
            ["LOCATION_FARMER_REWARD_REACT_TO_SONS_SECRET_DRINKING"],
            list(farmer_event.rewards),
        )

    def test_priests_signet_and_priestess_ring_branches_are_parallel(self):
        pot_event = "EVENT_TAVERN_USE_CLAY_POT_OF_TAR_IN_TIME_MACHINE"
        ring_event = data.events["EVENT_FARMER_RESOLVE_BELLAS_STORY"]

        signet_chain = [
            "EVENT_DIG_ASK_ABOUT_PRIESTS_SIGNET",
            "EVENT_LIGHTHOUSE_KEEPER_ASK_FOR_RACING_RAT",
            "EVENT_KOUKOL_ASK_FOR_RACING_RAT",
            "EVENT_GYPSY_BARON_ASK_FOR_RACING_RAT",
            "EVENT_GYPSY_BARON_BUY_RACING_RAT",
            "EVENT_DIG_ACCEPT_GYPSY_BARONS_RAT",
        ]
        self.assertEqual([pot_event], list(data.events[signet_chain[0]].required_quests))
        for predecessor, event_key in zip(signet_chain, signet_chain[1:]):
            with self.subTest(event=event_key):
                self.assertEqual([predecessor], list(data.events[event_key].required_quests))

        self.assertEqual([pot_event], list(ring_event.required_quests))
        self.assertEqual(
            ["EVENT_TAVERN_USE_PRIESTS_SIGNET_IN_TIME_MACHINE"],
            list(data.events["EVENT_DIG_UP_CHURCH_BRICK"].required_quests),
        )

    def test_stranger_sins_poisoned_vase_chain_is_explicit(self):
        chain = [
            "EVENT_TAVERN_USE_ANCIENT_PICKAXE_IN_TIME_MACHINE",
            "EVENT_ADAM_ASK_ABOUT_ANCIENT_KEYS",
            "EVENT_ADAM_SHOW_PORCELAIN_PITCHERS",
            "EVENT_MERCHANT_ASK_ABOUT_RARE_VASES",
            "EVENT_BEEKEEPER_ASK_ABOUT_RARE_VASES",
            "EVENT_DIG_SOLVE_POISON_RIDDLE",
            "EVENT_BEEKEEPER_TRADE_POISONED_PIE_FOR_VASES",
            "EVENT_ADAM_ACCEPT_POISONED_VASES",
            "EVENT_ADAM_SEARCH_HOUSE_FOR_ANCIENT_KEYS",
            "EVENT_TAVERN_USE_ANCIENT_KEYS_IN_TIME_MACHINE",
        ]
        for predecessor, event_key in zip(chain, chain[1:]):
            with self.subTest(event=event_key):
                self.assertEqual([predecessor], list(data.events[event_key].required_quests))

        self.assertEqual(
            ["ITEM_PORCELAIN_PITCHER"],
            list(data.events["EVENT_ADAM_SHOW_PORCELAIN_PITCHERS"].required_craft_items),
        )
        self.assertEqual(
            ["ITEM_PIE_WITH_POISON"],
            list(data.events["EVENT_BEEKEEPER_TRADE_POISONED_PIE_FOR_VASES"].required_quest_items),
        )
        self.assertEqual(
            ["ITEM_VASES_WITH_POISON"],
            list(data.events["EVENT_ADAM_ACCEPT_POISONED_VASES"].required_quest_items),
        )

    def test_stranger_sins_giant_carrot_chain_is_explicit(self):
        chain = [
            "EVENT_TAVERN_USE_DOOR_HINGE_IN_TIME_MACHINE",
            "EVENT_FARMER_ASK_ABOUT_GIANT_CARROT",
            "EVENT_CLOTHO_ASK_TO_ENLARGE_CARROT",
            "EVENT_CORY_ASK_TO_DATE_CLOTHO",
            "EVENT_TRESS_ASK_HOW_TO_CONVINCE_CORY",
            "EVENT_CLOTHO_ENLARGE_CARROT",
            "EVENT_FARMER_ACCEPT_GIANT_CARROT",
            "EVENT_FARMER_SEARCH_HOUSE_FOR_LEGIONARY_HELM",
            "EVENT_TAVERN_USE_LEGIONARY_HELM_IN_TIME_MACHINE",
        ]
        for predecessor, event_key in zip(chain, chain[1:]):
            with self.subTest(event=event_key):
                self.assertEqual([predecessor], list(data.events[event_key].required_quests))

        enlarge = data.events["EVENT_CLOTHO_ENLARGE_CARROT"]
        self.assertEqual(["ITEM_CARROT"], list(enlarge.required_craft_items))
        self.assertEqual(["LOCATION_CLOTHO_REWARD_ENLARGE_CARROT"], list(enlarge.rewards))
        self.assertEqual(
            ["ITEM_GIANT_CARROT"],
            list(data.events["EVENT_FARMER_ACCEPT_GIANT_CARROT"].required_quest_items),
        )
        self.assertNotIn("EVENT_ENLARGE_CARROT", data.events)

    def test_stranger_sins_intermediate_quest_items_are_randomized(self):
        item_rewards = {
            "EVENT_CLOTHO_ENLARGE_CARROT": (
                "ITEM_GIANT_CARROT",
                "LOCATION_CLOTHO_REWARD_ENLARGE_CARROT",
            ),
            "EVENT_DIG_SOLVE_POISON_RIDDLE": (
                "ITEM_PIE_WITH_POISON",
                "LOCATION_DIG_REWARD_SOLVE_POISON_RIDDLE",
            ),
            "EVENT_BEEKEEPER_TRADE_POISONED_PIE_FOR_VASES": (
                "ITEM_VASES_WITH_POISON",
                "LOCATION_BEEKEEPER_REWARD_TRADE_POISONED_PIE_FOR_VASES",
            ),
            "EVENT_GYPSY_BARON_BUY_RACING_RAT": (
                "ITEM_RAT_FOR_DIG",
                "LOCATION_GYPSY_BARON_REWARD_BUY_RACING_RAT",
            ),
            "EVENT_TAVERN_EVENT_COMEDY_STANDUP": (
                "ITEM_MILLERS_INVITATION",
                "LOCATION_TAVERN_REWARD_HOLD_FIRST_COMEDY_STANDUP",
            ),
            "EVENT_DIG_UP_BEEKEEPERS_HONEY_BARREL": (
                "ITEM_HONEY_BARREL",
                "LOCATION_VILLAGE_REWARD_DIG_UP_BEEKEEPERS_HONEY_BARREL",
            ),
            "EVENT_CLOTHO_GIVE_MAGIC_SCROLL_FOR_KOUKOL": (
                "ITEM_MAGIC_SCROLL_FOR_KOUKOL",
                "LOCATION_CLOTHO_REWARD_GIVE_MAGIC_SCROLL_FOR_KOUKOL",
            ),
        }
        for event_key, (item_key, location_key) in item_rewards.items():
            with self.subTest(event=event_key):
                self.assertIn(item_key, data.items)
                self.assertEqual([location_key], list(data.events[event_key].rewards))

        self.assertEqual(
            ["ITEM_RAT_FOR_DIG"],
            list(data.events["EVENT_DIG_ACCEPT_GYPSY_BARONS_RAT"].required_quest_items),
        )
        self.assertIn("ITEM_HONEY_PLASTER", data.items)
        self.assertIn(
            "LOCATION_BEEKEEPER_REWARD_ACCEPT_HONEY_BARREL_2",
            data.events["EVENT_BEEKEEPER_ACCEPT_HONEY_BARREL"].rewards,
        )

    def test_stranger_sins_ancient_lockpicks_chain_is_explicit(self):
        chain = [
            "EVENT_TAVERN_USE_LEGIONARY_HELM_IN_TIME_MACHINE",
            "EVENT_MILLER_ASK_ABOUT_ANCIENT_LOCKPICKS",
            "EVENT_MILLER_SEARCH_FOR_STOLEN_INVITATION_CLUES",
            "EVENT_LIGHTHOUSE_KEEPER_CONFRONT_ABOUT_STOLEN_INVITATION",
            "EVENT_TAVERN_EVENT_COMEDY_STANDUP",
            "EVENT_MILLER_ACCEPT_COMEDY_INVITATION",
            "EVENT_TAVERN_USE_ANCIENT_LOCKPICKS_IN_TIME_MACHINE",
        ]
        for predecessor, event_key in zip(chain, chain[1:]):
            with self.subTest(event=event_key):
                self.assertEqual([predecessor], list(data.events[event_key].required_quests))

        self.assertEqual(
            ["ITEM_MILLERS_INVITATION"],
            list(data.events["EVENT_MILLER_ACCEPT_COMEDY_INVITATION"].required_quest_items),
        )
        self.assertEqual(
            ["ITEM_FLYER", "ITEM_FAITH", "MATERIAL_TAVERN_REPUTATION"],
            list(data.events["EVENT_TAVERN_EVENT_COMEDY_STANDUP"].required_craft_items),
        )

    def test_stranger_sins_snake_booze_branches_share_the_happiness_gate(self):
        ask = data.events["EVENT_SNAKE_ASK_TO_BREW_BOOZE_FOR_DIG"]
        convince = data.events["EVENT_SNAKE_CONVINCE_TO_BREW_BOOZE_FOR_DIG"]
        collect = data.events["EVENT_SNAKE_RETURN_FOR_DIGS_BOOZE"]

        self.assertIn("EVENT_DIG_ASK_FOR_BOOZE", ask.required_quests)
        self.assertEqual(
            ["EVENT_SNAKE_ASK_TO_BREW_BOOZE_FOR_DIG"],
            list(convince.required_quests),
        )
        self.assertEqual([HappinessData("SNAKE", 70)], list(convince.required_happiness))
        self.assertEqual(
            ["EVENT_SNAKE_CONVINCE_TO_BREW_BOOZE_FOR_DIG"],
            list(collect.required_quests),
        )
        self.assertNotIn("EVENT_SNAKE_REMIND_ABOUT_DIGS_BOOZE", data.events)

    def test_stranger_sins_legionary_dagger_chain_is_explicit(self):
        chain = [
            "EVENT_TAVERN_USE_PRIESTS_MEDALLION_IN_TIME_MACHINE",
            "EVENT_KREZVOLD_ASK_TO_PERSUADE_MS_CHARM",
            "EVENT_MS_CHARM_AGREE_TO_SING_FOR_KREZVOLD",
            "EVENT_KREZVOLD_HEAR_MS_CHARM_WILL_SING",
            "EVENT_TAVERN_USE_LEGIONARY_DAGGER_IN_TIME_MACHINE",
        ]
        for predecessor, event_key in zip(chain, chain[1:]):
            with self.subTest(event=event_key):
                self.assertEqual([predecessor], list(data.events[event_key].required_quests))

        persuasion = data.events["EVENT_MS_CHARM_AGREE_TO_SING_FOR_KREZVOLD"]
        self.assertEqual([], list(persuasion.required_quest_items))
        self.assertEqual([], list(persuasion.required_craft_items))

    def test_stranger_sins_rare_dagger_chain_omits_optional_woodcutter_event(self):
        gypsy = data.events["EVENT_GYPSY_BARON_REPORT_RARE_DAGGER_MISSING"]
        cory = data.events["EVENT_CORY_DISCUSS_RARE_DAGGER"]
        tress = data.events["EVENT_TRESS_GIVE_RARE_DAGGER"]

        self.assertEqual(
            ["EVENT_KREZVOLD_HEAR_MS_CHARM_WILL_SING"],
            list(gypsy.required_quests),
        )
        self.assertNotIn("EVENT_WOODCUTTER_DISCUSS_RARE_DAGGER", data.events)
        self.assertEqual(
            ["EVENT_GYPSY_BARON_REPORT_RARE_DAGGER_MISSING"],
            list(cory.required_quests),
        )
        self.assertNotIn("EVENT_WOODCUTTER_DISCUSS_RARE_DAGGER", cory.required_quests)
        self.assertEqual(["EVENT_CORY_DISCUSS_RARE_DAGGER"], list(tress.required_quests))
        self.assertEqual([], list(tress.required_quest_items))
        self.assertEqual([], list(tress.required_craft_items))
        self.assertEqual(["LOCATION_TRESS_REWARD_GIVE_RARE_DAGGER"], list(tress.rewards))

    def test_stranger_sins_belt_buckle_chain_is_explicit(self):
        chain = [
            "EVENT_TAVERN_USE_LEGIONARY_DAGGER_IN_TIME_MACHINE",
            "EVENT_WOODCUTTER_ASK_ABOUT_BELT_BUCKLE",
            "EVENT_DIG_UP_BEEKEEPERS_HONEY_BARREL",
            "EVENT_BEEKEEPER_ACCEPT_HONEY_BARREL",
            "EVENT_WOODCUTTER_ACCEPT_HONEY_PLASTER",
            "EVENT_TAVERN_USE_BELT_BUCKLE_IN_TIME_MACHINE",
        ]
        for predecessor, event_key in zip(chain, chain[1:]):
            with self.subTest(event=event_key):
                self.assertEqual([predecessor], list(data.events[event_key].required_quests))

        self.assertEqual(
            ["ITEM_HONEY_BARREL"],
            list(data.events["EVENT_BEEKEEPER_ACCEPT_HONEY_BARREL"].required_quest_items),
        )
        self.assertEqual(
            ["ITEM_HONEY_PLASTER"],
            list(data.events["EVENT_WOODCUTTER_ACCEPT_HONEY_PLASTER"].required_quest_items),
        )

    def test_stranger_sins_ancient_pickaxe_chain_is_explicit(self):
        chain = [
            "EVENT_TAVERN_USE_ANCIENT_SHACKLES_IN_TIME_MACHINE",
            "EVENT_KOUKOL_ASK_FOR_HELP_WITH_NIGHTMARES",
            "EVENT_CLOTHO_GIVE_MAGIC_SCROLL_FOR_KOUKOL",
            "EVENT_KOUKOL_ACCEPT_MAGIC_SCROLL",
            "EVENT_KOUKOL_RETURN_WITH_DARK_ORGAN",
            "EVENT_KOUKOL_APPROVE_TAVERN_UPGRADE",
            "EVENT_TAVERN_USE_ANCIENT_PICKAXE_IN_TIME_MACHINE",
        ]
        for predecessor, event_key in zip(chain, chain[1:]):
            with self.subTest(event=event_key):
                self.assertIn(predecessor, data.events[event_key].required_quests)

        clotho = data.events["EVENT_CLOTHO_GIVE_MAGIC_SCROLL_FOR_KOUKOL"]
        self.assertEqual(
            {
                "EVENT_KOUKOL_ASK_FOR_HELP_WITH_NIGHTMARES",
                "EVENT_INQUISITOR_WAIT_FOR_DARK_ORGAN_REQUEST",
            },
            set(clotho.required_quests),
        )
        self.assertEqual(
            ["ITEM_MAGIC_SCROLL_FOR_KOUKOL"],
            list(data.events["EVENT_KOUKOL_ACCEPT_MAGIC_SCROLL"].required_quest_items),
        )

        dark_organ = data.events["EVENT_KOUKOL_RETURN_WITH_DARK_ORGAN"]
        self.assertEqual(1, len(dark_organ.rewards))
        self.assertEqual([], list(dark_organ.required_craft_items))

        self.assertNotIn("EVENT_TAVERN_UPGRADE_TO_40_QUALITY", data.events)
        tavern_approval = data.events["EVENT_KOUKOL_APPROVE_TAVERN_UPGRADE"]
        self.assertEqual(
            ["EVENT_KOUKOL_RETURN_WITH_DARK_ORGAN"],
            list(tavern_approval.required_quests),
        )
        self.assertEqual({AreaPointData("TAVERN", 40)}, set(tavern_approval.required_area_points))
        self.assertEqual(
            [],
            list(tavern_approval.required_craft_items),
        )

    def test_stranger_sins_combined_relation_and_artifact_rewards_have_two_checks(self):
        combined_reward_events = {
            "EVENT_MILLER_ACCEPT_COMEDY_INVITATION",
            "EVENT_DIG_ACCEPT_SNAKES_BOOZE",
            "EVENT_KREZVOLD_HEAR_MS_CHARM_WILL_SING",
            "EVENT_BEEKEEPER_ACCEPT_HONEY_BARREL",
            "EVENT_WOODCUTTER_ACCEPT_HONEY_PLASTER",
            "EVENT_ADAM_EXPLAIN_GHOSTLY_POTTERY",
            "EVENT_KOUKOL_APPROVE_TAVERN_UPGRADE",
            "EVENT_DIG_ACCEPT_GYPSY_BARONS_RAT",
        }
        for event_key in combined_reward_events:
            with self.subTest(event=event_key):
                self.assertEqual(2, len(data.events[event_key].rewards))

    def test_house_artifacts_are_separate_from_the_dialogue_that_grants_access(self):
        helm_search = data.events["EVENT_FARMER_SEARCH_HOUSE_FOR_LEGIONARY_HELM"]
        self.assertEqual(["EVENT_FARMER_ACCEPT_GIANT_CARROT"], list(helm_search.required_quests))
        self.assertEqual([HappinessData("FARMER", 40)], list(helm_search.required_happiness))
        self.assertEqual(
            ["EVENT_FARMER_SEARCH_HOUSE_FOR_LEGIONARY_HELM"],
            list(data.events["EVENT_TAVERN_USE_LEGIONARY_HELM_IN_TIME_MACHINE"].required_quests),
        )

        key_search = data.events["EVENT_ADAM_SEARCH_HOUSE_FOR_ANCIENT_KEYS"]
        self.assertEqual(["EVENT_ADAM_ACCEPT_POISONED_VASES"], list(key_search.required_quests))
        self.assertEqual(
            ["EVENT_ADAM_SEARCH_HOUSE_FOR_ANCIENT_KEYS"],
            list(data.events["EVENT_TAVERN_USE_ANCIENT_KEYS_IN_TIME_MACHINE"].required_quests),
        )

    def test_bellas_ring_research_chain_is_explicit(self):
        chain = [
            "EVENT_FARMER_RESOLVE_BELLAS_STORY",
            "EVENT_FARMERS_SON_DISCUSS_MOTHER",
            "EVENT_MILLER_DISCUSS_BELLA",
            "EVENT_CLOTHO_DISCUSS_BELLA",
            "EVENT_FARMER_RECALL_BELLAS_RING",
            "EVENT_FARMER_RECOVER_BELLAS_RING",
        ]
        for predecessor, event_key in zip(chain, chain[1:]):
            with self.subTest(event=event_key):
                self.assertEqual([predecessor], list(data.events[event_key].required_quests))
        self.assertEqual(
            ["EVENT_FARMER_RECOVER_BELLAS_RING"],
            list(data.events["EVENT_TAVERN_USE_PRIESTESS_RING_IN_TIME_MACHINE"].required_quests),
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
