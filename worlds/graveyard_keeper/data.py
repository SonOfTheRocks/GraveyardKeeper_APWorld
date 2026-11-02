from importlib.resources import files
from importlib.resources.abc import Traversable
import orjson
from typing import List, Dict, Union, Any, Tuple, Set

from BaseClasses import ItemClassification
from worlds.graveyard_keeper.models import DLCType, EventData, RegionData, LocationData, ItemData, VendorData, \
    RecipeData, UnlockData, GraveyardKeeperData, ReverseItemData, QualityRecipeData, SimpleRecipeData
from worlds.sa2b.Names.LocationName import route_101_itembox_1

UNREACHABLE_REGION_KEY = "REGION_UNREACHABLE"
CRAFTING_REGION_KEY = "REGION_CRAFTING"
CRAFTING_EVENT_PREFIX = "EVENT_CAN_GET_"
CRAFTING_EVENT_LABEL_PREFIX = "Can obtain "

def load_json_data(data_name: Union[str, Traversable]) -> Union[List[Any], Dict[str, Any]]:
    resource = files(__package__).joinpath("data", data_name) if isinstance(data_name, str) else data_name
    raw = resource.read_bytes()

    if raw is None:
        raise FileNotFoundError(f"Could not find data file: data/{data_name}")

    try:
        return orjson.loads(raw)
    except orjson.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse JSON file 'data/{data_name}': {e}"
        ) from e

def _str_to_dlc_type(string):
    match string:
        case "BASE_GAME":
            return DLCType.BASE_GAME
        case "STRANGER_SINS":
            return DLCType.STRANGER_SINS
        case "GAME_OF_CRONE":
            return DLCType.GAME_OF_CRONE
        case "BETTER_SAVE_SOUL":
            return DLCType.BETTER_SAVE_SOUL
        case _:
            raise ValueError(f"Unknown DLC type '{string}'")

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

def iter_json_files(base, recursive=True):
    for entry in sorted(base.iterdir(), key=lambda entry: entry.name):
        if entry.is_dir():
            if not recursive or entry.name == "unused":
                continue
            yield from iter_json_files(entry)
        elif entry.name.endswith(".json"):
            yield entry

def load_regions() -> Dict[str, RegionData]:
    regions_json = load_json_data("regions.json")
    regions: Dict[str, RegionData] = {
        region_name: RegionData(
            region_json.get("label", region_name),
            _str_to_dlc_type(region_json["dlc"]),
            region_json["locations"],
            region_json["events"],
            region_json["exits"]
        ) for region_name, region_json in regions_json.items()
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
    regions["REGION_SWEET_HOME"].connections += [CRAFTING_REGION_KEY, UNREACHABLE_REGION_KEY]
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

def load_events() -> Dict[str, EventData]:
    return {
        event_name: EventData(
            event_json["location_label"],
            event_json["item_label"]
        ) for event_name, event_json in load_json_data("quest_events.json").items()
    }

def load_items() -> Dict[str, ItemData]:
    items: Dict[str, ItemData] = {}
    root = files(__package__).joinpath("data", "items")
    item_files_data = (load_json_data(resource) for resource in iter_json_files(root))
    for item_file_data in item_files_data:
        for item_name, item_json in item_file_data.items():
            assert item_name not in items.keys(), f"Item '{item_name}' was defined multiple times"
            items[item_name] = ItemData(
                item_json["label"],
                _str_to_item_classification(item_json["classification"]),
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

    recipe_files_data = [
        load_json_data(filename) for filename
        in iter_json_files(files(__package__).joinpath("data", "logic", "recipes"), recursive=False)
    ]
    for recipe_file_data in recipe_files_data:
        for output_name, recipes in recipe_file_data.items():
            assert output_name not in all_recipes.keys(), f"Recipe for '{output_name}' was defined multiple times"
            all_recipes[output_name] = []
            # ignore recipes with non_renewables (non-craftable and non-buyable), as they are currently of no use
            for recipe in recipes:
                if any([mat in non_renewables for mat in recipe["materials_required"]]):
                    continue
                recipe_required = None
                if "recipe_required" in recipe.keys() and recipe["recipe_required"] != '':
                    recipe_required = recipe["recipe_required"]
                if "base_modifier" in recipe.keys():
                    all_recipes[output_name].append(
                        QualityRecipeData(
                            output_name,
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
                            frozenset(recipe["crafting_stations"]),
                            recipe_required,
                            frozenset(recipe["materials_required"]),
                            frozenset()
                        )
                    )

    # blueprints don't have a list of recipes, only one and therefore are a level higher in the JSON than the other recipes
    blueprint_filenames = ["workstations", "buildables"]
    for blueprint_filename in blueprint_filenames:
        for (output_name, workstation_recipe) in load_json_data(f"logic/{blueprint_filename}.json").items():
            recipe_required = None
            if "recipe_required" in workstation_recipe.keys() and workstation_recipe["recipe_required"] != '':
                recipe_required = workstation_recipe["recipe_required"]
            all_recipes[output_name] = [
                SimpleRecipeData(
                    output_name,
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
) -> None:
    crafting_events: Dict[str, EventData] = {}
    for output in recipes.keys():
        key = CRAFTING_EVENT_PREFIX + output
        label = f"Can obtain {output}"
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

def _init() -> None:
    # Create region data
    regions_json = load_json_data("regions.json")
    for region_name, region_json in regions_json.items():

        new_region = RegionData(_str_to_dlc_type(region_json["dlc"]))

        # Locations
        for location_key in region_json["locations"]:
            new_location = LocationData( # TODO: move creation of LocationData to its own loop
                location_key, # TODO: Use location label, not key
                region_name
            )
            new_region.locations.append(location_key)
            data.locations[location_key] = new_location

        #new_region.locations.sort()

        # Events
        for event_name in region_json["events"]:
            new_region.events.append(event_name)

        # Connections
        for region_exit in region_json["exits"]:
            new_region.connections.append(region_exit)

        data.regions[region_name] = new_region

    # Create event data
    events_json = load_json_data("quest_events.json")
    for event_name, event_json in events_json.items():

        new_event = EventData(
            event_json["location_label"],
            event_json["item_label"]
        )
        data.events[event_name] = new_event

    # Load/merge item json files
    item_json_list = []
    for file in iter_json_files(files(__package__).joinpath("data", "items"), recursive=False):
        item_json_list.append(load_json_data(file))

    items_json = {}
    for item_subset in item_json_list:
        for item_name, item_json in item_subset.items():
            if item_name in items_json:
                raise AssertionError(f"Item '{item_name}' was defined multiple times")
            items_json[item_name] = item_json

    # Create item data
    for item_name, item_json in items_json.items():
        data.items[item_name] = ItemData(
            item_json["label"],
            _str_to_item_classification(item_json["classification"]),
        )

    # Create progressive item data
    for progressive_item_name, progressive_item_data in load_json_data("logic/progressive_item_mapping.json").items():
        data.progressive_items[progressive_item_name] = progressive_item_data
        for (item_name, index) in progressive_item_data.items():
            data.progressive_items_reverse[item_name] = (progressive_item_name, index)

    # Create unlock data
    for unlock_name, unlock_data in load_json_data("items/unlocks.json").items():
        data.unlocks[unlock_name] = UnlockData(
            unlock_data["label"],
            _str_to_item_classification(unlock_data["classification"]),
            frozenset(unlock_data["unlocks"]),
            frozenset(unlock_data["researches"])
        )

    # Create merchant data
    vendors_json = load_json_data("logic/vendors.json")
    for vendor_name, vendor_data in vendors_json.items():
        data.vendors[vendor_name] = VendorData(
            frozenset(vendor_data["selling"]),
            vendor_data["region"]
        )

    # Create recipe data for workstations (they have a region dependency)
    workstations_json = load_json_data("logic/workstations.json")
    for workstation_name, workstation_data in workstations_json.items():
        recipe_required = None
        if "recipe_required" in workstation_data.keys() and workstation_data["recipe_required"] != '':
            recipe_required = workstation_data["recipe_required"]
        data.recipes[workstation_name] = (
            [
                SimpleRecipeData(
                    workstation_name,
                    frozenset(workstation_data["crafting_stations"]),
                    recipe_required,
                    frozenset(workstation_data["materials_required"]),
                    frozenset(workstation_data["regions"])
                )
            ]
        )

    # Create recipes data
    recipes_filenames = iter_json_files(files(__package__).joinpath("data", "logic", "recipes"), recursive=False)
    recipes_json = {}
    for recipe_filename in recipes_filenames:
        json_data = load_json_data(recipe_filename)
        for item, recipes in json_data.items():
            recipes_json[item] = recipes
    for result_name, recipes in recipes_json.items():
        data.recipes[result_name] = []
        for recipe in recipes:
            recipe_required = None
            if "recipe_required" in recipe.keys() and recipe["recipe_required"] != '':
                recipe_required = recipe["recipe_required"]
            data.recipes[result_name].append(
                RecipeData(
                    result_name,
                    frozenset(recipe["crafting_stations"]),
                    recipe_required,
                    frozenset(recipe["materials_required"]),
                    frozenset()
                )
            )

    # add vendor-only-items (no crafting recipe) to available items
    # TODO: make refugee camp vendors only in logic if refugee camp is reachable
    for vendor_data in data.vendors.values():
        for item_key in vendor_data.sells_level_1:
            if item_key not in data.recipes.keys():
                data.accessible_items.add(item_key)
    print(f"Vendor-only items in accessible pool: {data.accessible_items}")

def load_all_data() -> GraveyardKeeperData:
    new_data = GraveyardKeeperData()
    new_data.regions = load_regions()
    new_data.locations = load_locations(new_data.regions)
    new_data.events = load_events()
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