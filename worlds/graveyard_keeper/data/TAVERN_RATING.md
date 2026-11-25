# Talking Skull quality (Stranger Sins)

`TavernPointCalculator` computes the highest attainable quality of the player's
Talking Skull tavern. `HasTavernRating` supports `required_area_points` entries
such as `TAVERN_40`, requires access to the opened tavern, and resolves to false
without any DLC dependencies when Stranger Sins is disabled.

Adam's Clay Shards quest requires **40 quality**, through the preceding
rewardless tavern-report dialogue. Koukol's existing quest does **not** use a quality threshold. The former
`TAVERN_40` entry was an incorrect assumption and is replaced by access to the
materials for Table II, following his recipe-unlocking conversation. The general
tavern-rating rule is used by Adam's existing quest.

## Original game evidence

Values were read from the installed game's `Graveyard Keeper_Data/resources.assets`,
`game_data` path ID 150260 (Unity 2020.3.17f1), using the same private-field-aware
extraction as the church calculator. The older JSON dumps omit the actual
`SmartExpression._expression` and inventory values. The companion checkout's
`WorldGameObject.quality` and `WorldZone.GetTotalQuality` explain how object and
inventory quality are added. No original dumps, decompiled sources or game assets
were changed.

| Source | Quality | Availability/capacity |
| --- | ---: | --- |
| `tavern_table_1` | 5 | Two table patches initially, four after expansion |
| `tavern_table_2` | 10 | Same patches; unlocked on returning to Koukol for the dark organ |
| `tavern_fireplace` | 5 | Spawned automatically by `tavern_upgrade` |
| `tavern_barrel_no_buildzone` | 3 | Spawned automatically by `tavern_upgrade` |
| `tavern_barrel` | 3 each | Two additional barrel patches after expansion |
| `tavern_artifacts_shelves` | 5 | One fixed location |
| `rat_race_table` | 5 | One fixed location, unlocked by Snake's ancient-amulet conversation |
| Each displayed artifact | 1 | Seventeen distinct artifacts, one of each |

`level3` contains `PLAYERS_TAVERN_INSIDE/players_tavern_first/players_tavern_zone_first`
with two approximately 6 x 6 table patches. `players_tavern_zone_second` provides
four such patches and `tavern_barrel_sub_zone` provides two 3 x 2 barrel patches.
The artifact shelf and rat-race table have distinct fixed GDPoint locations;
they do not consume table/barrel patches. Tables replace each other rather than
adding both tiers' quality to the same patch. There is no initial quality bonus.
The kitchen, conveyor and cellar storage contribute no quality.

The `tavern_upgrade` graph spawns the fireplace and fixed barrel and unlocks
`players_tavern_builddesk:p:tavern_barrel_place`. The shelf recipe needs no quest
unlock. `npc_hunchback` unlocks Table II during option 3; `npc_cultist` unlocks the
rat-race table through the already modeled
`EVENT_SNAKE_PERSUADE_TO_STEAL_ANCIENT_AMULET` conversation. These quest unlocks
are checked separately from access to renewable building materials. The four
new material recipes reproduce the native `craft_obj_data` entries; no new
randomized blueprints are invented.

The `insert_tr_*` crafts use `tavern_artifacts_shelves` as their workstation,
consume the corresponding artifact and place that same artifact in the shelf's
17-slot inventory. Their unlocks follow the corresponding time-machine visions.
The calculator therefore requires the shelf, that vision's event and ownership
of that artifact. It counts each distinct artifact once, regardless of extra
copies. Rats have zero item quality and add nothing to the rat-race table score.

Maximum attainable quality is **81**:
four Tables II (40), fireplace plus fixed barrel (8), two crafted barrels (6),
shelf and rat-race table (10), and all displayed artifacts (17).

## Koukol's actual condition

This was verified against both the exported graph and the original serialized
FlowScript, `resources.assets` path ID **150806**, named `on_tavern_table_built`.
The original graph matches the relevant exported flow:

1. Array node 11 (`$id: 23`) is a `SwitchString` with
   `comparisonOutputs: ["tavern_table_1", "tavern_table_2"]`.
2. The ordinary-table branch (`0`) and default branch end immediately.
3. The Table II branch (`1`) reaches the once-only Koukol flag. Its zero branch
   sets the flag and unlocks `@tr_quest_14_after_tavern_improve_1`.
4. `npc_hunchback:90:option:4` claims the existing relation and Ancient Pickaxe
   rewards. No zone-quality comparison occurs on this path.

The script also calls `tavern_quality_achievment_check`, but that separate call
does not gate the Table II branch. The native trigger is thus one completed
Table II, even when the tavern's quality is below 40; a high-quality tavern with
only ordinary tables does not trigger the conversation.

The original APWorld used material access as a shortcut for Table II. This update
expresses that condition through `BUILDABLE_TAVERN_TABLE_2`, with the verified
materials (wooden beams, wooden planks and silk), and retains the preceding
Koukol quest. No quality threshold is substituted for Koukol's original condition.

## Adam's 40-quality condition

The original serialized `npc_potter` FlowScript was checked directly against
`resources.assets`, as well as its export. It updates `players_tavern_quality` from `Flow_GetQualityOfZone` for
`players_tavern` before presenting the dialogue. SmartRes `$id: 145` has
`res_type: GameRes`, `id: players_tavern_quality`, `v: 40`; its value feeds the
`lock` of answer `$id: 148`, connected to option 2 of the main menu. That branch
completes `dlc_stories_tavern_enhance` and starts the ghost sequence. The later
option 3 awards the Clay Shards after that sequence. The original `lng_en`
resource's `task_dlc_stories_tavern_enhance` text also explicitly requires quality
40 and returning to Adam. This rewardless intermediate step is folded into
`EVENT_ADAM_EXPLAIN_GHOSTLY_POTTERY` as `TAVERN_40`.

This is reachable before the later Snake/Koukol unlocks: four ordinary tables
(20), expansion's fixed fireplace/barrel (8), two crafted barrels (6), an artifact
shelf (5) and the already available Statuette on display (1) reach exactly 40.
The regression checks that 39 fails and this 40-point state succeeds without
Table II or the rat-race table.

The calculator is therefore required by this authored quest. Earlier statements
that no current quest required tavern quality were incorrect: they had only
established Koukol's condition and overlooked Adam's earlier quality lock.

## Compatibility and validation

Existing names, numeric IDs, options, shared grants and slot-data fields remain
unchanged. The companion client's two Koukol reward checks still observe the
same native dialogue outcomes. A new seed is required to use the corrected logic.

`test_tavern_rating.py` covers opening and expansion, replacement of tables,
native recipe materials, quest unlocks, artifact insertion, the 81-point maximum,
inclusive thresholds, generic quest-rule dispatch, cache invalidation, and the
disabled-DLC case. The Koukol regression deliberately checks both directions:
Table II below 40 succeeds, while quality above 40 without Table II fails.
The data-integrity test's former 40-point assertion was replaced because the
original FlowScript proves that assertion invalid. No TODO prerequisites were added.
