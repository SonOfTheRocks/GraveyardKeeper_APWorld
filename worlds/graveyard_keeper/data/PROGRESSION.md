# Recipe progression

Recipe ownership items (`ITEM_LEARN_*` and `ITEM_BP_*`) use `FILLER` or
`USEFUL` in the shared item definitions. `USEFUL` is the hand-maintained choice
for recipes with a quality-of-life benefit. Do not put `PROGRESSION` on these
definitions: it is calculated separately for every generated player world.

Active addressed checks, entrance rules and the selected completion rule are
the roots of the analysis. Their Rule Builder dependencies are followed through
quest, crafting and purchase events until no new dependency is found. All
alternatives retained by the active rules are included. Acquisition alternatives
excluded by DLC or vendor options, including cycles without a source, resolve
to false before the closure is built. This structural check never grants access:
the normal quest, quality, money and region rules still apply. Rating calculators
declare their optional inputs independently, so excluding one input does not
erase the remaining dependencies. Crafting events are
created on demand; unused internal quest events are removed as well.

An item needed by this closure is progression. Other recipe ownership items
retain their shared fallback classification. This includes progressive items:
if any stage is referenced, every generated copy of that progressive item is
progression. The pool contains exactly one copy per declared progressive stage.
Pool balancing may remove filler, including optional filler recipes, but never
useful or progression items.

The rules and progression plan are prepared at the end of `create_regions`,
before Archipelago calls `create_items`. Start-inventory items created earlier
receive provisional progression flags, then their flags and collected state are
reconciled with the plan. Shared definitions are never mutated during generation.

Use Rule Builder rules for new logic. Opaque Python callables are rejected by
the progression analysis because their item dependencies cannot be inspected.
The graveyard completion rule exposes the point calculators' inputs explicitly;
update their dependency declarations whenever their state inputs change.

Names, network IDs, grants and progressive stage order are unchanged. The client
uses each received/scouted item's server flags for its presentation; static
classification metadata is only the fallback, not a prediction of seed flags.
Generate a new seed to use the new classifications and pool construction.

## Validation

Run from the APWorld repository root with its existing virtual environment:

```powershell
.venv\Scripts\python.exe ModuleUpdate.py --yes
.venv\Scripts\python.exe -m pytest worlds/graveyard_keeper/test -q --tb=short -p no:cacheprovider
.venv\Scripts\python.exe worlds/graveyard_keeper/data/shared/validate_data.py
```

Verified: setup succeeded; 7,759 tests and 5,989 subtests passed. No pre-existing
test failures were present (the initial baseline passed 7,687 tests). The two
remaining warnings concern the optional LocationStore speedups and deprecated
`pkg_resources`. Shared validation passed with 486 items and 286 authored locations.

The suite includes all 48 combinations of goal, vendor logic and DLC toggles,
both start-inventory modes, cycle/alternative handling, per-player isolation,
stable location IDs, cache invalidation, and restrictive filling for both goals
and a two-player multiworld. Goal combinations use the default rating of 500;
zero-rating completion is covered separately. This is not a validation of every
value of the pre-existing graveyard-rating option.

From `worlds/graveyard_keeper/data/shared`, using the same Python executable:

```powershell
python -m unittest discover -s tests -t .
```

Verified: all 12 shared-data tests passed.

From the companion client repository, with `DOTNET_CLI_HOME` set to a writable
local directory, run the focused tests with:

```powershell
dotnet test GraveyardKeepelago.Tests/GraveyardKeepelago.Tests.csproj --no-restore --filter 'FullyQualifiedName~ClientContractTests|FullyQualifiedName~ApItemColorTests' -p:PluginsPath="$PWD/out/codex-progression-validation/" --verbosity quiet
```

Verified: all 32 client tests passed. `PluginsPath` redirects the project's
automatic post-build copy into its ignored output directory. Both shared-data
copies agree on all item definitions and every file changed by this task.
