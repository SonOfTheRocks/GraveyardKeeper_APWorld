from BaseClasses import Tutorial
from worlds.AutoWorld import WebWorld

from .options import option_groups, option_presets

class GraveyardKeeperWebWorld(WebWorld):
    game = "Graveyard Keeper"

    theme = "stone"

    setup_en = Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up Graveyard Keeper for Multiworld.",
        "English",
        "setup_en.md",
        "setup/en",
        ["SonOfTheRocks"]
    )

    # TODO: setup_de

    tutorials = [setup_en]

    options_groups = option_groups
    options_presets = option_presets