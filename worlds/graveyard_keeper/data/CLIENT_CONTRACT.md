# APWorld/client data contract

The `external/graveyard_keeper_data` submodule contains the generated,
versioned interface between the Graveyard Keeper APWorld and the companion
client. The canonical authoring data remains in this directory:

- item definitions under `items/`;
- `item_grants.json` for the concrete in-game effect of every received item;
- `locations.json` and the technology locations generated from `regions.json`;
- `quest_reward_triggers.json` for client-side location checks.

Do not edit the generated contract by hand. Initialize the submodule and
regenerate its contract from the repository root with:

```powershell
git submodule update --init --recursive
.venv\Scripts\python.exe worlds/graveyard_keeper/tools/build_client_contract.py
.venv\Scripts\python.exe external/graveyard_keeper_data/validate_contract.py
```

Commit the generated change inside the data submodule first. Then update both
consumer repositories to that exact data commit. The client consumes the
contract directly from its own checkout of the same submodule.

Changing `schema_version` requires coordinated loader changes in the client.
Changing an item or location `name` changes the Archipelago network contract
and likewise requires a coordinated compatibility decision.
