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
