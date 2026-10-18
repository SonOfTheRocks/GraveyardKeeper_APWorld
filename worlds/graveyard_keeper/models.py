import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List, FrozenSet, Dict, Set, Counter, override

from BaseClasses import ItemClassification, CollectionState


class DLCType(enum.Enum):
    BASE_GAME = enum.auto()
    STRANGER_SINS = enum.auto()
    GAME_OF_CRONE = enum.auto()
    BETTER_SAVE_SOUL = enum.auto()

    @classmethod
    def from_string(cls, string: str):
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

class ChurchLevel(enum.Enum):
    CLOSED = enum.auto()
    OPEN = enum.auto()
    BIG = enum.auto()
    CATHEDRAL = enum.auto()

@dataclass(frozen=True)
class HappinessData:
    npc: str
    value: int

    @classmethod
    def from_string(cls, string: str):
        npc, value = string.rsplit("_", 1)
        return cls(npc, int(value))


@dataclass(frozen=True)
class AreaPointData:
    area: str
    value: int

    @classmethod
    def from_string(cls, string: str):
        try:
            area, raw_value = string.rsplit("_", 1)
            value = int(raw_value)
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError(f"Invalid area point requirement '{string}'") from error

        if not area or value <= 0:
            raise ValueError(f"Invalid area point requirement '{string}'")
        return cls(area, value)


@dataclass
class EventData:
    location_label: str
    item_label: str


@dataclass
class QuestEventData(EventData):
    dlc: DLCType
    required_quests: FrozenSet[str]
    required_happiness: FrozenSet[HappinessData]
    required_quest_items: FrozenSet[str]
    required_craft_items: FrozenSet[str]
    required_area_points: FrozenSet[AreaPointData]
    rewards: FrozenSet[str]



@dataclass
class RegionData:
    label: str
    dlc: DLCType
    locations: List[str]
    events: List[str]
    connections: List[str]


@dataclass
class LocationTriggerData:
    type: str
    graph: str | None = None
    node_id: str | None = None
    answer_index: int | None = None
    craft_id: str | None = None
    item_id: str | None = None
    technology_id: str | None = None

    def to_slot_data(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"type": self.type}
        for field_name in (
            "graph", "node_id", "answer_index", "craft_id", "item_id", "technology_id",
        ):
            value = getattr(self, field_name)
            if value is not None:
                result[field_name] = value
        return result


@dataclass
class LocationData:
    label: str
    parent_region: str
    triggers: tuple[LocationTriggerData, ...] = ()
    trigger_todo: str | None = None


@dataclass
class ItemData:
    label: str
    classification: ItemClassification
    amount: int

@dataclass
class ReverseItemData:
    key: str
    count: int

@dataclass
class VendorData:
    region: str
    sells_level_1: FrozenSet[str]
    sells_level_2: FrozenSet[str]
    sells_level_3: FrozenSet[str]
    sells_all: FrozenSet[str] = field(init=False)
    #buys: FrozenSet[str]
    def __post_init__(self) -> None:
        self.sells_all = set(list(self.sells_level_1) + list(self.sells_level_2) + list(self.sells_level_3))


class CraftingGroup(enum.Enum):
    NoGroup = enum.auto()
    Standard = enum.auto() # Only Industriousness
    WriterOnly = enum.auto() # Writer (0.3), NO Industriousness
    WritingWithoutIndustriousness = enum.auto() #  Writer (0.3), Playwright (0.5), NO Industriousness
    Writing = enum.auto() # Writer (0.3), Playwright (0.5)
    Book = enum.auto() # Jeweler (0.7), +0.2 for Desk II, but not Organ Workbench Recipes
    Wine = enum.auto() # Wine Master (0.8)
    Chisel = enum.auto() # Blacksmith (0.1), Engineer (0.3)
    Wood = enum.auto() # Carpenter (0.5), Engineer (0.3)
    Marble = enum.auto() # Mason (0.5), Engineer (0.3)
    Food = enum.auto() # Currently unused, could later be used by unimplemented Cook perk
    # Industriousness for all quality crafts


@dataclass
class RecipeData(ABC):
    name: str
    index: int
    workstations: FrozenSet[str]
    required_recipe_item: str
    ingredients: FrozenSet[str]
    regions: FrozenSet[str]

    @property
    @abstractmethod
    def is_quality(self):
        pass


class SimpleRecipeData(RecipeData):
    def __init__(
            self,
            name: str,
            index: int,
            workstations: FrozenSet[str],
            required_recipe_item: str,
            ingredients: FrozenSet[str],
            regions: FrozenSet[str],
    ) -> None:
        super().__init__(
            name,
            index,
            workstations,
            required_recipe_item,
            ingredients,
            regions
        )

    @property
    def is_quality(self):
        return False


class QualityRecipeData(RecipeData):
    crafting_group: CraftingGroup
    base_modifier: float
    def __init__(
            self,
            name: str,
            index: int,
            workstations: FrozenSet[str],
            required_recipe_item: str,
            ingredients: FrozenSet[str],
            regions: FrozenSet[str],
            crafting_group: str,
            base_modifier: float
    ) -> None:
        super().__init__(
            name,
            index,
            workstations,
            required_recipe_item,
            ingredients,
            regions
        )
        match crafting_group:
            case "standard":
                self.crafting_group = CraftingGroup.Standard
            case "writer_only":
                self.crafting_group = CraftingGroup.WriterOnly
            case "writing_without_industriousness":
                self.crafting_group = CraftingGroup.WritingWithoutIndustriousness
            case "writing":
                self.crafting_group = CraftingGroup.Writing
            case "book":
                self.crafting_group = CraftingGroup.Book
            case "wine":
                self.crafting_group = CraftingGroup.Wine
            case "chisel":
                self.crafting_group = CraftingGroup.Chisel
            case "wood":
                self.crafting_group = CraftingGroup.Wood
            case "marble":
                self.crafting_group = CraftingGroup.Marble
            case "food":
                self.crafting_group = CraftingGroup.Food
            case _:
                self.crafting_group = CraftingGroup.NoGroup
        self.base_modifier = base_modifier

    def is_quality(self):
        return True


@dataclass
class UnlockData:
    label: str
    classification: ItemClassification
    unlocks: FrozenSet[List[str]]
    researches: FrozenSet[List[str]]


class GraveyardKeeperData:
    regions: Dict[str, RegionData]
    locations: Dict[str, LocationData]
    events: Dict[str, QuestEventData]
    items: Dict[str, ItemData]
    vendors: Dict[str, VendorData]
    recipes: Dict[str, List[RecipeData]]
    unlocks: Dict[str, UnlockData]
    progressive_items: Dict[str, Dict[str, int]]
    progressive_items_reverse: Dict[str, ReverseItemData]
    accessible_items: Set[str]
    last_synchronized_player_state: Counter

    def __init__(self) -> None:
        self.regions = {}
        self.locations = {}
        self.events = {}
        self.items = {}
        self.vendors = {}
        self.recipes = {}
        self.unlocks = {}
        self.progressive_items = {}
        self.progressive_items_reverse = {}
        self.accessible_items = set()
        self.last_synchronized_player_state = None
