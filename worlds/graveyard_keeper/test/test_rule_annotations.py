"""Rule annotations must resolve for runtime type inspection and static analysis."""
from typing import get_type_hints

from ..logic import custom_rules
from ..world import GraveyardKeeperWorld


def test_crafting_quality_world_annotation_resolves():
    namespace = vars(custom_rules) | {"GraveyardKeeperWorld": GraveyardKeeperWorld}
    hints = get_type_hints(custom_rules.HasCraftingQuality._instantiate, globalns=namespace)
    assert hints["world"] is GraveyardKeeperWorld
