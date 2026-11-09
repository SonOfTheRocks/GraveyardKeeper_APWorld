# Church quality logic

`required_area_points: ["CHURCH_20"]` and `CHURCH_50` are enforced by
`CanComplete` through `HasChurchRating`. Tavern, graveyard, trade office,
sacrifice zone and refugee camp quality also have quest-rule support.
Generate a new seed to use these church requirements.

The calculator chooses the highest simultaneously attainable score for each
building patch. It requires the existing progressive blueprint stage and access
to every material, rather than treating receipt of a blueprint as a finished
building. Candles and incense count when obtainable through the existing crafting
or vendor logic. Renewable quantities and waiting for construction are abstracted
in the same way as other AP crafting requirements.

## Evidence

Verified against the installed original game's `Graveyard Keeper_Data/resources.assets`
(`game_data`, path ID 150260), `level3` (church scene), and `level6` (building
prefabs), Unity 2020.3.17f1. The companion checkout contains decompiled
`Assembly-CSharp/WorldGameObject.cs`, `WorldZone.cs`, and `GameSave.cs` under
`GraveyardKeepelago/Dumps/Decompiled`. Its Assembly-CSharp MVID is
`2648EA72-6313-4C23-A802-BED407240412`.

The older JSON dumps omit the serialized private `SmartExpression._expression`
and `GameRes._res_v` fields. In particular, `quality.default_value: 0` is **not**
the actual score of a church furnishing. The values below were read from the
original assets with UnityPy and the managed assembly's serialized type definitions.
No raw dumps or game assets were changed.

| Native object | Score | Footprint |
| --- | ---: | --- |
| `church_altar`, `church_pulpit` | 1 + 2 | Fixed |
| `church_bench`, `church_bench_2` | 1 / 3 | 7 x 2 |
| `candelabrum_1/2/3` | 1 / 2 / 3 | 2 x 3 |
| `wall_candelabrum_1/2/3` | 1 / 2 / 3 | Dedicated T-shaped wall spot |
| `church_budka_1/2` | 5 / 7 | 4 x 4 |
| `church_table_1/2` | 5 / 8 | 4 x 3 or 3 x 4 |
| `c_obj_incense_1/2` | 1 / 3 | 2 x 4 |
| `church_window_1` | 5 | 3 x 2 wall spot |

The scene's `CHURCH/WGOs` contains two original ordinary benches, the altar and
the pulpit: starting quality is 5. The six 7 x 2 bench patches accommodate six
new benches in total, replacing those two. The altar/pulpit footprint remains
occupied and is not available to furnishings.

`church_inside_1/buildzone_1` provides two 2 x 3, two 2 x 4 and two 4 x 4
furnishing patches, in addition to the six bench patches. The large church adds
two 2 x 4 and two 3 x 6 patches plus four wall spots. The cathedral adds one
3 x 2 wall spot, shared by a stained-glass window and a wall candelabrum.
The separate totem/chest area and the occupied cathedral staircase are not
quality-building patches. `logic/church_rating.json` records the alternative
occupancies; competing furniture never receives overlapping space.

The large layout is gated by `EVENT_BISHOP_UPGRADE_TO_BIG_CHURCH`, the cathedral
layout by `EVENT_BISHOP_REPORT_CATHEDRAL_UPGRADE`. These are collected event items,
not recursive `CanComplete` calls: a 20-point check cannot assume that the upgrade
which requires that check has already happened. The legacy 10-point
`church_big_quality_obj` is excluded because `GameSave` unconditionally destroys
that object when loading a save.

Native `candelabrum_*_to_*` crafts replace the empty object with its burning
variant: each of the tier's 1/2/3 candle slots adds 1/2/3 points for
`candle_1`, `candle_3`, `candle_4`, respectively. `church_incense_*` crafts add
one `pseudo_item_qual_2/4` during burning, so incense adds 2/4 points per burner.
Only the best obtainable consumable and furnishing tier is used.

The 15 building recipes reproduce `craft_obj_data`'s `church_builddesk:p:*`
materials and the blueprint ownership stages in the shared client grants.
No network IDs, grants, slot-data fields, options or client code change.

## Validation

`test_church_rating.py` covers initial quality, replacement of existing benches,
space competition, consumables, upgrades, inclusive thresholds, church access,
the two authored quest requirements, each recipe's blueprint/material requirements,
client grant agreement, and cache invalidation after collecting/removing inputs.
The progression suite covers both goals, all DLC combinations, vendor settings,
pool balance, dependency classification and restrictive filling.
