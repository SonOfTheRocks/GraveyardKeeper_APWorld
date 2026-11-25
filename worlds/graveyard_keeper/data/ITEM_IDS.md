# Stable network item IDs

`item_ids.json` is the APWorld-owned mapping from canonical shared item keys to
network IDs. Its 488 definitions have deterministic IDs independently of file
ordering. The 486 original assignments were checked against the existing local
`trap-contract-before.json` snapshot, with no differences. The two specific trap
IDs are 488 (Bats Trap) and 489 (Green Slime Trap). The general random trap was
removed before the first release, leaving 487 available. Internal events use
`code=None` and `address=None`.

Shared JSON definitions still own names, classifications and grants. Their file
and object ordering must never assign network IDs. The APWorld validates exact
mapping coverage, unique positive integer IDs, and unique network names. Assign
new items unused IDs explicitly. Once a
release exists, changing published IDs or definitions requires an explicit
compatibility decision. Before the first release, obsolete definitions can be
removed without maintaining compatibility with development-only seeds.

The client obtains network IDs from the server Data Package. Changing an ID in
this table changes the Data Package for newly generated seeds. The shared data
version is set separately in the shared manifest. Tests load reordered shared
resources and compare advertised IDs and created item codes with the public map.

Resource traversal is also sorted so filesystem enumeration cannot change the
item-pool order for an otherwise identical seed. This ordering never assigns IDs.
