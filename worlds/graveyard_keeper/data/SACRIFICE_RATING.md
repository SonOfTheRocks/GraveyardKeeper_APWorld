# Sacrifice zone quality

`logic/sacrifice_rating.json` records native furniture, fixed capacities and
activation requirements. `HasSacrificeRating` requires access to
`REGION_SACRIFICE_ZONE`; `CanComplete` applies it to `SACRIFICE_ZONE_20`.

## Native evidence

Original `resources.assets` GameBalance gives these qualities and recipes:

| Object | Places | Quality per place | Materials |
| --- | ---: | ---: | --- |
| `blood_fountain` | 2 | 2, activated 5 | `stone_plate_2` ×5, `polishing_paste` ×5, `repair_stn` ×1 |
| `skeleton_crucified` | 2 | 2 | `skull` ×1, `wood_balk_1` ×2, `pumpkin_crop:2` ×1 |
| `skeleton_crucified_on_wall` | 2 | 1 | Same as standing skeleton |
| `skulls_in_wall` | 2 | 1 | `skull` ×5 |
| `skulls_on_column` | 2 | 1 | `skull` ×5 |

Original `level3` contains two separate ground patches and two positions in each
of the four named WorldSubZones. Each type has its own places; no type competes
with another. The initial site has no quality furniture. The full score is
2 × 5 + 2 × 2 + 2 × 1 + 2 × 1 + 2 × 1 = **20**.

`blood_fountain_activate` consumes ten blood and changes the object to
`blood_fountain_activated`. The activated score replaces the empty score;
there is no extra empty fountain to add and no ongoing fuel requirement.

Original `npc_cultist` custom function `@snake_help` (offer to prepare the site)
ends by unlocking `sacrifice_builddesk:p:blood_fountain`,
`:skeleton_crucified_on_wall` and `:skeleton_crucified` (array nodes 465–467,
serialized refs 1150/1152/1154). Both skull-decoration crafts have
`needs_unlock = false`. Only the three locked types require the collected
`EVENT_SNAKE_OFFER_TO_PREPARE_RITUAL_SITE` event.

The same original graph reads zone `sacrifice` with `Flow_GetQualityOfZone`
(serialized ref 2084) into `sacrifice_quality`. SmartRes ref 1200 sets the
20-point lock on Answer ref 1203 for showing the prepared site. The existing
quest threshold is retained and now enforced.

## AP model

Internal building recipes model material access, with quest unlocks checked by
the calculator. There are no invented randomized furniture blueprints. The
silver pumpkin requirement uses the usual higher-quality substitution rules.
The previously missing `ITEM_STONE_REPAIR_KIT` recipe models native `repair_stn`
and `repair_stn_2`: stonecutter I or II, one `stone_plate_1`, two `detail_1`, one
clay, and the existing `ITEM_LEARN_CREATE_STONE_REPAIR_KIT` recipe item.

As elsewhere, repeatable materials do not carry quantity requirements: access
permits filling both places or activating both fountains. Each crafting-event
and quest-event input is declared for rule-cache invalidation. This is base-game
content for all DLC combinations. No AP item/location IDs, grants, options,
slot-data fields or client code change.
