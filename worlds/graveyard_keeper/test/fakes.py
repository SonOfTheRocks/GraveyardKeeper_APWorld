class FakeState:
    def __init__(self, items, counts=None):
        self.items = items
        self.counts = counts or {}

    def has(self, item, player, count=1):
        return item in self.items

    def has_all(self, items, player):
        return all(i in self.items for i in items)

    def has_any(self, items, player):
        return any(i in self.items for i in items)

    def count(self, item, player):
        return self.counts.get(item, 0)

class FakeWorld:
    def __init__(self, options = None):
        if options is None:
            options = {
                "stranger_sins": True,
                "game_of_crone": True,
                "better_save_soul": True,
            }
        # emulate attribute access (world.options.game_of_crone)
        self.options = type("Opts", (), options)
        self.player = 1

class FakeItem:
    def __init__(self, label):
        self.label = label