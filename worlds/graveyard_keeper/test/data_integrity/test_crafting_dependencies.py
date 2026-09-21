import unittest

from ...data import data
from ..rule_evaluation import find_acquisition_cycle, find_all_acquisition_cycle_groups


class TestCraftingDependencies(unittest.TestCase):

    def test_complete_crafting_graph_has_no_dependency_cycles(self):
        cycle_groups = find_all_acquisition_cycle_groups()
        diagnostics = "\n\n".join(group.format() for group in cycle_groups)
        self.assertFalse(
            cycle_groups,
            "The complete crafting graph contains cyclic dependency groups:\n"
            f"{diagnostics}",
        )

    def test_quest_crafting_requirements_have_no_dependency_cycles(self):
        affected_requirements: dict[tuple[str, ...], list[str]] = {}
        for event_key, event in data.events.items():
            for item_key in event.required_craft_items:
                cycle = find_acquisition_cycle(item_key)
                if cycle is None:
                    continue
                cycle_nodes = cycle[:-1]
                canonical_nodes = min(
                    cycle_nodes[index:] + cycle_nodes[:index]
                    for index in range(len(cycle_nodes))
                )
                canonical_cycle = (*canonical_nodes, canonical_nodes[0])
                affected_requirements.setdefault(canonical_cycle, []).append(
                    f"{event_key} requires {item_key}"
                )

        diagnostics = "\n\n".join(
            f"Cycle: {' -> '.join(cycle)}\n"
            + "\n".join(f"  - {requirement}" for requirement in requirements)
            for cycle, requirements in affected_requirements.items()
        )
        self.assertFalse(
            affected_requirements,
            "Quest crafting requirements contain cyclic acquisition paths:\n"
            f"{diagnostics}",
        )
