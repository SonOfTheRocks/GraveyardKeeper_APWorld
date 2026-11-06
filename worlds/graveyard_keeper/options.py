from dataclasses import dataclass

from Options import Toggle, OptionGroup, PerGameCommonOptions, Choice, Range


class Goal(Choice):
    """
    Goal for this playthrough

    Portal: Restore the portal on Witch Hill.
    Graveyard: Reach the rating specified by Graveyard Goal Rating.
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

    Targets above the reachable maximum for the selected DLCs and available items
    are automatically reduced to that maximum under the modeled graveyard layouts.
    The adjustment is logged. Zero completes immediately.
    This option only has an effect if the goal is set to "Graveyard".
    """
    display_name = "Graveyard Goal Rating"
    range_start = 0
    range_end = 2484
    default = 500


class VendorLogic(Choice):
    """
    Determines when the randomizer may require purchasing items from vendors.

    Out of Logic: Purchases are only required for items whose only modeled
    source is a vendor, such as Silk or a Whetstone. These purchases require
    access to the vendor and a reliable source of income.

    Require Money Source: Purchases may be required once the vendor is
    accessible and a reliable source of income is available.

    Always Available: Purchases may be required as soon as the vendor is
    accessible, without requiring a source of income.

    A reliable source of income currently means having the church open.
    Individual prices and your current money are not tracked by logic.
    You will still need to earn enough money to make required purchases.
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


class TrapPercentage(Range):
    """Percentage of filler items replaced with monster traps.

    Useful and progression items are never replaced. A trap spawns a small group
    of monsters near the player once normal gameplay resumes. Zero disables
    generated traps. The percentage is rounded down to a whole item count.
    """
    display_name = "Trap Percentage"
    range_start = 0
    range_end = 100
    default = 0


class BatsTrapWeight(Range):
    """Relative weight of Bats Trap when generating traps. Each spawns four bats.

    Zero disables this trap type. 50/50 gives both types equal chances; 100/0
    generates only bats. At least one weight must be positive when traps are enabled.
    """
    display_name = "Bats Trap Weight"
    range_start = 0
    range_end = 100
    default = 50


class GreenSlimeTrapWeight(Range):
    """Relative weight of Green Slime Trap. Each spawns four green slimes.

    Zero disables this trap type. Weights are relative and do not need to add up
    to 100. At least one weight must be positive when traps are enabled.
    """
    display_name = "Green Slime Trap Weight"
    range_start = 0
    range_end = 100
    default = 50


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
    trap_percentage: TrapPercentage
    bats_trap_weight: BatsTrapWeight
    green_slime_trap_weight: GreenSlimeTrapWeight
    stranger_sins: StrangerSins
    game_of_crone: GameOfCrone
    better_save_soul: BetterSaveSoul

option_groups = [
    OptionGroup("Goal Options", [Goal, GraveyardGoalRating]),
    OptionGroup("Logic Options", [VendorLogic]),
    OptionGroup("Trap Options", [TrapPercentage, BatsTrapWeight, GreenSlimeTrapWeight]),
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
