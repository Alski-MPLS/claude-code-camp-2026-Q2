# World Map

## Rooms

```json
{
  "The Bakery": {
    "description": "Small bakery, sweet scent of danish and bread. A baker NPC and a small sign on the counter (reads 'buy'/'list' for shop instructions). Shop stock via `list`: 1) A danish pastry - 7 coins (unlimited), 2) A bread - 14 coins (unlimited), 3) A waybread - 72 coins (unlimited).",
    "exits": {"south": "Main Street (near Armory)"}
  },
  "Main Street (near Armory)": {
    "description": "South to Armory, north to Bakery, east to Market Square.",
    "exits": {"north": "The Bakery", "south": "The Armory", "east": "Market Square", "west": "Main Street (west end)"}
  },
  "Main Street (west end)": {
    "description": "South to Mages' Guild entrance, north to magic shop, west to city gate.",
    "exits": {"south": "The Entrance To The Mages' Guild", "west": "Inside The West Gate Of Midgaard", "east": "Main Street (near Armory)"}
  },
  "The Entrance To The Mages' Guild": {
    "description": "Small, poorly lit entrance hall. Guarded by a sorcerer/Peacekeeper/cityguard — blocks entry (\"The guard humiliates you\").",
    "exits": {"north": "Main Street (west end)"}
  },
  "The Armory": {
    "description": "Armor for sale, armorer NPC, note on the wall.",
    "exits": {"north": "Main Street (near Armory)"}
  },
  "Market Square": {
    "description": "Central square with statue. Roads in all directions.",
    "exits": {"north": "The Temple Square", "south": "The Common Square", "east": "Main Street (general store/pet shop)", "west": "Main Street (near Armory)"}
  },
  "Main Street (general store/pet shop)": {
    "description": "General store to the north (unexplored interior), Pet Shop to the south (unexplored interior), main street continues east.",
    "exits": {"west": "Market Square", "east": "Main Street (weapon shop/Swordsmen)", "north": "(unexplored — General Store)", "south": "(unexplored — Pet Shop)"}
  },
  "Main Street (weapon shop/Swordsmen)": {
    "description": "Weapon shop to the north, Guild of Swordsmen to the south, town exit to the east (unexplored).",
    "exits": {"west": "Main Street (general store/pet shop)", "north": "The Weapon Shop", "south": "The Guild Of Swordsmen (entrance, unconfirmed)", "east": "(unexplored — leaves town)"}
  },
  "The Weapon Shop": {
    "description": "A weaponsmith NPC, a small note on the counter. Shop `list`: 1) A flail - 835, 2) A warhammer - 66, 3) A wooden club - 16, 4) A long sword - 802, 5) A small sword - 80, 6) A dagger - 13.",
    "exits": {"south": "Main Street (weapon shop/Swordsmen)"}
  },
  "The Temple Square": {
    "description": "Marble steps up to temple. Clerics' Guild to west, Grunting Boar Inn to east, fountain.",
    "exits": {"north": "The Temple Of Midgaard", "west": "The Entrance To The Clerics' Guild", "south": "Market Square"}
  },
  "The Entrance To The Clerics' Guild": {
    "description": "Small modest hall. Bar to the north. Guarded by knight templar/cityguard — blocks entry.",
    "exits": {"east": "The Temple Square"}
  },
  "The Temple Of Midgaard": {
    "description": "Main temple hall, ATM. Reading Room to west, donation room to east.",
    "exits": {"south": "The Temple Square", "west": "The Reading Room", "north": "By The Temple Altar"}
  },
  "The Reading Room": {
    "description": "Desks/benches, bulletin board, a teleporter device, a saleswoman with overpriced gadgets — shop `list`: The teleporter, 12 coins (no weapons).",
    "exits": {"east": "The Temple Of Midgaard"}
  },
  "By The Temple Altar": {
    "description": "Altar, statue of Odin. Path north out the back of the temple.",
    "exits": {"south": "The Temple Of Midgaard", "north": "Behind The Temple Altar"}
  },
  "Behind The Temple Altar": {
    "description": "Dirt path toward the Dragonhelm Mountains.",
    "exits": {"south": "By The Temple Altar", "north": "The Great Field Of Midgaard"}
  },
  "The Great Field Of Midgaard": {
    "description": "Open countryside. One junction room has a path splitting off west and a structure to the east (newbie zone entrance).",
    "exits": {"south": "Behind The Temple Altar", "north": "The Great Field Of Midgaard (junction)"}
  },
  "The Great Field Of Midgaard (junction)": {
    "description": "Strange structure to the east (Newbie Zone entrance), dirt path splitting west (toward Chessboard).",
    "exits": {"south": "The Great Field Of Midgaard", "east": "The Entrance To The Newbie Zone", "west": "The Dirt Path"}
  },
  "The Entrance To The Newbie Zone": {
    "description": "Newbie monster here (\"Kill him! Kill him!\") — reads as trivial/safe XP.",
    "exits": {"west": "The Great Field Of Midgaard (junction)", "north": "The Beginning Of The Passage"}
  },
  "The Beginning Of The Passage": {
    "description": "Long corridor, sounds of creatures.",
    "exits": {"south": "The Entrance To The Newbie Zone", "east": "The Dirty Hallway"}
  },
  "The Dirty Hallway": {
    "description": "Slimy/moldy hallway. A creepy crawling thing here. Closed door to the south.",
    "exits": {"west": "The Beginning Of The Passage", "east": "A Nexus", "south": "(door, closed)"}
  },
  "A Nexus": {
    "description": "Intersection; north and east doors closed, south continues, west back to Dirty Hallway.",
    "exits": {"west": "The Dirty Hallway", "south": "More Of The Hallway", "north": "(door, closed)", "east": "(door, closed)"}
  },
  "More Of The Hallway": {
    "description": "A pet dragon loose here, plus the newbie monster. Door to the west closed.",
    "exits": {"north": "A Nexus", "west": "(door, closed)", "south": "Another Corner"}
  },
  "Another Corner": {
    "description": "Untidy corner of the passage. Door to the east.",
    "exits": {"north": "More Of The Hallway", "west": "(unexplored)", "east": "The Alchemist's Room"}
  },
  "The Alchemist's Room": {
    "description": "Bottles/flasks, formulae on the walls. The Newbie Alchemist NPC. Door to the north (unexplored), a stairway down guarded by a warning sign: \"If you are below level 7 and alone, or below level 4 then bugger off! Or else don't blame me if you die...\" — GATED AREA, likely where the minotaur lives. Not yet descended (character level 1, solo).",
    "exits": {"west": "Another Corner", "north": "(unexplored — door)", "down": "(unexplored — gated, level 7 solo / level 4 grouped minimum per sign)"}
  },
  "The Dirt Path": {
    "description": "Leads to a large rusty gate (Great Chessboard entrance).",
    "exits": {"east": "The Great Field Of Midgaard (junction)", "west": "The Great Chessboard Of Midgaard (archway)"}
  },
  "The Great Chessboard Of Midgaard (archway)": {
    "description": "\"This zone is above your recommended level.\" Gate rusted open.",
    "exits": {"east": "The Dirt Path", "west": "A White Square"}
  },
  "The Common Square": {
    "description": "Nasty smell to the south (The Dump). West to Poor Alley, east to Dark Alley.",
    "exits": {"north": "Market Square", "west": "The Eastern End Of Poor Alley", "east": "The Dark Alley", "south": "The Dump"}
  },
  "The Dark Alley": {
    "description": "Two mercenaries waiting for a job. Guild of Thieves entrance to the south, alley continues east.",
    "exits": {"west": "The Common Square", "south": "The Entrance Hall To The Guild Of Thieves", "east": "The Dark Alley At The Levee"}
  },
  "The Entrance Hall To The Guild Of Thieves": {
    "description": "Thieves'/assassins' guild entrance, ATM. Unguarded here, but the thieves' bar to the east is guarded (\"The guard humiliates you\").",
    "exits": {"north": "The Dark Alley", "east": "(guarded — thieves' bar, blocked)"}
  },
  "The Dark Alley At The Levee": {
    "description": "A Peacekeeper stands here. South leads to the Levee.",
    "exits": {"west": "The Dark Alley", "east": "The Eastern End Of The Alley", "south": "The Levee"}
  },
  "The Levee": {
    "description": "River flowing west, low bank (can enter river). A retired captain sells boats here (`list` -> boats, no weapons).",
    "exits": {"north": "The Dark Alley At The Levee"}
  },
  "The Eastern End Of The Alley": {
    "description": "City wall blocks further east. Small warehouse to the south.",
    "exits": {"west": "The Dark Alley At The Levee", "south": "The Deserted Warehouse"}
  },
  "The Deserted Warehouse": {
    "description": "Old ship items. A sailor NPC — shop `list` currently shows \"nothing for sale\".",
    "exits": {"north": "The Eastern End Of The Alley"}
  },
  "The Dump": {
    "description": "City garbage dump. Sewer entrance (pipes) visible, `down` exit unexplored.",
    "exits": {"north": "The Common Square", "down": "(unexplored — sewer system)"}
  },
  "The Eastern End Of Poor Alley": {
    "description": "Grubby Inn to the south, common square to the east, alley continues west.",
    "exits": {"east": "The Common Square", "south": "Grubby Inn", "west": "Poor Alley"}
  },
  "Grubby Inn": {
    "description": "Uncleaned for decades. A beggar, Filthy the bartender — shop `list`: bottle of local speciality 26, bottle of firebreather 66 (drinks only, no weapons).",
    "exits": {"north": "The Eastern End Of Poor Alley"}
  },
  "Poor Alley": {
    "description": "City wall to the west, a beggar here.",
    "exits": {"east": "The Eastern End Of Poor Alley", "west": "Wall Road (south)"}
  },
  "Wall Road (south)": {
    "description": "Along the western city wall.",
    "exits": {"east": "Poor Alley", "north": "Wall Road (north)"}
  },
  "Wall Road (north)": {
    "description": "City gate just to the north.",
    "exits": {"south": "Wall Road (south)", "north": "Inside The West Gate Of Midgaard"}
  },
  "Inside The West Gate Of Midgaard": {
    "description": "Footbridge/towers over the gate. Cityguard here.",
    "exits": {"east": "Main Street (west end)", "south": "Wall Road (north)", "west": "Outside The West Gate Of Midgaard"}
  },
  "Outside The West Gate Of Midgaard": {
    "description": "Forest edge to the west.",
    "exits": {"east": "Inside The West Gate Of Midgaard", "west": "A Road Through The Plains"}
  },
  "A Road Through The Plains": {
    "description": "Road toward the forest of Haon-Dor; occasional adventurers.",
    "exits": {"east": "Outside The West Gate Of Midgaard", "west": "(unexplored, into Haon-Dor)"}
  }
}
```

## Monsters of Note
- "newbie monster" — Entrance To The Newbie Zone / The Beginning Of The Passage /
  More Of The Hallway — described as "looking confused," reads as trivial/safe XP.
- "a creepy little crawling thing" — The Dirty Hallway — small, unassessed.
- "an oozing green gelatinous blob" — seen in The Bakery and Market Square — unassessed.
- "a beastly fido" — scavenging in several street rooms — unassessed, likely trivial
  (fidos are classic tbaMUD junk mobs).
- Chessboard pawns (Black/White Square rooms) — entire zone flagged "above your
  recommended level" — do not engage until much higher level.
- "the minotaur" (target, not yet seen directly) — believed to live down the
  stairway in The Alchemist's Room (past Another Corner, off More Of The
  Hallway). Gated by an explicit in-game warning sign: level 7+ if solo, or
  level 4+ if grouped. DO NOT ENGAGE below those levels — not yet confirmed by
  sight/`consider`, only inferred from the sign.
- "The Newbie Guard" — A Small Room (south off The Dirty Hallway) — unassessed.
- "The Newbie Alchemist" — The Alchemist's Room — unassessed.

## Shops checked, no dagger/weapons found
- The Armory (south of Main Street near Armory) — armor only (helmets, shields, sleeves, breastplates etc.)
- The Magic Shop (north of Main Street west end) — scrolls/potions/wand/staff only
- The Grunting Boar bar (east of Grunting Boar Inn entrance hall, off Temple Square) — drinks only
- Grubby Inn (south of Poor Alley) — drinks only
- The Reading Room saleswoman (west of Temple) — a teleporter gadget only
- The Levee (south of Dark Alley At The Levee) — boats only
- The Deserted Warehouse (south of Eastern End Of The Alley) — currently nothing for sale
- The Post Office (north of Grunting Boar Inn entrance hall) — mail services, no shop

## Guildmasters / Practice
- Player's class confirmed via `score`: **warrior** ("Dummy the Swordpupil").
- Mages' Guild entrance (south off Main Street west end) — guarded, entry blocked. Wrong guild for a warrior.
- Clerics' Guild entrance (west off Temple Square) — guarded, entry blocked. Wrong guild for a warrior.
- Guild of Thieves entrance hall (south off Dark Alley) — entrance hall itself is unguarded, but its bar to the east is guarded. Wrong guild for a warrior regardless.
- **Guild Of Swordsmen found** — south off "Main Street (weapon shop/Swordsmen)",
  which is two rooms east of Market Square (Market Square → east → Main Street
  (general store/pet shop) → east → Main Street (weapon shop/Swordsmen) → south).
  This is the character's actual matching guild — entry not yet attempted/confirmed.
  The Weapon Shop is right next door (north from the same junction) and sells a
  dagger for 13 coins (see Rooms above for full weapon shop stock).
