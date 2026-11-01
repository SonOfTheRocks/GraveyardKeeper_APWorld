# Stable network item IDs

`item_ids.json` is the APWorld-owned mapping from canonical shared item keys to
network IDs. Its 488 definitions have deterministic IDs independently of file
ordering. The 486 original assignments were checked against the existing local
`trap-contract-before.json` snapshot, with no differences. The two specific trap
IDs are 488 (Bats Trap) and 489 (Green Slime Trap). The general random trap was
removed before the first release; 487 is unused and is not reserved. ID zero is
used for events.

Shared JSON definitions still own names, classifications and grants. Their file
and object ordering must never assign network IDs. The APWorld validates exact
mapping coverage, unique positive integer IDs, unique network names, and agreement
with any explicit ID in a shared definition. A new item needs a deliberately
assigned unused ID; do not regenerate this table from file ordering. Once a
release exists, changing published IDs or definitions requires an explicit
compatibility decision. Before the first release, obsolete definitions can be
removed without maintaining compatibility with development-only seeds.

The client obtains network IDs from the server Data Package. This table does not
change shared runtime data or its version. Tests load reordered shared resources
and compare both advertised IDs and created item codes against the public map.

Resource traversal is also sorted so filesystem enumeration cannot change the
item-pool order for an otherwise identical seed. This ordering never assigns IDs.
