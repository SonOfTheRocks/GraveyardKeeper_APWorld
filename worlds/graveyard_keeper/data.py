import pkgutil

import importlib_resources
import orjson
from typing import List, Dict, Union, Any, Tuple, Set

from BaseClasses import ItemClassification
from worlds.graveyard_keeper.models import DLCType, EventData, RegionData, LocationData, ItemData, VendorData, \
    RecipeData, UnlockData, GraveyardKeeperData, ReverseItemData, QualityRecipeData, SimpleRecipeData, QuestEventData, \
    HappinessData

UNREACHABLE_REGION_KEY = "REGION_UNREACHABLE"
CRAFTING_REGION_KEY = "REGION_CRAFTING"
CRAFTING_EVENT_PREFIX = "EVENT_CAN_GET_"
CRAFTING_EVENT_LABEL_PREFIX = "Can obtain "

def load_json_data(data_name: str) -> Union[List[Any], Dict[str, Any]]:
    raw = pkgutil.get_data(__name__, f"data/{data_name}")

    if raw is None:
        raise FileNotFoundError(f"Could not find data file: data/{data_name}")

    try:
        return orjson.loads(raw)
    except orjson.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse JSON file 'data/{data_name}': {e}"
        ) from e

def _str_to_item_classification(string: str) -> ItemClassification:
    match string:
        case "PROGRESSION":
            return ItemClassification.progression
        case "USEFUL":
            return ItemClassification.useful
        case "FILLER":
            return ItemClassification.filler
        case "TRAP":
            return ItemClassification.trap
        case _:
            raise ValueError(f"Unknown item classification '{string}'")

#def parse_enum(enum_cls: type[enum.Enum], value: str) -> enum.Enum:
#    try:
#        return enum_cls[value]
#    except KeyError:
#        raise ValueError(f"'{value}' is not a valid {enum_cls.__name__}")

def iter_json_files(base):
    for entry in base.iterdir():
        if entry.is_dir():
            if entry.name == "unused":
                continue
            yield from iter_json_files(entry)
        elif entry.name.endswith(".json"):
            yield entry

def load_regions() -> Dict[str, RegionData]:
    regions_json = load_json_data("regions.json")
    regions: Dict[str, RegionData] = {
        region_key: RegionData(
            region_json.get("label", region_key),
            DLCType.from_string(region_json["dlc"]),
            region_json["locations"],
            region_json["events"],
            region_json["exits"]
        ) for region_key, region_json in regions_json.items()
    }
    regions[CRAFTING_REGION_KEY] = RegionData(
        "Crafting",
        DLCType.BASE_GAME,
        [],
        [], # CAN_CRAFT events will be added in generate_crafting_events
        ["REGION_SWEET_HOME"]
    )
    regions[UNREACHABLE_REGION_KEY] = RegionData(
        "Unreachable Region",
        DLCType.BASE_GAME,
        [],
        [],
        ["REGION_SWEET_HOME"]
    )
    regions["REGION_SWEET_HOME"].connections += [
        CRAFTING_REGION_KEY,
        UNREACHABLE_REGION_KEY
    ]
    return regions

def load_locations(regions: Dict[str, RegionData]) -> Dict[str, LocationData]:
    locations: Dict[str, LocationData] = {}

    locations.update({
        location_name: LocationData(
            location_json["label"],
            location_json["parent_region"],
        ) for location_name, location_json in load_json_data("locations.json").items()
    })

    ''' disabled for now
    '''

    # tech unlock locations automatically created from regions
    for (tech_region_name, tech_region_label) in [(key, value.label) for key,value in regions.items()
                                 if key.startswith("REGION_TECH_TREE") and '/' in key]:
        tech_region_subname = tech_region_name.split('/')[-1]
        # 3 Unlocks per Tech
        for i in range(1, 4):
            if "SPIRITUALISM" in tech_region_name and tech_region_name.endswith("_GRAVESTONES"):
                location_name = f"LOCATION_{tech_region_subname}_SPIRITUALISM_UNLOCK_{i}"
                location_label = f"{tech_region_label} - Unlock {i} (Spiritualism)"
            else:
                location_name = f"LOCATION_{tech_region_subname}_UNLOCK_{i}"
                location_label = f"{tech_region_label} - Unlock {i}"
            locations[location_name] = LocationData(
                location_label,
                tech_region_name
            )

    return locations

def load_quest_events() -> Dict[str, EventData]:
    quest_events = {}
    for event_key, event_json in load_json_data("quest_events.json").items():
        assert all([ l in event_json.keys() for l in [
            "location_label",
            "item_label",
            "dlc",
            "required_quests",
            "required_happiness",
            "required_quest_items",
            "required_craft_items",
            "rewards"
        ]]), f"incomplete data for '{event_key}'"
        quest_events[event_key] = QuestEventData(
                event_json["location_label"],
                event_json["item_label"],
                DLCType.from_string(event_json["dlc"]),
                event_json["required_quests"],
                [HappinessData.from_string(h) for h in event_json["required_happiness"]],
                event_json["required_quest_items"],
                event_json["required_craft_items"],
                event_json["rewards"]
            )

    return quest_events

def load_items() -> Dict[str, ItemData]:
    items: Dict[str, ItemData] = {}
    #item_files_data = (load_json_data(filename) for filename in importlib_resources.files(__name__).glob("data/items/*.json"))
    #item_files_data = (
    #    load_json_data(f"data/items/{filename}")
    #    for filename
    #    in importlib_resources.files(__name__).glob("data/items/*.json")
    #    if "unused" not in str(filename)
    #)
    root = importlib_resources.files(__name__) / "data/items"
    item_files_data = (
        load_json_data("items/" + str(p.relative_to(root)))
        for p in iter_json_files(root)
    )
    for item_file_data in item_files_data:
        for item_name, item_json in item_file_data.items():
            assert item_name not in items.keys(), f"Item '{item_name}' was defined multiple times"
            items[item_name] = ItemData(
                item_json["label"],
                _str_to_item_classification(item_json["classification"]),
                item_json.get("amount", 1),
            )
    return items

def load_vendors() -> Dict[str, VendorData]:
    vendors: Dict[str, VendorData] =  {
        vendor_name: VendorData(
            vendor_data["region"],
            frozenset(vendor_data["selling"]["level_1"]),
            frozenset(vendor_data["selling"].get("level_2", [])),
            frozenset(vendor_data["selling"].get("level_3", []))
        ) for vendor_name, vendor_data in load_json_data("logic/vendors.json").items()
    }
    return vendors

def load_recipes() -> Dict[str, List[RecipeData]]:
    all_recipes: Dict[str, List[RecipeData]] = {}

    non_renewables = [
        "ITEM_METAL_SCRAP",
        "ITEM_RUINED_BOOK",
        "ITEM_GOO_OF_DEATH"
    ]

    recipe_files = sorted(
        importlib_resources.files(__name__).glob("data/logic/recipes/*.json"),
        key=str,
    )

    recipe_files_data = [
        load_json_data(filename)
        for filename in recipe_files
    ]
    for recipe_file_data in recipe_files_data:
        for output_name in sorted(recipe_file_data):
            recipes = recipe_file_data[output_name]
            assert output_name not in all_recipes.keys(), f"Recipe for '{output_name}' was defined multiple times"
            all_recipes[output_name] = []
            # ignore recipes with non_renewables (non-craftable and non-buyable), as they are currently of no use
            for index, recipe in enumerate(recipes):
                if any([mat in non_renewables for mat in recipe["materials_required"]]):
                    continue
                recipe_required = recipe.get("recipe_required")
                if not recipe_required:
                    recipe_required = None
                if "base_modifier" in recipe.keys():
                    all_recipes[output_name].append(
                        QualityRecipeData(
                            output_name,
                            index,
                            frozenset(recipe["crafting_stations"]),
                            recipe_required,
                            frozenset(recipe["materials_required"]),
                            frozenset(),
                            recipe["crafting_group"],
                            recipe["base_modifier"]
                        )
                    )
                else:
                    all_recipes[output_name].append(
                        SimpleRecipeData(
                            output_name,
                            index,
                            frozenset(recipe["crafting_stations"]),
                            recipe_required,
                            frozenset(recipe["materials_required"]),
                            frozenset()
                        )
                    )

    # blueprints don't have a list of recipes, only one and therefore are a level higher in the JSON than the other recipes
    blueprint_filenames = ["workstations", "buildables"]
    for blueprint_filename in blueprint_filenames:
        blueprint_data = load_json_data(f"logic/{blueprint_filename}.json")
        for output_name in sorted(blueprint_data):
            workstation_recipe = blueprint_data[output_name]
            recipe_required = workstation_recipe.get("recipe_required")
            if not recipe_required:
                recipe_required = None

            all_recipes[output_name] = [
                SimpleRecipeData(
                    output_name,
                    0,
                    frozenset(workstation_recipe["crafting_stations"]),
                    recipe_required,
                    frozenset(workstation_recipe["materials_required"]),
                    frozenset(workstation_recipe["regions"])
                )
            ]

    return all_recipes

def load_unlocks() -> Dict[str, UnlockData]:
    return {
        unlock_name: UnlockData(
            unlock_data["label"],
            _str_to_item_classification(unlock_data["classification"]),
            frozenset(unlock_data["unlocks"]),
            frozenset(unlock_data["researches"])
        ) for unlock_name, unlock_data in load_json_data("items/unlocks.json").items()
    }

def load_progressive_items() -> Tuple[Dict[str, Dict[str, int]], Dict[str, ReverseItemData]]:
    progressive_items: Dict[str, ItemData] = {}
    reverse_progressive_items: Dict[str, ReverseItemData] = {}
    progressive_items_data = load_json_data("logic/progressive_item_mapping.json")
    for progressive_item_name, progressive_item_data in progressive_items_data.items():
        progressive_items[progressive_item_name] = progressive_item_data
        for (item_key, count) in progressive_item_data.items():
            reverse_progressive_items[item_key] = ReverseItemData(
                progressive_item_name,
                count,
            )
    return progressive_items, reverse_progressive_items

def generate_crafting_events(
        crafting_region_data: RegionData,
        recipes: Dict[str, RecipeData],
        items: Dict[str, ItemData],
        vendors: Dict[str, VendorData],
) -> Dict[str, EventData]:
    crafting_events: Dict[str, EventData] = {}
    for output in recipes.keys():
        if output in items:
            continue
        key = CRAFTING_EVENT_PREFIX + output
        label = CRAFTING_EVENT_LABEL_PREFIX + output
        crafting_events[key] = EventData(
            location_label=label, item_label=label
        )
        crafting_region_data.events.append(key)

    vendor_crafting_events: Dict[str, EventData] = {}
    for vendor in vendors.values():
        for item_key in vendor.sells_all:
            # item not craftable and no AP item, need to buy it
            if item_key not in items and item_key not in recipes:
                key = CRAFTING_EVENT_PREFIX + item_key
                label = CRAFTING_EVENT_LABEL_PREFIX + item_key
                vendor_crafting_events[key] = EventData(
                    location_label=label, item_label=label
                )
                # multiple vendors can sell the same item
                if key not in crafting_region_data.events:
                    crafting_region_data.events.append(key)
    crafting_events.update(vendor_crafting_events)

    return crafting_events

"""
def load_initial_accessible_items(vendors: Dict[str, VendorData], recipes: Dict[str, List[RecipeData]]) -> List[str]:
    # add vendor-only-items (no crafting recipe) to available items
    # TODO: make refugee camp vendors only in logic if refugee camp is reachable
    initial_accessible_items: Set[str] = set()
    for vendor_data in vendors.values():
        for item_key in vendor_data.sells:
            if item_key not in recipes.keys():
                initial_accessible_items.add(item_key)
    #print(f"Vendor-only items in accessible pool: {initial_accessible_items}")
    return initial_accessible_items
"""

def load_all_data() -> GraveyardKeeperData:
    new_data = GraveyardKeeperData()
    new_data.regions = load_regions()
    new_data.locations = load_locations(new_data.regions)
    new_data.events = load_quest_events()
    new_data.items = load_items()
    new_data.vendors = load_vendors()
    new_data.recipes = load_recipes()
    new_data.unlocks = load_unlocks()
    (new_data.progressive_items, new_data.progressive_items_reverse) = load_progressive_items()
    new_data.events.update(
        generate_crafting_events(
            new_data.regions[CRAFTING_REGION_KEY],
            new_data.recipes,
            new_data.items,
            new_data.vendors
        )
    )
    #new_data.accessible_items = load_initial_accessible_items(new_data.vendors, new_data.recipes)
    return new_data

data = load_all_data()
