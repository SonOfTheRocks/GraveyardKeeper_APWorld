import unittest

from .fakes import FakeState
from ..data import data, CRAFTING_EVENT_PREFIX, CRAFTING_EVENT_LABEL_PREFIX
from ..logic.rule_builder import _build_recipe_dependencies
from ..models import RecipeData, RecipeDependencies

PLAYER = 1

def _get_recipe_parts(recipe: RecipeData):
    workstations = [
        data.events[CRAFTING_EVENT_PREFIX + w].item_label
        for w in recipe.workstations
    ]

    ingredients = []
    for i in recipe.ingredients:
        if i in data.items:
            ingredients.append(data.items[i].label)
        else:
            ingredients.append(data.events[CRAFTING_EVENT_PREFIX + i].item_label)

    required_item = []
    if recipe.required_recipe_item:
        key = recipe.required_recipe_item
        count = 1
        if key in data.progressive_items_reverse:
            reverse_item = data.progressive_items_reverse[key]
            key = reverse_item.key
            count = reverse_item.count

        required_item = [data.items[key].label] * count

    return workstations, ingredients, required_item

def _build_dependency_graph(exclude):
    graph = {}
    for item_key, recipes in data.recipes.items():
        deps = set()

        for recipe in recipes:
            deps.update(recipe.ingredients)
            if recipe.required_recipe_item:
                # collect crafting-only items (the others have other meaning of procurement)
                if recipe.required_recipe_item not in data.items:
                    deps.add(recipe.required_recipe_item)
            deps.update(recipe.workstations)
            deps -= exclude

        graph[item_key] = deps

    return graph

def _find_cycles(graph):
    visited = set()
    stack = set()
    cycles = []

    def visit(node, path):
        if node in stack:
            # found cycle
            cycle_start = path.index(node)
            cycles.append(path[cycle_start:] + [node])
            return

        if node in visited:
            return

        visited.add(node)
        stack.add(node)

        for dep in graph.get(node, []):
            if dep in graph: # only follow craftable nodes
                visit(dep, path + [dep])

        stack.remove(node)

    for node in graph:
        visit(node, [])

    return cycles


class TestCraftingRules(unittest.TestCase):

    def test_all_recipes_are_satisfiable(self):
        for item_key, recipes in data.recipes.items():

            for recipe in recipes:
                if recipe.is_quality:
                    continue

                deps: RecipeDependencies = _build_recipe_dependencies(recipe)
                w, i, r = _get_recipe_parts(recipe)
                state = FakeState(w + i + r)
                self.assertTrue(
                    deps.are_fulfilled(state, PLAYER),
                    f"{item_key} not craftable with full requirements"
                )

    def test_missing_ingredient_breaks_recipe(self):
        for item_key, recipes in data.recipes.items():

            for recipe in recipes:
                deps: RecipeDependencies = _build_recipe_dependencies(recipe)
                w, i, r = _get_recipe_parts(recipe)
                base = w + i + r

                for ingredient in i:
                    state = FakeState([x for x in base if x != ingredient])
                    self.assertFalse(
                        deps.are_fulfilled(state, PLAYER),
                        f"{item_key} still craftable without ingredient {ingredient}")

    def test_missing_required_item_breaks_recipe(self):
        for item_key, recipes in data.recipes.items():

            for recipe in recipes:
                deps: RecipeDependencies = _build_recipe_dependencies(recipe)
                w, i, r = _get_recipe_parts(recipe)
                if not r:
                    continue

                base = w + i + r
                for req in r:
                    state = FakeState([x for x in base if x != req])
                    self.assertFalse(
                        deps.are_fulfilled(state, PLAYER),
                        f"{item_key} still craftable without required item {req}"
                    )

    def test_no_workstation_breaks_recipe(self):
        for item_key, recipes in data.recipes.items():

            for recipe in recipes:
                deps: RecipeDependencies = _build_recipe_dependencies(recipe)
                w, i, r = _get_recipe_parts(recipe)

                if not w:
                    continue

                state = FakeState(i + r) # intentionally no workstation
                self.assertFalse(
                    deps.are_fulfilled(state, PLAYER),
                    f"{item_key} still craftable any workstation"
                )

    def test_missing_single_workstation_still_works(self):
        for item_key, recipes in data.recipes.items():

            for recipe in recipes:
                deps: RecipeDependencies = _build_recipe_dependencies(recipe)
                w, i, r = _get_recipe_parts(recipe)

                if len(w) <= 1:
                    continue

                base = w + i + r
                for removed_ws in w:
                    remaining_ws = [x for x in w if x != removed_ws]
                    state = FakeState(remaining_ws + i + r)
                    self.assertTrue(
                        deps.are_fulfilled(state, PLAYER),
                        f"{item_key} failed with valid alternative workstation"
                    )

    def test_no_recipe_depends_on_itself(self):
        for item_key, recipes in data.recipes.items():
            for recipe in recipes:
                all_deps = set(recipe.workstations)
                if recipe.required_recipe_item:
                    all_deps.add(recipe.required_recipe_item)
                all_deps.update(recipe.ingredients)

                assert item_key not in all_deps, f"{item_key} depends on itself"

    def test_no_cycles(self):
        exclusions = set()
        for vendor in data.vendors.values():
            exclusions.update(vendor.sells_level_1)
        graph = _build_dependency_graph(exclusions)
        cycles = _find_cycles(graph)
        cycles_str = '\n'.join([str(c) for c in cycles])
        self.assertEqual(len(cycles), 0, f"Cycles found: {cycles_str}")
