from dataclasses import dataclass

from Options import Toggle, OptionGroup, PerGameCommonOptions, Choice, Range


class Goal(Choice):
    """
    Goal for this playthrough

    Portal: Enter the portal on Witch Hill (Not yet implemented)
    Graveyard: Reach a certain graveyard rating (specified in ...)
    """
    display_name = "Goal"

    option_portal = 0
    option_graveyard = 1

    default = option_portal

class GraveyardGoalRating(Range):
    """
    Sets the graveyard rating required to complete the Graveyard goal.

    Increasing this value will require more progress in improving your graveyard,
    including better corpse preparation, decorations, upgrading the church and buying the graveyard extension.

    Note: This option only has an effect if the goal is set to "Graveyard".
    """
    display_name = "Graveyard Goal Rating"
    range_start = 0
    range_end = 2484
    default = 500


class VendorLogic(Choice):
    """
    Determines whether buying items from vendors is considered in logic.

    Out of Logic: Buying optional vendor items is never required. If buying a
    particular vendor item is mandatory for game progression, the purchase is
    considered in logic once that item's vendor is reachable and the church is
    open.

    Require Money Source: Buying vendor items is considered in logic once their
    vendor is reachable and the church is open. The open church is currently
    used to represent access to a reliable source of money.

    Always Available: Buying vendor items is considered in logic as soon as
    their vendor is reachable. The player still needs enough money to make the
    purchase, but access to a money source is not required by logic.
    """
    display_name = "Vendor Logic"

    option_out_of_logic = 0
    option_require_money_source = 1
    option_always_available = 2

    default = option_out_of_logic


class StrangerSins(Toggle):
    """
    Add Stranger Sins' quest rewards to the pool.

    To use this option, you must own the "Stranger Sins" DLC.
    """
    display_name = "Stranger Sins"

class GameOfCrone(Toggle):
    """
    Add Game Of Crone's quest rewards and technology unlocks to the pool.

    To use this option, you must own the "Game Of Crone" DLC.
    """
    display_name = "Game Of Crone"

class BetterSaveSoul(Toggle):
    """
    Add Better Save Soul's technology tree unlocks to the pool.

    To use this option, you must own the "Better Save Soul" DLC.
    """
    display_name = "Better Save Soul"

@dataclass
class GraveyardKeeperOptions(PerGameCommonOptions):
    goal: Goal
    graveyard_goal_rating: GraveyardGoalRating
    vendor_logic: VendorLogic
    stranger_sins: StrangerSins
    game_of_crone: GameOfCrone
    better_save_soul: BetterSaveSoul

option_groups = [
    OptionGroup("Goal Options", [Goal, GraveyardGoalRating]),
    OptionGroup("Logic Options", [VendorLogic]),
    OptionGroup("DLCs", [StrangerSins, GameOfCrone, BetterSaveSoul])
]

option_presets = {
    "default": {
        "goal": Goal.option_portal,
        "graveyard_goal_rating": GraveyardGoalRating.default,
        "vendor_logic": VendorLogic.default,
        "stranger_sins": True,
        "game_of_crone": True,
        "better_save_soul": True,
    }
}
