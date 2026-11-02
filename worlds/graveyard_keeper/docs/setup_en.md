# Graveyard Keeper Setup Guide

## Requirements

- Graveyard Keeper on Windows.
- BepInEx 5.x x64.
- The GraveyardKeepelago client matching the APWorld used to generate your seed.
- Every DLC enabled in the seed.
- Your multiworld server address, slot name and optional room password.

This is an unreleased development integration. Use the matching tested builds supplied
by your multiworld host if release downloads are not yet available.

## Install and connect

1. Extract BepInEx 5.x x64 into the game directory, beside the game executable.
2. Launch the game once, then close it.
3. Put `GraveyardKeepelago.dll` into `BepInEx/plugins/GraveyardKeepelago/`.
   The DLL includes the client libraries and shared game data.
4. Launch the game and select the Archipelago logo on the title screen.
5. Enter `host:port`, your slot name and optional password, then select **Connect**.
6. Start a new game for your first Archipelago session. Normal saves cannot be
   converted into Archipelago saves.

Connect before loading your Archipelago save on later launches. Disconnect before
playing a normal save. If the connection drops, use **Connection** in the pause menu
and select **Reconnect**. Completed checks are retained until the connection returns.

## Research, rewards and goals

Technology research keeps its point costs and prerequisites. Its preview shows the
randomized rewards, which may belong to another player. Receive the corresponding
multiworld item to unlock a randomized recipe or ability in your own game.

The seed selects either the Portal goal or a required graveyard rating. A graveyard
rating of zero completes immediately once the Archipelago save is ready. Completion
is checked again after loading a save or reconnecting.

Keep the client version compatible with your seed and save. Data version 8 changes
research-check IDs from earlier development versions, so those earlier seeds must be
regenerated when moving to this version.

For further installation and troubleshooting details, see the
[client player guide](https://github.com/SonOfTheRocks/GraveyardKeepelago/blob/main/docs/player-guide.md).
