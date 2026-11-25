from typing import Set

from test.bases import WorldTestBase
from ..world import GraveyardKeeperWorld
from ..data import data


class GraveyardKeeperTestBase(WorldTestBase):
    game = "Graveyard Keeper"
    world: GraveyardKeeperWorld

    def assertConnectionOpen(self, source: str, dest: str):
        self._assertEntrance(source, dest, True)

    def assertConnectionClosed(self, source: str, dest: str):
        self._assertEntrance(source, dest, False)

    def _assertEntrance(self, source: str, dest: str, expect_open: bool):
        rule = self.world.get_entrance(f"{source} -> {dest}").access_rule
        if expect_open:
            error_msg = f"entrance '{source} -> {dest}' should be open"
        else:
            error_msg = f"entrance '{source} -> {dest}' should be closed"
        self.assertEqual(rule(self.multiworld.state), expect_open, error_msg)

    @staticmethod
    def get_required_ap_items_for(ingame_item: str) -> Set[str]:
        # use requested_items as a cache to avoid recursion
        requested_items: Set[str] = set()
        return GraveyardKeeperTestBase._get_required_ap_items_for(ingame_item, requested_items)

    @staticmethod
    def _get_required_ap_items_for(ingame_item: str, requested_items: Set[str]) -> Set[str]:
        # already requested in another call, stop here to avoid recursion
        if ingame_item in requested_items:
            return set()

        # special case for recycling recipes that are not renewable (and therefore out of logic)
        # TODO: recipes for all the goos
        #if ingame_item in ["ITEM_RUINED_BOOK", "ITEM_METAL_SCRAP", "ITEM_GOO_OF_DEATH"]:
        #    return set()

        requested_items.add(ingame_item)
        required_ap_items: Set[str] = set()

        # no recipe for ingame item, need to be bought
        if ingame_item not in data.recipes.keys():
            assert any([ingame_item in vendor.sells_all for vendor in data.vendors.values()]), \
                f"no recipe nor selling merchant for {ingame_item}"
        else:
            for recipe in data.recipes[ingame_item]:
                if recipe.required_recipe_item is not None:
                    recipe_required = recipe.required_recipe_item
                    if recipe.required_recipe_item in data.progressive_items_reverse.keys():
                        recipe_required = data.progressive_items_reverse[recipe_required].key
                    required_ap_items.add(recipe_required)

                for workstation in recipe.workstations:
                    required_ap_items.update(GraveyardKeeperTestBase._get_required_ap_items_for(workstation, requested_items))

                for ingredient in recipe.ingredients:
                    required_ap_items.update(GraveyardKeeperTestBase._get_required_ap_items_for(ingredient, requested_items))

        return required_ap_items
