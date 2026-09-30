from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from BaseClasses import ItemClassification
from rule_builder.rules import Rule

from ..data import data
from ..logic.acquisition import (
    get_higher_quality_substitutes,
    get_structurally_acquirable_item_keys,
    recipe_requirements_are_available,
)
from ..logic.custom_rules import CanGet, HasHappiness
from ..models import QuestEventData
from .fakes import FakeState, FakeWorld


@dataclass(frozen=True)
class RuleEvaluation:
    """Structured result used to explain why a rule or quest requirement failed."""

    label: str
    passed: bool
    children: tuple["RuleEvaluation", ...] = ()
    detail: str | None = None

    def format_failed_tree(self, indent: int = 0) -> str:
        """Render only the branches that contribute to this failure."""
        prefix = "  " * indent
        status = "PASS" if self.passed else "FAIL"
        line = f"{prefix}- [{status}] {self.label}"
        if self.detail and self.detail != self.label:
            line += f": {self.detail}"

        failed_children = tuple(child for child in self.children if not child.passed)
        if not failed_children:
            return line
        return "\n".join(
            [line, *(child.format_failed_tree(indent + 1) for child in failed_children)]
        )


@dataclass(frozen=True)
class AcquisitionEdge:
    source: str
    target: str
    recipe_index: int
    dependency_kind: str


@dataclass(frozen=True)
class AcquisitionCycleGroup:
    nodes: frozenset[str]
    internal_edges: tuple[AcquisitionEdge, ...]
    example_cycle: tuple[AcquisitionEdge, ...]
    independent_entries: tuple[str, ...]
    affected_quest_requirements: tuple[str, ...]

    def format(self) -> str:
        cycle_lines = ["Representative cycle:"]
        cycle_lines.extend(
            f"  {edge.source} --{_format_edge(edge)}--> {edge.target}"
            for edge in self.example_cycle
        )
        entry_lines = ["Independent acquisition entries:"]
        entry_lines.extend(f"  - {entry}" for entry in self.independent_entries)
        quest_lines = ["Affected quest requirements:"]
        quest_lines.extend(f"  - {requirement}" for requirement in self.affected_quest_requirements)
        return "\n".join([
            f"Cyclic component ({len(self.nodes)} nodes): {', '.join(sorted(self.nodes))}",
            *cycle_lines,
            *entry_lines,
            *quest_lines,
        ])


def _format_edge(edge: AcquisitionEdge) -> str:
    if edge.recipe_index < 0:
        return edge.dependency_kind
    return f"recipe {edge.recipe_index} {edge.dependency_kind}"


def find_all_acquisition_cycle_groups() -> tuple[AcquisitionCycleGroup, ...]:
    """Return every cyclic component in the complete crafting dependency graph."""
    graph = _build_acquisition_graph()
    components = _strongly_connected_components(graph)
    cyclic_components = [
        component
        for component in components
        if len(component) > 1
        or any(edge.target == next(iter(component)) for edge in graph.get(next(iter(component)), ()))
    ]

    quest_requirements = [
        (event_key, item_key)
        for event_key, event in data.events.items()
        if isinstance(event, QuestEventData)
        for item_key in event.required_craft_items
    ]
    groups: list[AcquisitionCycleGroup] = []
    for component in cyclic_components:
        internal_edges = tuple(
            edge
            for source in sorted(component)
            for edge in graph.get(source, ())
            if edge.target in component
        )
        groups.append(AcquisitionCycleGroup(
            frozenset(component),
            internal_edges,
            _find_example_cycle(graph, component),
            _find_independent_acquisition_entries(component),
            tuple(
                f"{event_key} requires {item_key}"
                for event_key, item_key in quest_requirements
                if _can_reach_component(item_key, component, graph)
            ),
        ))
    return tuple(sorted(groups, key=lambda group: sorted(group.nodes)))


def _build_acquisition_graph() -> dict[str, tuple[AcquisitionEdge, ...]]:
    graph: dict[str, list[AcquisitionEdge]] = {item_key: [] for item_key in data.recipes}
    for item_key, recipes in data.recipes.items():
        for recipe in recipes:
            dependencies = [
                *((workstation, "workstation") for workstation in recipe.workstations),
                *((ingredient, "ingredient") for ingredient in recipe.ingredients),
            ]
            if recipe.required_recipe_item:
                dependencies.append((recipe.required_recipe_item, "recipe unlock"))
            for dependency, dependency_kind in dependencies:
                resolved_dependency = data.progressive_items_reverse.get(dependency)
                if resolved_dependency is not None:
                    dependency = resolved_dependency.key
                if dependency in data.recipes:
                    graph[item_key].append(AcquisitionEdge(
                        item_key,
                        dependency,
                        recipe.index,
                        dependency_kind,
                    ))
        for higher_quality_key in get_higher_quality_substitutes(item_key):
            graph[item_key].append(AcquisitionEdge(
                item_key,
                higher_quality_key,
                -1,
                "higher-quality substitute",
            ))
    return {item_key: tuple(edges) for item_key, edges in graph.items()}


def _strongly_connected_components(
        graph: dict[str, tuple[AcquisitionEdge, ...]],
) -> list[set[str]]:
    index = 0
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[set[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indexes[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for edge in graph.get(node, ()):
            target = edge.target
            if target not in indexes:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indexes[target])

        if lowlinks[node] != indexes[node]:
            return
        component: set[str] = set()
        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.add(member)
            if member == node:
                break
        components.append(component)

    for node in graph:
        if node not in indexes:
            visit(node)
    return components


def _find_example_cycle(
        graph: dict[str, tuple[AcquisitionEdge, ...]],
        component: set[str],
) -> tuple[AcquisitionEdge, ...]:
    start = min(component)

    def search(node: str, path: tuple[AcquisitionEdge, ...], seen: set[str]) -> tuple[AcquisitionEdge, ...] | None:
        for edge in graph.get(node, ()):
            if edge.target not in component:
                continue
            if edge.target == start:
                return (*path, edge)
            if edge.target in seen:
                continue
            result = search(edge.target, (*path, edge), {*seen, edge.target})
            if result is not None:
                return result
        return None

    return search(start, (), {start}) or ()


def _find_independent_acquisition_entries(component: set[str]) -> tuple[str, ...]:
    available_item_keys = get_structurally_acquirable_item_keys(
        frozenset(component)
    )
    entries: list[str] = []
    for item_key in sorted(component):
        entries.extend(
            f"{item_key} sold by {vendor_key}"
            for vendor_key, vendor in data.vendors.items()
            if item_key in vendor.sells_all
        )
        for recipe in data.recipes[item_key]:
            if recipe_requirements_are_available(recipe, available_item_keys):
                entries.append(f"{item_key} recipe {recipe.index}")
    return tuple(entries)


def _can_reach_component(
        item_key: str,
        component: set[str],
        graph: dict[str, tuple[AcquisitionEdge, ...]],
) -> bool:
    pending = [item_key]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current in component:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(edge.target for edge in graph.get(current, ()))
    return False


def evaluate_resolved_rule(
        label: str,
        rule: Rule.Resolved,
        state: FakeState,
) -> RuleEvaluation:
    """Evaluate a resolved rule while retaining its nested failure structure."""
    passed = rule(state)
    resolved_children: Iterable[Rule.Resolved] = getattr(rule, "children", ())
    children = tuple(
        evaluate_resolved_rule(str(child), child, state)
        for child in resolved_children
    )
    detail = None if children else rule.explain_str(state)
    return RuleEvaluation(label, passed, children, detail)


def make_all_items_state() -> FakeState:
    """Build the maximum item and event state without constructing a MultiWorld."""
    counts: dict[str, int] = {}

    for item_key, item in data.items.items():
        if not item.classification & ItemClassification.progression:
            continue
        # Individual stages are replaced by their progressive item in the pool.
        if item_key in data.progressive_items_reverse:
            continue

        count = item.amount
        if item_key in data.progressive_items:
            count = len(data.progressive_items[item_key])
        counts[item.label] = count

    for event in data.events.values():
        counts[event.item_label] = 1

    return FakeState(counts=counts)


def find_acquisition_cycle(
        item_key: str,
        stack: tuple[str, ...] = (),
        visited: set[str] | None = None,
) -> tuple[str, ...] | None:
    """Find one recursive CanGet/CanCraft dependency path without resolving rules."""
    if visited is None:
        visited = set()

    if item_key in stack:
        cycle_start = stack.index(item_key)
        return (*stack[cycle_start:], item_key)

    resolved_key = data.progressive_items_reverse.get(item_key)
    if resolved_key is not None:
        item_key = resolved_key.key
    if item_key in data.items:
        return None
    if item_key in visited:
        return None

    next_stack = (*stack, item_key)
    for recipe in data.recipes.get(item_key, ()):
        dependencies = [*recipe.workstations, *recipe.ingredients]
        if recipe.required_recipe_item:
            dependencies.append(recipe.required_recipe_item)
        for dependency in dependencies:
            cycle = find_acquisition_cycle(dependency, next_stack, visited)
            if cycle is not None:
                return cycle
    visited.add(item_key)
    return None


class QuestRuleEvaluator:
    """Fast quest diagnostics using production rules and lightweight fakes."""

    def __init__(self, world: FakeWorld | None = None, state: FakeState | None = None):
        self.world = world or FakeWorld()
        self.state = state or make_all_items_state()
        self._cache: dict[str, RuleEvaluation] = {}

    def evaluate_all(self) -> dict[str, RuleEvaluation]:
        return {
            event_key: self.evaluate(event_key)
            for event_key, event in data.events.items()
            if isinstance(event, QuestEventData)
        }

    def evaluate(self, event_key: str, stack: tuple[str, ...] = ()) -> RuleEvaluation:
        cached = self._cache.get(event_key)
        if cached is not None:
            return cached

        if event_key in stack:
            cycle_start = stack.index(event_key)
            cycle = (*stack[cycle_start:], event_key)
            return RuleEvaluation(
                f"quest {event_key}",
                False,
                detail=f"dependency cycle: {' -> '.join(cycle)}",
            )

        quest = data.events[event_key]
        next_stack = (*stack, event_key)
        children: list[RuleEvaluation] = []

        for required_quest in sorted(quest.required_quests):
            # TODO prerequisites intentionally have no effect in production yet.
            if required_quest.startswith("TODO"):
                continue
            children.append(self.evaluate(required_quest, next_stack))

        for happiness in sorted(quest.required_happiness, key=lambda value: (value.npc, value.value)):
            rule = HasHappiness(happiness).resolve(self.world)
            children.append(evaluate_resolved_rule(
                f"happiness {happiness.npc} >= {happiness.value}",
                rule,
                self.state,
            ))

        for item_key in sorted(quest.required_quest_items):
            item = data.items[item_key]
            actual = self.state.count(item.label, self.world.player)
            children.append(RuleEvaluation(
                f"quest item {item_key}",
                actual >= 1,
                detail=f"{item.label}: {actual}/1",
            ))

        for item_key in sorted(quest.required_craft_items):
            try:
                rule = CanGet(item_key).resolve(self.world)
            except RecursionError:
                cycle = find_acquisition_cycle(item_key)
                detail = "dependency cycle while resolving acquisition rule"
                if cycle is not None:
                    detail = f"dependency cycle: {' -> '.join(cycle)}"
                children.append(RuleEvaluation(
                    f"get {item_key}",
                    False,
                    detail=detail,
                ))
            else:
                children.append(evaluate_resolved_rule(
                    f"get {item_key}",
                    rule,
                    self.state,
                ))

        # Area-point requirements are data-only until the corresponding area
        # calculators are implemented in production logic.

        evaluation = RuleEvaluation(
            f"quest {event_key}",
            all(child.passed for child in children),
            tuple(children),
        )
        self._cache[event_key] = evaluation
        return evaluation

    @staticmethod
    def failure_frontier(
            evaluations: dict[str, RuleEvaluation],
    ) -> dict[str, RuleEvaluation]:
        """Return failed quests that are not merely blocked by another failed quest."""
        failed = {event_key for event_key, result in evaluations.items() if not result.passed}
        frontier = {
            event_key: evaluations[event_key]
            for event_key in sorted(failed)
            if not any(
                required_quest in failed
                for required_quest in data.events[event_key].required_quests
                if not required_quest.startswith("TODO")
            )
        }

        # A dependency cycle has no frontier because every member is blocked by
        # another failed member. Returning all failures is intentionally noisy,
        # but ensures cycles can never make this diagnostic test pass silently.
        if failed and not frontier:
            return {
                event_key: evaluations[event_key]
                for event_key in sorted(failed)
            }
        return frontier
