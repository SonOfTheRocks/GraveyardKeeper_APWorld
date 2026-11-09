# Trade office quality

`logic/trade_office_rating.json` records native quality inputs. The calculator
models attainable quality, rather than the player's current furniture or stock.
Repeatable materials have no quantity requirement in AP logic.

## Native evidence

- Original `resources.assets` GameBalance: `box_pallet` has quality 1;
  `storage_builddesk` has base quality 0, inventory size 5, and accepts
  `marketing_point`. That item has quality 1 and stack size 99999.
- Original `level3`: one `box_pallet` already exists in the office. The `storage`
  WorldZone has ten pallet positions, including that occupied position. Its
  child collider also includes the build desk.
- `storage_builddesk:p:box_pallet` consumes six `flitch` and one
  `marketing_point`, with no blueprint unlock. `storage_builddesk::give_marketing_point`
  consumes ten `flyer:flyer_bad` and runs `give_marketing_point`.
- Original `give_marketing_point` adds one marketing point to the build desk,
  refreshes `storage`, and checks the fame achievement. It has no exchange limit.
- Decompiled `WorldGameObject.quality` adds inventory quality to object quality.
  `Item.GetInventoryQuality` / `GetItemQuality` count the entire marketing-point
  stack. `WorldZone.GetTotalQuality` sums the objects. Thus **unspent marketing
  points count too**, while sale crates have zero quality.
- Original `npc_merchant` reads `storage` quality into `storage_quality`. The
  marketing-completion answer locks against `storage_quality` 3. Showing the
  trade license sets `storage_available` and opens the office.

## AP model

The office must be reachable and `EVENT_MERCHANT_SHOW_TRADE_LICENSE` collected.
It then starts at quality 1. Access to flyers permits repeatable marketing
exchanges: the desk can hold 5 × 99999 points. Access to the pallet build recipe
also permits all ten pallets; spent marketing points can subsequently be
replenished. The theoretical maximum is 500005, although the only current quest
threshold is 3. In particular, flyers suffice for that quest without flitch:
the existing pallet plus two unspent marketing points already meet the threshold.

The internal pallet recipe uses `ITEM_FLITCH` and `ITEM_FLYER`, expanding the
renewable marketing-point input directly to its source. It needs no new AP item
or blueprint. The progressive morgue-pallet blueprint is unrelated. Collection
and removal of the opening event, flyer crafting event, and pallet crafting
event invalidate cached quality rules. This is base-game content for every DLC
combination; item/location IDs, client grants, and slot data are unchanged.
