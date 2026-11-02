# Traps

Set the player option `trap_percentage` to an integer from 0 to 100:

```yaml
Graveyard Keeper:
  trap_percentage: 25
  bats_trap_weight: 50
  green_slime_trap_weight: 50
```

The default is 0 (disabled). The percentage applies to filler copies after the
normal pool has been balanced against available locations, rounded down. At 25,
one quarter of those filler copies become traps. Useful and progression
items are preserved, including recipes dynamically promoted by active logic.
Recipes classified as filler may be replaced. Pool size is unchanged.

`Bats Trap` spawns four bats, and `Green Slime Trap` spawns four green slimes near
the receiving player. The seed chooses the item type using relative weights
`bats_trap_weight` and `green_slime_trap_weight` (0–100, default 50 each). A zero
weight disables that type. Weights 1/3 and 25/75 are equivalent. If traps are
enabled, at least one weight must be positive; both zero produces a generation
error. When `trap_percentage` is 0, both weights may be zero.

The client queues traps while normal gameplay
is unavailable and spaces activations by at least ten seconds. Pending traps
are part of the AP save record and are not replayed when receipt history is
received again. Technology previews show each monster as the main icon, with a
skull in the native quality/star corner. Foreign-game rewards keep the AP main
icon and use the same skull badge when their server flags classify them as traps.

Shared data version 8 is required by both APWorld and client. The two items use
explicit IDs 488 (bats) and 489 (green slimes). There is no general random trap
or compatibility path; its pre-release definition was removed. ID 487 is unused
and has no reservation. Other item IDs remain unchanged.
Older seeds must be regenerated for this client, even if traps are disabled.

The queue commits consumption before spawning, so a partially failing spawn
cannot repeatedly create monsters. A failed spawn is logged as an error and
consumed; it does not block subsequent items or traps. Native in-game spawning
and monster persistence still need a manual gameplay check with the updated
client and a version 8 seed.
