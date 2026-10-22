# APWorld/client data contract

`client_contract.json` is a generated, versioned interface between the
Graveyard Keeper APWorld and the companion client. The canonical source data
remains in this directory:

- item definitions under `items/`;
- `item_grants.json` for the concrete in-game effect of every received item;
- `locations.json` and the technology locations generated from `regions.json`;
- `quest_reward_triggers.json` for client-side location checks.

Do not edit `client_contract.json` or the client copy by hand. Regenerate both
copies from the repository root with:

```powershell
.venv\Scripts\python.exe worlds/graveyard_keeper/tools/build_client_contract.py `
  --client-output C:/Users/Kai/RiderProjects/GraveyardKeepelago/GraveyardKeepelago/Data/graveyard_keeper_contract.json
```

Changing `schema_version` requires coordinated loader changes in the client.
Changing an item or location `name` changes the Archipelago network contract
and likewise requires a coordinated compatibility decision.
