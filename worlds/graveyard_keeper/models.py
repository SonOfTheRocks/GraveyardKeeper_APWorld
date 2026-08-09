import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, FrozenSet, Dict, Set, Counter, override

from BaseClasses import ItemClassification, CollectionState


class DLCType(enum.Enum):
    BASE_GAME = enum.auto()
    STRANGER_SINS = enum.auto()
    GAME_OF_CRONE = enum.auto()
    BETTER_SAVE_SOUL = enum.auto()

class ChurchLevel(enum.Enum):
    CLOSED = enum.auto()
    OPEN = enum.auto()
    BIG = enum.auto()
    CATHEDRAL = enum.auto()

@dataclass
class EventData:
    location_label: str
    item_label: str
    #parent_region: str


@dataclass
class RegionData:
    label: str
    dlc: DLCType
    locations: List[str]
    events: List[str]
    connections: List[str]


@dataclass
class LocationData:
    label: str
    parent_region: str


@dataclass
class ItemData:
    label: str
    classification: ItemClassification

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
            workstations: FrozenSet[str],
            required_recipe_item: str,
            ingredients: FrozenSet[str],
            regions: FrozenSet[str],
    ) -> None:
        super().__init__(
            name,
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
            workstations: FrozenSet[str],
            required_recipe_item: str,
            ingredients: FrozenSet[str],
            regions: FrozenSet[str],
            crafting_group: str,
            base_modifier: float
    ) -> None:
        super().__init__(
            name,
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
    events: Dict[str, EventData]
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

@dataclass(frozen=True)
class Requirement:
    label: str
    count: int = 1


@dataclass(frozen=True)
class QualityRequirement:
    label: str
    additional_modifier: float


class RecipeDependencies(ABC):
    workstations: frozenset[str]
    requirements: frozenset[Requirement]

    def __init__(self, workstations: List[str], requirements: list[Requirement]):
        self.workstations = frozenset(workstations)
        self.requirements = frozenset(requirements)

    @property
    @abstractmethod
    def is_quality(self):
        pass

    def are_fulfilled(self, state: CollectionState, player: int) -> bool:
        has_workstation = not self.workstations or state.has_any(self.workstations, player)
        has_requirements = [
            (req.label, req.count, state.has(req.label, player, req.count))
            for req in self.requirements
        ]

        #print("Workstations: ", rule.workstations, "=>", has_workstation)
        #print("Requirements: ", has_requirements)

        return has_workstation and all(ok for _, _, ok in has_requirements)


class SimpleRecipeDependencies(RecipeDependencies):
    def __init__(self, workstations: List[str], requirements: list[Requirement]):
        super().__init__(workstations, requirements)

    @property
    def is_quality(self):
        return False


class QualityRecipeDependencies(RecipeDependencies):
    base_modifier: float
    perk_requirements: frozenset[QualityRequirement]

    def __init__(
            self,
            workstations: List[str],
            requirements: list[Requirement],
            base_modifier: float,
            quality_requirements: list[QualityRequirement]
    ):
        super().__init__(workstations, requirements)
        self.base_modifier = base_modifier
        self.quality_requirements = frozenset(quality_requirements)

    def is_quality(self):
        return True

    @override
    def are_fulfilled(self, state: CollectionState, player: int) -> bool:
        has_basic_reqs = super(QualityRecipeDependencies, self).are_fulfilled(state, player)
        if not has_basic_reqs:
            return False

        chance = self.base_modifier
        for q_req in self.quality_requirements:
            chance += state.has(q_req.label, q_req.additional_modifier)

        return 0.5 <= chance <= 1.5