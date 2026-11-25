# Shared APWorld/client data

`shared/` is a Git submodule containing the source data used directly by both
the APWorld and GraveyardKeepelago. It owns item definitions, item grants,
explicit reward locations, reward triggers, and `manifest.json`.

There is no generated aggregate contract. The submodule commit pins the exact
build input. The integer `data_version` in `manifest.json` is copied into slot
data as `graveyard_keeper_data_version`; the client compares that value with its
own bundled manifest and asks the player to update on a mismatch.

Quest requirements, region topology, recipes, vendors, and graph presentation
metadata remain APWorld-private in the surrounding data directory.
