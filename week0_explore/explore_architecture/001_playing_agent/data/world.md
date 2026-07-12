# World Map (Midgaard) — Explored So Far

## The Bakery (FOUND)
- **Location:** North of "Main Street" (room 3013), which is directly west of Market Square (room 3014).
  Route from Market Square: `west` (to Main Street, room 3013) -> `north` (into The Bakery, room 3009).
- **Room desc:** "You are standing inside the small bakery. A sweet scent of danish and fine bread fills the room. The bread and Danish are arranged in fine order on the shelves, and seem to be of the finest quality. A small sign is on the counter."
- **NPC:** The baker (wiping flour from his face).
- **Exits:** s (back to Main Street/Market Square area)
- **Menu (`list` command):**
  | # | Availability | Item | Cost |
  |---|---|---|---|
  | 1 | Unlimited | A danish pastry | 7 |
  | 2 | Unlimited | A bread | 14 |
  | 3 | Unlimited | A waybread | 72 |
- Use `buy <item>` to purchase.
- Note: There are TWO "Main Street" rooms flanking Market Square — the bakery is on the WEST one (room 3013, also has the Armory to the south). The EAST one (room 3015) has the General Store (north) and Pet Shop (south) — do not confuse the two.
- This was cross-referenced against parsed world data at `week0_explore/preview/data/world/wld/30.json` (room id 3009) to confirm the route before walking it in-game.

## Goal in progress
~~Looking for **the bakery** to list its menu.~~ DONE — see above.

## Rooms Explored

### The Temple Of Midgaard (spawn point)
- Exits: n (By The Temple Altar), e (The Midgaard Donation Room), s (The Temple Square), w (The Reading Room), d (The Temple Square)
- Has an ATM (automatic teller machine) here.

### The Temple Square
- Exits: n (Temple of Midgaard), e (Entrance Hall of the Grunting Boar Inn), s (Market Square), w (Entrance to the Clerics' Guild)
- Fountain here.

### The Entrance Hall Of The Grunting Boar Inn
- Exits: n (Post Office), e (The Grunting Boar - bar), w (Temple Square), u (The Reception)
- Peacekeeper NPC here.

### The Post Office
- Exits: s (back to Inn entrance hall)
- Head postmaster NPC here.

### The Grunting Boar (bar)
- Exits: w (Inn entrance hall)
- Drunk NPC, bartender NPC.

### The Reception (up from Inn entrance hall)
- Exits: n, d (down, back to entrance hall)
- Receptionist NPC. This is where you `rent` to persist your character location.
- Has an ATM here too. Oozing green gelatinous blobs (monsters) present.

### Market Square
- Exits: n (Temple Square), e (Main Street), s (Common Square), w (Main Street)
- Large statue in the middle.

### The Common Square
- Exits: n (Market Square), e (Dark Alley), s (too dark to tell), w (Eastern End of Poor Alley)
- Beastly fido (monster) mucking through garbage.

### The Dark Alley
- Leads to Pet Shop (n)

### The Pet Shop
- Exits: n only
- Pet Shop Boy NPC. Small crowded store full of cages/animals.

### Main Street (west segment, near Market Square)
- Exits: n (General Store), e (continues Main Street), s (Pet Shop), w (Market Square)

### The General Store
- Exits: s only (back to Main Street)
- Grocer NPC. Items on shelves behind counter (not yet `list`ed).

### Main Street (east segment)
- Exits: n (Weapon Shop), e (leaves town / East Gate), s (Guild of Swordsmen), w (Market Square)
- Beastly fido here too.

### Inside The East Gate Of Midgaard
- Exits: e (leave town), s (Water Shop), w (Main Street)
- Cityguard NPC.

## Not yet explored
- By The Temple Altar (n of Temple)
- Midgaard Donation Room (e of Temple)
- The Reading Room (w of Temple)
- Clerics' Guild (w of Temple Square)
- Eastern End of Poor Alley (w of Common Square)
- South of Common Square ("too dark to tell")
- Weapon Shop (n of east Main Street)
- Guild of Swordsmen (s of east Main Street)
- Water Shop (s of East Gate)
- East of East Gate (outside town)

## Shop-like locations found so far (none confirmed as "bakery")
- The General Store (groceries, not confirmed as bakery — should `list` here)
- The Pet Shop
- Weapon Shop (unexplored)
- Water Shop (unexplored)

## Next steps
- `list` items at General Store to rule it out / confirm as bakery-adjacent.
- Explore remaining unvisited rooms above, especially Poor Alley and south of Common Square, and areas south/west of the Clerics' Guild — bakery likely in a shop row not yet visited.
- Consider `help shops` or in-game `where` on shopkeeper NPCs if available.
