from collections import Counter

from Options import OptionsMetaProperty

from ..options import BetterSaveSoul, GameOfCrone, StrangerSins, VendorLogic


class FakeOptions(metaclass=OptionsMetaProperty):
    vendor_logic: VendorLogic
    stranger_sins: StrangerSins
    game_of_crone: GameOfCrone
    better_save_soul: BetterSaveSoul

    def __init__(self, values):
        for name, option_type in type(self).type_hints.items():
            setattr(self, name, option_type(values[name]))


class FakeState:
    def __init__(self, items=None, counts=None):
        if items is None:
            items = []
        self.items = set(items)
        self.counts = dict(counts or {})

        for item in self.items:
            self.counts.setdefault(item, 1)
        self.prog_items = {1: Counter(self.counts)}

    def has(self, item, player, count=1):
        return self.count(item, player) >= count

    def has_all(self, items, player):
        return all(self.has(item, player) for item in items)

    def has_any(self, items, player):
        return any(self.has(item, player) for item in items)

    def has_all_counts(self, item_counts, player):
        return all(self.has(item, player, count) for item, count in item_counts.items())

    def has_any_count(self, item_counts, player):
        return any(self.has(item, player, count) for item, count in item_counts.items())

    def count(self, item, player):
        return self.counts.get(item, 0)

    def can_reach_region(self, region, player):
        return True

class FakeWorld:
    def __init__(self, options = None):
        option_values = {
            "vendor_logic": VendorLogic.default,
            "stranger_sins": True,
            "game_of_crone": True,
            "better_save_soul": True,
        }
        option_values.update(options or {})
        self.options = FakeOptions(option_values)
        self.player = 1
        self.state = FakeState()

class FakeItem:
    def __init__(self, label):
        self.label = label
