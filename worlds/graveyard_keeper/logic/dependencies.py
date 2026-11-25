"""Dependency declarations for calculators with independently optional inputs."""
from typing import TYPE_CHECKING

from rule_builder.rules import And, Rule

if TYPE_CHECKING:
    from ..world import GraveyardKeeperWorld


def optional_dependency_names(rule: Rule, world: "GraveyardKeeperWorld") -> tuple[str, ...]:
    """Collect each input independently, without simplifying their declaration.

    A calculator can still use its other inputs when one input is excluded.
    Resolving the enclosing And would discard every dependency in that case.
    Actual access requirements continue to use normal Rule Builder resolution.
    """
    pending = [rule]
    names: set[str] = set()
    while pending:
        current = pending.pop()
        if isinstance(current, And):
            pending.extend(current.children)
        else:
            names.update(current.resolve(world).item_dependencies())
    return tuple(sorted(names))
