from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from BaseClasses import DEFAULT_COLLECTION_RULE, ItemClassification
from rule_builder.rules import Rule
from ..data import CRAFTING_EVENT_PREFIX, CRAFTING_REGION_KEY, data
from ..items import GraveyardKeeperItem
from ..locations import GraveyardKeeperLocation
from .custom_rules import build_crafting_event_rule
from ..models import EventData
from ..regions import enabled_dlcs

if TYPE_CHECKING:
    from ..world import GraveyardKeeperWorld


# Recipe and blueprint ownership, including gathering/extraction and progressive
# recipes. These prefixes are the existing shared-data categories, not a QoL list.
RECIPE_ITEM_NAMES = frozenset(
    item.label for key, item in data.items.items()
    if key.startswith(("ITEM_LEARN_", "ITEM_BP_"))
)


@dataclass(frozen=True)
class ProgressionPlan:
    required_items: frozenset[str]
    required_events: frozenset[str]


def build_progression_plan(world: GraveyardKeeperWorld) -> ProgressionPlan:
    """Follow active rules back through events; instantiate crafting on demand.

    Addressed checks, entrances and completion are roots. An internal event is
    never a root merely because it has a definition in the global catalogue.
    """
    events_by_item = {event.item_label: (key, event) for key, event in data.events.items()}
    pending = [location.access_rule for location in world.get_locations() if location.address is not None]
    pending.extend(entrance.access_rule for entrance in world.multiworld.get_entrances(world.player))
    pending.append(world.multiworld.completion_condition[world.player])
    required_items: set[str] = set()
    required_events: set[str] = set()
    visited_locations: set[str] = set()

    def require_event(key: str, event: EventData) -> None:
        if key in required_events:
            return
        required_events.add(key)
        if key.startswith(CRAFTING_EVENT_PREFIX):
            region = world.get_region(data.regions[CRAFTING_REGION_KEY].label)
            region.add_event(event.location_label, event.item_label,
                             location_type=GraveyardKeeperLocation, item_type=GraveyardKeeperItem)
            world.set_rule(world.get_location(event.location_label),
                           build_crafting_event_rule(key.removeprefix(CRAFTING_EVENT_PREFIX)))
        pending.append(world.get_location(event.location_label).access_rule)

    while pending:
        rule = pending.pop()
        if rule is DEFAULT_COLLECTION_RULE.__func__:
            continue
        if not isinstance(rule, Rule.Resolved):
            raise TypeError(f"Progression analysis requires declared Rule Builder dependencies: {rule!r}")
        for name in sorted(rule.item_dependencies()):
            if name in required_items:
                continue
            required_items.add(name)
            if name in events_by_item:
                require_event(*events_by_item[name])
        for name in sorted(rule.location_dependencies()):
            if name in visited_locations:
                continue
            visited_locations.add(name)
            location = world.get_location(name)
            if location.item and location.item.name in events_by_item:
                require_event(*events_by_item[location.item.name])
            else:
                pending.append(location.access_rule)

    # Remove unused quest/misc events as well: their rules must not retain
    # dependencies on recipes that have just become filler/useful.
    for location in list(world.get_locations()):
        if location.address is None and location.item:
            entry = events_by_item.get(location.item.name)
            if entry and entry[0] not in required_events:
                location.parent_region.locations.remove(location)

    items_by_name = {item.label: item for item in data.items.values()}
    allowed_dlcs = enabled_dlcs(world)
    for name in required_items & items_by_name.keys():
        if items_by_name[name].dlc not in allowed_dlcs:
            raise ValueError(f"Active logic requires disabled DLC item {name!r}")
        if name not in RECIPE_ITEM_NAMES:
            item = items_by_name[name]
            if not item.classification & ItemClassification.progression:
                raise ValueError(f"Active logic requires non-progression item {name!r}")

    # Provisional quest rules were resolved before their unused events were
    # removed. Only retained rules belong in the runtime invalidation cache.
    for dependencies in (world.rule_item_dependencies, world.rule_region_dependencies,
                         world.rule_location_dependencies, world.rule_entrance_dependencies):
        dependencies.clear()
    active_rules = [location.access_rule for location in world.get_locations()]
    active_rules.extend(entrance.access_rule for entrance in world.multiworld.get_entrances(world.player))
    active_rules.append(world.multiworld.completion_condition[world.player])
    for rule in active_rules:
        if isinstance(rule, Rule.Resolved):
            world.register_rule_dependencies(rule)

    return ProgressionPlan(frozenset(required_items), frozenset(required_events))
