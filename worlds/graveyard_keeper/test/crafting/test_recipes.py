import unittest

from test.param import classvar_matrix
from ..fakes import FakeState, FakeWorld
from ...logic.custom_rules import CanCraftRecipe
from ...data import data
from ...models import RecipeData


def _iter_recipes():
    for item_key in sorted(data.recipes):
        for recipe in data.recipes[item_key]:
            yield item_key, recipe.index

PERKS = [
    data.items["ITEM_PERK_"+k].label
    for k in [
        "WRITER",
        "PLAYWRIGHT",
        "JEWELER",
        "WINE_MASTER",
        "BLACKSMITH",
        "ENGINEER",
        "CARPENTER",
        "MASON",
        "INDUSTRIOUSNESS",
    ]
]


@classvar_matrix(
    recipe=list(_iter_recipes()),
)
class TestCraftingRules(unittest.TestCase):
    recipe: tuple[str, int]

    def _get_recipe(self) -> tuple[str, RecipeData]:
        item_key, recipe_index = self.recipe
        recipe = next(
            r for r in data.recipes[item_key]
            if r.index == recipe_index
        )
        return item_key, recipe

    def test_recipe_is_satisfiable(self):
        item_key, recipe = self._get_recipe()

        world = FakeWorld()
        rule = CanCraftRecipe(recipe)

        all_apitems = (i.label for i in data.items)
        world.state = FakeState(all_apitems)

        self.assertTrue(
            rule.resolve(world),
            f"{item_key} not craftable with full requirements",
        )
