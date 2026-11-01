# Graveyard quality logic

The quest requirements `OLD_GRAVEYARD_5`, `OLD_GRAVEYARD_30` and
`OLD_GRAVEYARD_200` now use the existing `HasGraveyardRating` rule, also used by
the graveyard completion goal. Positive thresholds require access to the Old
Graveyard. A goal rating of zero retains its existing immediate-completion
behavior and has no input dependencies.

`logic/graveyard_rating.json` owns the decoration values, alternative patch
occupancies, fence scores and state prerequisites. The calculator scores each
patch independently and selects its highest attainable configuration. Alternative
decorations replace one another; they are not all added to the same physical spot.
The existing separate `GravePointCalculator` still supplies the individual-grave
score. This change does not replace its corpse/organ or progressive decoration
model.

## Evidence and corrected prerequisites

Object scores were cross-checked against the original `game_data` in
`Graveyard Keeper_Data/resources.assets`, path ID 150260, Unity 2020.3.17f1.
As described for church and tavern quality, the old JSON dumps omit private
quality expressions; their zero `default_value` fields are not the real scores.

| Source | Points |
| --- | ---: |
| `grass_sward_2x3/2x4/2x6` | 2 / 3 / 4 |
| `road_marble` | 3 |
| `flowerbed_2x2`, `pray_stand_wd` | 2 |
| `lantern_3`, `pray_stand_stn` | 4 |
| `columbarium_stone/marble` | 12 / 20 |
| `gate_wood_new_f_0_qual` | 10 |
| `gate_stone_ancient_grille_open` | 20 |
| `bishop_statue` | 5 |

The original FlowGraphs and client contract establish the state inputs:

* **Western expansion:** `graveyard_zone_lvlup2` charges
  `scroll_graveyard_prop:1` on the unlocking interaction and enables the second
  build zone. This is the received `ITEM_GRAVEYARD_SCROLL`, not completion of
  the Inquisitor's randomized permission reward. The shared client grant maps
  that AP item to `scroll_graveyard_prop`. Receiving the document makes the
  material-free interaction possible; no synthetic quest event is introduced.
* **Church stage:** collected `EVENT_CHURCH_OPEN`,
  `EVENT_BISHOP_UPGRADE_TO_BIG_CHURCH` and
  `EVENT_BISHOP_REPORT_CATHEDRAL_UPGRADE` events replace the old unconditional
  `ChurchLevel.BIG` placeholder. Rating 5 does not assume a future church opening.
* **Fence:** `npc_bishop` array node 412 (`$id: 1009`) unlocks
  `graveyard_builddesk::graveyard_fence_2_upgr` in the big-church aftermath.
  `graveyard_fence_2_upgr` unlocks the stone upgrade and replaces the gate with
  its 10-point variant. The stone upgrade replaces that gate with the 20-point
  variant. Therefore both upgrades require the big-church stage, and the stone
  score also requires access to the wooden fence's materials. The scores do not
  stack. A small open church alone does not unlock the wooden fence.
* **Statue:** `EVENT_BISHOP_BUILD_STATUE` represents constructing the 5-point
  object. It can help the 200-point task before the final cathedral report.
  Cathedral status alone does not grant a statue.

The old `has_graveyard_extension() -> False` and
`get_max_church_level() -> ChurchLevel.BIG` placeholders are removed. The resolved
rule declares all new item/event dependencies for progression classification and
cache invalidation, without retaining a World or MultiWorld reference.

## Layout scope

The existing 18 authored patch configurations are retained, now stored as data.
The original scene's `World/ZONES/Graveyard_Buildzone/graveyard_buildzone` and
`graveyard_buildzone_2` colliders confirm the small corner areas and the
8 x 10, 7 x 10, 8 x 6, 7 x 6 and 15 x 6 main rectangles. The eastern side
provides the original nine patches; the received document enables the western
nine. Mirror configurations and their regression scores remain unchanged.

This is the best score among the authored layouts, not a new exhaustive packing
solver. The previous layout assumption of cleared vegetation is retained:
partially obstructed western patches before large-tree felling are not separately
modeled. No claim is made that this update fully audits individual corpse
engineering, grave decoration materials, or every possible layout.

## Compatibility and validation

No item/location names, network IDs, options, client grants or slot-data keys
change. The companion client continues observing the same Bishop dialogue checks;
the APWorld now enforces their existing numeric requirements during generation.
Generate a new seed to use the corrected logic.

`test_graveyard_rating.py` covers the three authored quest thresholds, positive
and negative access, the first five points before church opening, received versus
rewarded permission, fence order, statue timing, alternative decorations, all
Game of Crone/Better Save Soul combinations, declared dependencies and collecting/
removing expansion/statue inputs with caching enabled. The existing goal tests
cover zero rating, generation, deterministic progression classification and filling.

Three old assertions/fixtures were corrected based on the native flows: the
wooden-fence test now uses the big church, stone-fence fixtures include the
preceding wooden upgrade, and cathedral status no longer produces a free statue.
The positive statue-plus-fence case still verifies a total of 25. No tests were
deleted or weakened to bypass a generation failure. No TODO quest prerequisites
were added.
