# AI Summary: Finding the Bakery

When the agent ran into some difficulties, I asked claude specifically to summarize this. Here is what it came up with. (AI generated)

## Tools/Scripts Created

- **`/tmp/mud_login.py` → `/tmp/mud_play.py`** — Python `socket`-based MUD client with a regex `read_until()` helper to wait for specific prompts instead of blind `sleep()` timing. This replaced initial `nc`/shell-script attempts and was what got a reliable login working.
- **`/tmp/mud_explore.py`, `/tmp/find_bakery.py` – `find_bakery6.py`** — Iterative exploration scripts that walked the live MUD room-by-room (`look`, `exits`, directional movement) to manually map Midgaard, since there was no prior knowledge of the layout.
- **`grep`/Python one-liners over `week0_explore/preview/data/world/wld/*.json`** — The circlemud-world-parser had already converted the raw `.wld` map files into JSON. Grepping these for `"name": ".*Bakery"` and then pulling the exact room object (id, exits, room_linked) for room 3009 in zone 30 (Midgaard) was the real breakthrough — it gave the exact path (Market Square → west → Main Street 3013 → north → Bakery 3009) instead of continuing to wander.
- **`/tmp/goto_bakery.py` – `goto_bakery3.py`** — Final targeted navigation scripts using the route derived from the parsed world data, ending in a successful `list` at the Bakery.
- **`data/player.md` / `data/world.md`** — Updated per CLAUDE.md instructions to persist the login flow, character state, and the confirmed Bakery location/menu/route for future sessions.

## Key to Finding It Faster

Switching from live trial-and-error walking to **grepping the already-parsed world JSON** (`preview/data/world/wld/`) for "bakery" was the turning point — it turned a blind graph search into a lookup, giving exact room IDs and exits so navigation could go straight there.

## Issues That Slowed Things Down

- **Shell `nc`/`sleep`-based scripting was unreliable** — fixed timing caused missed prompts and race conditions; had to rewrite as Python sockets with pattern-based waiting.
- **Login flow ambiguity** — new-character creation (sex/class prompts) vs. existing-character login (just name/password) have different prompt sequences, and an initial hardcoded fixed step count caused several failed login cycles.
- **Reconnect resumed at last location, not spawn** — broke scripts that assumed a fixed starting point (Temple), requiring re-navigation logic.
- **Symmetric map layout confusion** — Market Square has a "Main Street" room on both the east (General Store/Pet Shop) and west (Bakery/Armory) sides with similar naming, causing a wasted exploration pass down the wrong side before finding the parsed data.
- **Memory files weren't updated as work progressed**, despite CLAUDE.md instructing this — only started persisting state after being prompted, meaning early exploration progress wasn't saved.

## Bakery Result

- **Route:** From Market Square, go `west` (Main Street, room 3013) then `north` (The Bakery, room 3009).
- **Menu:**

  | # | Item | Cost |
  |---|------|------|
  | 1 | A danish pastry | 7 gold |
  | 2 | A bread | 14 gold |
  | 3 | A waybread | 72 gold |
