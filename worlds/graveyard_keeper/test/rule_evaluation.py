from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from rule_builder.rules import Rule

from ..data import data
from ..logic.custom_rules import CanGet, HasHappiness
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
    """Build the maximum AP-item state without constructing a MultiWorld."""
    counts: dict[str, int] = {}

    for item_key, item in data.items.items():
        # Individual stages are replaced by their progressive item in the pool.
        if item_key in data.progressive_items_reverse:
            continue

        count = item.amount
        if item_key in data.progressive_items:
            count = len(data.progressive_items[item_key])
        counts[item.label] = count

    return FakeState(counts=counts)


def find_acquisition_cycle(item_key: str, stack: tuple[str, ...] = ()) -> tuple[str, ...] | None:
    """Find one recursive CanGet/CanCraft dependency path without resolving rules."""
    if item_key in stack:
        cycle_start = stack.index(item_key)
        return (*stack[cycle_start:], item_key)

    resolved_key = data.progressive_items_reverse.get(item_key)
    if resolved_key is not None:
        item_key = resolved_key.key
    if item_key in data.items:
        return None

    next_stack = (*stack, item_key)
    for recipe in data.recipes.get(item_key, ()):
        dependencies = [*recipe.workstations, *recipe.ingredients]
        if recipe.required_recipe_item:
            dependencies.append(recipe.required_recipe_item)
        for dependency in dependencies:
            cycle = find_acquisition_cycle(dependency, next_stack)
            if cycle is not None:
                return cycle
    return None


class QuestRuleEvaluator:
    """Fast quest diagnostics using production rules and lightweight fakes."""

    def __init__(self, world: FakeWorld | None = None, state: FakeState | None = None):
        self.world = world or FakeWorld()
        self.state = state or make_all_items_state()
        self._cache: dict[str, RuleEvaluation] = {}

    def evaluate_all(self) -> dict[str, RuleEvaluation]:
        return {event_key: self.evaluate(event_key) for event_key in data.events}

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
