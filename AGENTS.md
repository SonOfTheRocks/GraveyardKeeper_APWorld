# Graveyard Keeper APWorld — Agent Guide

## Scope and repository role

This is an Archipelago core fork used to develop the **Graveyard Keeper APWorld**. Product code lives in `worlds/graveyard_keeper/`. Treat other worlds and Archipelago core as upstream code and reference material unless a task explicitly requires a core change.

The APWorld owns seed-generation behavior: stable item/location definitions, regions, reachability and placement logic, options, goals, DLC filtering, slot data, WebHost metadata, and player documentation.

The companion client lives in `C:\Users\Kai\RiderProjects\GraveyardKeepelago`. Names, IDs, slot data, goals, and other client-facing behavior form a shared contract and must be checked against that repository.

## Media policy

Do not create or add AI-generated icons, images, textures, audio, video, or other media to this project, including procedurally generated visual assets. AI-generated code, documentation, and data files are allowed. Reuse existing game assets or human-authored assets with known provenance. UI code may arrange and tint existing native widgets/assets; do not generate new artwork.

## Source-of-truth order

When sources conflict, use this order:

1. The user's explicit requirements.
2. This repository's `/docs`, especially `world api.md`, `options api.md`, `network protocol.md`, `tests.md`, and `apworld specification.md`.
3. Current Archipelago APIs and tests in this checkout.
4. `worlds/apquest` as the preferred small, understandable APWorld example.
5. `worlds/stardew_valley` as a mature example for data modeling, organization, and comprehensive testing.
6. Other worlds only when they demonstrate the exact required mechanism.

Use Stardew Valley selectively. Graveyard Keeper does not need Stardew's full abstraction level or feature scope merely because Stardew contains a comparable mechanism.

## Working principles

- Focus implementation on `worlds/graveyard_keeper` and preserve unrelated user changes.
- Prefer data-driven definitions under `worlds/graveyard_keeper/data` over duplicated hard-coded mappings.
- Do not guess game behavior, internal IDs, quest requirements, or the client contract. Inspect dumps, tests, the companion client, or ask the user.
- Keep changes narrowly scoped and avoid opportunistic Archipelago core refactors.
- Do not add Stardew-sized infrastructure unless current requirements justify it.

## APWorld ↔ client contract

Treat this boundary as a versioned public API. It includes:

- game name;
- item/location names and numeric IDs;
- classifications and progressive-item semantics;
- slot-data keys, types, enum values, and defaults;
- goals and completion reporting;
- DLC identifiers and filtering;
- Data Package expectations and compatibility/version fields.

Until a shared manifest exists, every contract change must be checked manually in both repositories and tested where practical. Never silently rename or renumber an existing item or location. If compatibility must break, say so explicitly and update both sides together.

This project has not had a release or external users yet. User-approved pre-release cleanup may remove obsolete definitions and compatibility code without reserving their IDs. After release, protect published contracts or explicitly plan migration/version breaks; do not add compatibility paths for development-only states by default.

IDs must be deterministic and stable across file ordering, refactors, and releases. IDs advertised by `item_name_to_id` and `location_name_to_id` must exactly match the generated Item and Location objects.

`fill_slot_data()` must serialize every setting the client needs at runtime. Adding an option is incomplete until client behavior, serialization, defaults, and compatibility are addressed.

## Data and logic invariants

For every relevant change, preserve or test that:

- every referenced region, location, event, item, recipe, workstation, vendor, and unlock exists;
- every non-event location belongs to exactly one enabled region;
- connections remain valid for every DLC combination;
- disabled DLC content does not leak into regions, locations, events, pools, rules, or slot data;
- the item pool matches the number of fillable locations;
- required progression items are classified correctly;
- progressive counts and stages match client behavior;
- every supported option combination has a reachable completion condition;
- no rule depends on option-excluded content;
- generation is deterministic for the same seed and options.

Do not weaken logic merely to make generation pass. If accurate behavior cannot be established from evidence, ask the user and record the gap in a test or TODO.

## Testing is mandatory

Strong test coverage is a core project requirement.

- Add or update tests with every behavior change and bug fix; prefer a regression test that fails before the fix.
- Test observable behavior, data invariants, and option combinations rather than private implementation details.
- Logic changes need positive and negative reachability cases.
- DLC-sensitive changes need the relevant enabled/disabled combinations.
- ID/name changes need stability, uniqueness, and client-contract tests.
- Goals need logical-completion and serialized-slot-data tests.
- Keep fixtures small and use helpers under `worlds/graveyard_keeper/test`.
- Never delete or relax a failing test without explaining why the old assertion is invalid.

Before running Python scripts or tests, follow repository setup and run `python ModuleUpdate.py` from the root. This can change installed dependencies; when that mutation is inappropriate, ask the user before proceeding rather than claiming tests were run.

After setup, the focused suite is:

```bash
python -m pytest worlds/graveyard_keeper/test
```

Run the narrowest relevant tests while iterating. At completion, report exact commands/results and any pre-existing failures.

## Development and packaging

- Use Python 3.11.9 or newer, below 3.14, and not the Windows Store build.
- Use relative imports inside the APWorld and absolute imports for Archipelago core modules.
- Ensure Python subdirectories contain `__init__.py` where frozen packaging requires it.
- Build through the `Build APWorlds` launcher component; do not handcraft `.apworld` archives.
- Keep `archipelago.json`, WebWorld metadata, setup docs, options, and implementation synchronized.

Local multiworld command:

```bash
python MultiServer.py <archive_filename> --log_network
```

For WebHost work, follow `/docs` and copy `docs/webhost configuration sample.yaml` to root `config.yaml`.

## Completion checklist

- Generation implements the requested behavior.
- Names, IDs, slot data, goals, and DLC behavior agree with GraveyardKeepelago.
- Relevant option/DLC combinations generate successfully.
- Positive, negative, regression, and data-integrity tests pass.
- No unrelated upstream code changed.
- Player documentation remains accurate.
- Uncertainty is stated and clarified rather than guessed.

## Build and deployment context

Prefer the GitHub Actions `Build` workflow for a complete binary distribution. If explicitly required locally, use `python setup.py build_exe`; AppImage additionally uses `python setup.py bdist_appimage` and `appimagetool`.

Docker deployment contains `multiworld`, `web`, and `nginx`. Preserve the documented host networking and mounted configurations. Deployment changes are outside normal APWorld work unless explicitly requested.
