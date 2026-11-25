# Refugee camp happiness and quality

`logic/refugee_camp_rating.json` defines the thirteen quality-increasing builds.
`HasRefugeeCampRating` enforces all existing `REFUGEE_CAMP_2` through
`REFUGEE_CAMP_13` quest requirements. Game of Crone must be enabled, the camp
reachable, and `EVENT_CHURCH_OPEN` collected (the mandatory camp introduction
is folded into that milestone).

## Happiness is a renewable budget with a building-dependent ceiling

Native `DLCRefugees.RefugeesCampEngine.WorldZoneComputed` stores the quality of
zone `refugees_camp`. `UpdateCampProgressObjectSlots` uses it as the happiness
ceiling. `UpdateHappiness` clamps `cur_refugee_happiness` to that ceiling, and
`UpdateCampProgressObjectHappinessItems` mirrors the integer amount to the
`refugee_happiness_item` resources consumed by building crafts. The AP rule
models **attainable happiness**, not the current stock or waiting time.

The original `refugee_camp_get_food` script calls feeding at intervals of 0.2
days. `CalculateOverallHappinessDelta` uses
`(3 * (energy_satiety + water_satiety) - 2 * time_in_days) / 100 * residents`.
Full water supply alone therefore gives positive growth even with no food.
Water is freely renewable from the existing Workyard well, bucket and inventory
recipe, with no randomized unlock or material cost. There is no mandatory food
recipe or camp well upgrade prerequisite for waiting and refilling happiness.
Normal play may of course provide both water and food for faster growth.

The calculator starts with the three original tents, quality 3 and four
residents. In each pass it adds only buildings whose costs fit the **existing**
ceiling and whose materials, quest unlocks, preceding builds and required
residents are available. It repeats until no more buildings are affordable.
Happiness can refill between actions, so costs are not summed. The new slot
from a building cannot finance that building's own cost. Recruitment costs two
renewable happiness; additional tent capacities are 2, 2, 2 and 1 residents,
allowing a maximum of eleven. Recruitment changes population, not quality.

## Native quality and costs

Original `resources.assets` GameBalance (`objs_data`, `craft_obj_data`) gives:

| Build | Happiness cost | Quality change |
| --- | ---: | ---: |
| Water well | 3 | +1 |
| Tent 4 / 5 / 6 / 7 | 2 / 5 / 8 / 10 | +1 each |
| Garden fence | 2 | +1 |
| Cooking table | 6 | +1 |
| Cooking table II | 8 | +1 (quality 2 replaces 1) |
| Campfire II | 8 | +1 |
| Farm fence | 12 | +1 |
| Defensive stakes | 11 | +1 |
| Sword rack | 12 | +1 |
| Observation tower | 13 | +1 |

The maximum is 3 + 13 = **16**, matching native
`MAX_REFUGEE_CAMP_QUALITY` and the paradise achievement check. Well II retains
quality 1 and adds no slot. Depot upgrades, workplaces, gardens and beehives
have zero quality and are not counted. Construction placeholders temporarily
have quality -1; completed buildings replace them, with no further material
cost. They are not permanent penalties or extra buildings.

The AP building recipes reproduce native material access and omit the happiness
resource, which the calculator handles separately. No randomized blueprint is
invented. Campfire II uses ordinary stone (`stone_plate_1`), not polished stone;
the corresponding existing Teodoro quest requirement has been corrected.

## Unlocks and residents

Verified against original `npc_teodoro`, `npc_refugee_cook`,
`npc_refugee_tanner`, the `refugee_unlock_*` scripts and `RefugeeCampData`:

- The initial Teodoro conversation unlocks the well and tent 4. Reporting them
  unlocks tent 5 and the garden fence.
- The fifth resident is the Cook. Her introductory conversation directly runs
  `refugee_unlock_cooking_table` (`npc_refugee_cook`, serialized ref 256).
  Garden-fence completion can run the same script independently. The garden is
  therefore not a kitchen prerequisite. Reporting the kitchen unlocks its
  upgrade. Without a garden, the early camp can still reach seven slots and
  claim the first kitchen reward; the garden's extra slot is needed to progress
  to the eight-cost upgrades. The old mandatory garden/wood-billet requirement
  on the first kitchen reward has been removed and regression-tested.
- Alarich's revival and the seven-resident milestone jointly enable the Beatrice
  sequence and Teodoro's next conversation, unlocking tent 6 and campfire II.
- Reporting the depot/campfire/tent-6 milestone unlocks tent 7.
- The Tanner is resident eleven. Her workplace report unlocks the farm fence.
- The Pagan-amulet investigation and eleven-resident milestone enable the guards
  sequence and stakes task; subsequent stakes and sword-rack reports unlock the
  sword rack and tower respectively. The randomized Pagan amulet remains an
  explicit story input, separate from the stakes' actual building materials.

Quest corrections preserve independent side branches:

- The Coffin Maker is resident nine. Her two initial supply checks now require
  the two milestones unlocking tent 6, plus the existing tent materials and
  eight-happiness budget. They do **not** require reporting the parallel
  depot/campfire/tent-6 milestone, nor completing one supply request first.
- The Tanner's first check now requires the milestone unlocking tent 7, plus
  the existing materials and twelve-happiness budget. Reporting eleven residents
  to Teodoro is not a prerequisite.

Collected milestone items are inputs to the calculator; it does not recursively
resolve quest completion while calculating quality. All observed crafting,
story-item and milestone inputs are declared for cache invalidation. With Game
of Crone disabled, the resolved rule is false and carries no camp dependencies.
No AP item/location names or IDs, shared grants, slot data, options or client
code change. Generate a new seed to use the new logic.
