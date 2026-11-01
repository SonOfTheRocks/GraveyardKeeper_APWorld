# Stable network item IDs

`item_ids.json` is the APWorld-owned mapping from canonical shared item keys to
network IDs. It freezes all 489 IDs advertised by the development checkout at
APWorld commit `bb5c69315037ee79d1170ecdd781b94f0f725c32`; no existing IDs changed.
The 486 legacy assignments were also checked against the existing local
`trap-contract-before.json` snapshot, with no differences. The three trap IDs
remain 487 (retired random Monsters Trap), 488 (Bats Trap), and 489 (Green Slime
Trap). ID zero remains reserved for events.

Shared JSON definitions still own names, classifications and grants. Their file
and object ordering must never assign network IDs. The APWorld validates exact
mapping coverage, unique positive integer IDs, unique network names, and agreement
with any explicit ID in a shared definition. A new item needs a deliberately
assigned unused ID; do not regenerate this table from file ordering or reuse a
retired ID. Removing or renaming an existing public definition needs an explicit
compatibility decision.

The client obtains network IDs from the server Data Package. This table does not
change shared runtime data or its version. Tests load reordered shared resources
and compare both advertised IDs and created item codes against the public map.

Resource traversal is also sorted so filesystem enumeration cannot change the
item-pool order for an otherwise identical seed. This ordering never assigns IDs.
