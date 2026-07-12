---
name: tbamud-explorer
description: Connect to and explore the local tbaMUD (CircleMUD-derived) server running on localhost:4000, mapping out rooms, exits, and points of interest as you go. Use this whenever the user asks to "connect to the MUD," "play tbaMUD," "explore the mud," "log into the mud on port 4000," or otherwise wants an automated telnet session with a MUD/CircleMUD/DikuMUD server on localhost. Also use it if the user asks to send raw commands over telnet to a MUD, wants a map of the game world, or wants to pursue a multi-session goal like reaching a target level or defeating a specific monster.
---

# tbaMUD Explorer

Drives a persistent telnet session against a local tbaMUD server (a CircleMUD/DikuMUD
descendant) to log in and systematically explore the game world, building a map of
rooms and how they connect. Also supports multi-session goals (reach level N, defeat
monster X) by persisting character and world state to disk between sessions — see
**Long-term goals and persistent memory** below.

## Why a persistent session

A MUD is stateful: your character stays in one room, in one game, for the entire
session. Reconnecting for every single command would mean re-logging-in every time and
losing your place in the world. `scripts/mud_client.py` solves this by running a small
background daemon that holds the one telnet connection open; you interact with it
through short-lived subcommands that write to (and read from) that daemon.

```
python3 scripts/mud_client.py start              # connect, auto-login, prints the entry room
python3 scripts/mud_client.py send "<command>"    # send one MUD command, print the reply
python3 scripts/mud_client.py send "look" --wait 3   # give a slow reply more time before printing
python3 scripts/mud_client.py read                # print anything new without sending a command
python3 scripts/mud_client.py status              # is it still connected? show recent output
python3 scripts/mud_client.py stop                # quit the game and kill the daemon
```

Connection details (host `localhost`, port `4000`, account `dummy`/`helloworld`) are
hardcoded as constants at the top of the script — this is a local throwaway test
account, so there's no reason to make credential management fancier than that. If the
user gives you different host/port/creds, edit those constants directly.

Only ever run one `start` per exploration session — it's a singleton per session
directory (`/tmp/tbamud-session` by default). `send`/`read`/`status`/`stop` all fail
loudly if there's no active daemon, so call `start` first.

## Long-term goals and persistent memory

A telnet daemon only lasts one session — but a goal like "reach level 7" or "defeat
the goblin guard" spans many sessions. Two files are the memory that survives when the
daemon dies:

- `<project-root>/data/player.md` (who the character is and what they're working toward)
- `<project-root>/data/world.md` (what the world is known to contain)

`<project-root>` is the directory three levels above this skill — strip the trailing
`.claude/skills/tbamud-explorer` off the "Base directory for this skill" path given at
the top of the invocation. For example if that base directory is
`/repo/02_agent_skills/.claude/skills/tbamud-explorer`, the data files are at
`/repo/02_agent_skills/data/player.md` and `/repo/02_agent_skills/data/world.md`.
Always resolve the path this way, never from the current working directory or a bare
`data/player.md` — sibling projects can have their own unrelated `data/player.md` /
`data/world.md` at their own project root (e.g. a `01_playing_agent/data/` directory
elsewhere in the repo), and reading or writing the wrong one silently mixes up two
different characters' progress. If in doubt, use the full absolute path.

Read them before doing anything else when a goal is in play; write them before the
session ends. The MUD server has no memory of your plans — these files are the only
record, so if you don't update them (in the right location), the next session starts
blind.

**`data/player.md`** — character and goal state:

```markdown
# Player: Aldric

## Current Goal
Reach level 7 and defeat "the goblin guard" (seen in The Dirty Hallway, newbie zone)

## Status (as of last session)
- Level: 3, HP: 22/22, session ended in: The Dirty Hallway
- Practice sessions available: 2
- Known skills: kick (poor), bash (average)

## Progress Log
- Session 1: created character, explored Midgaard city, reached level 2
- Session 2: leveled to 3 practicing kick, located goblin guard but too weak to engage (it hit for ~15/round)

## Next Steps
- Practice kick to "good" before re-engaging the goblin guard
- Grind easier mobs in the newbie zone for XP toward level 4-5 first
```

**`data/world.md`** — room graph and points of interest, in the same room-graph shape
described in Exploration algorithm below, plus a section for things relevant to combat
goals:

```markdown
# World Map

## Rooms
(same room-graph JSON as the Exploration algorithm section — name, description, exits)

## Monsters of Note
- "the goblin guard" — The Dirty Hallway (newbie zone) — hits ~15/round, seen at char level 3
- "newbie monster" — Entrance To The Newbie Zone — trivial, safe XP

## Guildmasters / Practice
- (guild name) — (room) — trains: (skills/spells)
```

Session flow when a goal is active:

1. **On start**, read both files (at `<project-root>/data/`, per above) if they
   exist. Resume from the recorded location and status rather than assuming a fresh
   character — `start` reconnects the existing character, it doesn't reset progress.
2. **Update `<project-root>/data/player.md`'s Status and Progress Log after every
   meaningful change**: a level-up, a practice session spent, a death, or a
   failed/successful fight against the target monster. "I'll write it up at the end"
   is how progress silently disappears when a session gets cut short — update as you
   go, not in a final batch.
3. **Update `<project-root>/data/world.md`** whenever you learn something that
   changes the plan: a monster's approximate damage output, a guildmaster's location,
   a new room. Skip re-recording rooms already present.
4. **Combat toward a goal is in scope** — unlike pure mapping (below), a leveling/kill
   goal requires fighting. See Combat and leveling.
5. Before ending the session (user says stop, or you hit a natural stopping point),
   write both files even if the goal isn't complete yet. A half-finished goal with
   accurate state beats a "finished for now" goal with none.

## Combat and leveling

Only engage this mode when the user's goal actually requires combat (leveling up,
defeating a named monster) — plain mapping still avoids fights (see Exploration
algorithm).

- Check `practice` for current skills/proficiency and practice sessions available;
  spend sessions on combat skills (e.g. `practice kick`) at a guildmaster before
  engaging anything risky.
- Before attacking a target monster, compare its apparent damage (from
  `<project-root>/data/world.md` notes, or a cautious `consider <monster>` / prior
  encounter) against current HP. If it's a clear mismatch, don't engage — log it in
  Next Steps and grind easier mobs instead.
- Watch HP every round during a fight. If HP drops below roughly a third of max and
  the fight isn't clearly won, flee (`flee` command) rather than pushing through —
  death typically costs XP and drops you back at a bind point, which sets the goal back
  further than a retreat does.
- After any fight (won, lost, or fled), record the outcome in
  `<project-root>/data/player.md`'s Progress Log before moving on — this is what
  lets next session's `consider` decision be informed instead of a guess.

## Exploration algorithm

The goal is a map, not a playthrough — don't fight monsters, shop, or chat unless the
user specifically asks for that. Walk the world and record it:

1. **Start** the session. The room you land in (usually "The Temple Of Midgaard") is
   your first node.
2. Parse each room's reply for three things:
   - **Room name** (the line right after the prompt, often in its own color/caps)
   - **Exits** — either from the `[ Exits: n e s w d ]` line under the description, or
     by sending `exits` for the fuller `Obvious exits: / north - <room name>` form,
     which is more reliable because it names the destination room.
   - Anything notable worth recording as a point of interest (shops, NPCs, objects
     mentioned in the room description) — keep this brief, it's flavor for the map,
     not the point of it.
3. Maintain a graph in memory (and periodically write it out — see Output below) keyed
   by room name, e.g.:
   ```json
   {
     "The Temple Of Midgaard": {
       "description": "...",
       "exits": {"north": "By The Temple Altar", "west": "The Reading Room", ...}
     }
   }
   ```
4. Walk it depth-first: from the current room, send the MUD direction word for each
   *unvisited* exit (`north`, `south`, `east`, `west`, `up`, `down`, `northeast`,
   `northwest`, `southeast`, `southwest` — most tbaMUD servers also accept the
   single-letter forms `n s e w u d`). After recording the new room, either keep
   descending into its unvisited exits, or backtrack by sending the opposite direction
   once a branch is exhausted (north⇄south, east⇄west, up⇄down, ne⇄sw, nw⇄se). Track a
   visited set by room name so you don't re-walk explored territory.
5. **Cap the walk.** Don't try to map the whole game in one pass — 20-30 rooms is a
   reasonable default unless the user asks for more or fewer. Stop when you hit the
   cap or run out of unvisited exits, whichever comes first.
6. **Safety check every few moves.** The MUD prompt shows current/max HP, e.g.
   `10H 100M 49V` = 10 hit points. If HP is dropping between reads (a wandering
   monster attacked you) or you see a death/combat message, stop exploring
   immediately — don't send more movement commands into what might be a fight. Report
   the situation to the user rather than guessing at combat commands. (This step is for
   pure mapping only — if a combat/leveling goal is active, see Combat and leveling
   above instead of stopping at every encounter.)
7. **Watch for non-room replies.** `You cannot go that way.` means the listed exit was
   a red herring (locked door, etc.) — note it and move on rather than retrying.
   Ambient messages (other players/mobs arriving, "You are hungry", shop chatter) can
   interleave with room text; they don't need their own map entries.
8. When done, send `quit` then, from the resulting menu, `0` — or just call
   `scripts/mud_client.py stop`, which does exactly that and tears down the daemon.

## Output

Give the user two things when exploration wraps up:
- The **room graph** as JSON (the structure above), saved somewhere sensible in their
  project or workspace.
- A short **human-readable summary**: a bulleted room list or simple ASCII map showing
  how rooms connect, plus anything notable you spotted (shops, NPCs, teleporters).

Don't bother with the JSON graph for a quick one-off ("just look around and tell me
what's near the temple") — match the output effort to what was actually asked.

If a multi-session goal is active, `<project-root>/data/player.md` and
`<project-root>/data/world.md` (kept current per Long-term goals and persistent
memory above) already contain both the map and the progress log — summarize their
current state to the user rather than re-deriving a
separate report from scratch.

## Troubleshooting

- `send`/`read`/`status`/`stop` say no active session → run `start` first, or check
  `status` — the daemon may have died (server restarted, connection dropped). Its
  stderr/stdout are captured in `<session-dir>/daemon.log`.
- Login stalls or fails → the server's prompts changed, or the account's password is
  wrong. Read `<session-dir>/output.log` directly for the raw transcript to see where
  it got stuck; the `do_login` function in the script has the expected prompt sequence
  (name prompt → password → optional "press return" → numbered menu → "1" to enter).
- If you need to inspect raw output without waiting on `send`'s timing, `read --wait N`
  lets you pause and drain the log separately from sending a command — useful right
  after a movement command that might trigger a slow room description or a random
  encounter.
