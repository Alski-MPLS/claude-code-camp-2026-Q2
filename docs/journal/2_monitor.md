# Week 2 Technical Documentation

## Technical Goal
The goal for this week is to create additional observation services within the program. There is not much to go on (no walk through video's this week) so I'll have to create a plan and come up with the code to see if it works and gets closer to solving the main goal. 

## Technical Uncertainty
I'm finding that even with AI helping out with the building, this is going to be a challenge. Even with some guidance from the main video, how we come up with the ideas are going to be key. AI is not going to be able to understand the nuiances and I'm worried I'm going to waste a ton of time going down alley's that end up being dead ends. I tried to play with a memory feature in week1 and it seemed to help in some aspects but failed in ways I did not anticipate. I'll give it a try and see how far I get. I think the ultimate goal is to document what I'm seeing and keep up on the discord chat for hints and ideas to help out. I hope this isn't going to be used for week 3 (new week) so that if something isn't working exactly, we can still work on additional tasks without being stuck. 

## Technical Hypothesis
I've taking the code from phase 12 in week1 and moved it into the week 2 folder. I've called it agent-exp and will start from there. I'll make sure I use multiple branches to help with this. My hypothesis is that this is going to take many tries (and many tokens) before I get close.

First step is to develop a plan.md file while watching the video from Saturday again. I will make sure that I'm very detailed in the descriptions on what has to happen and then ask AI to split it up into phases so I can test after each area (similar to how week 1 was split up). I hope that this phased approach doesn't take up too much time. The plan.md file is going to be the key.

## Technical Observations
- I built out a fairly detailed plan.md file that I hope has enough to get this moving. I also found a file that talks about the commands in circleMUD and what they do. I asked Claude to use that to help build out this new boukensha program.
- I'm using a a python built flask web site that will show live sessions, built out a map and built out a water fall graph with times. Seems to work OK but needs many tweaks.
- It was missing a ton of information when it would walk into a room. Had to fix that in the code and force it to pull everything. I'm going to make it accessible in the map tab so you can pull details.
- It's still getting confused. Simply asking it to go find the bakery seems to be such a major issue. It found it once with some direction but when i wiped the map memory and started over, it would get stuck again and again. It could be that I'm using a simple local model but this shouldn't be that difficult. I could understand if this was a more complex situation (like deciding to fight or flee or solving a puzzle). 
- It's now saying that it can't find a specific room (the market Square) when it clearly is shown on the map. Asking claude to check the logic with the navigation.py file.
- It was an error in the code and it's updated now. Before I test, I've asked it to add in some kind of graphic to show exactly where the character is located on the map and it will move it as the character moves. 
- The live tab shows the details for each move. No need to refresh the map now
- Found some rooms that had no titles. Even though I told it could happen, it didn't understand and built multiple entries for the same room.
- It also got thrown into the main menu. I think the character died so I need to add that logic to the code. 
- It did die. It didn't show on the live feed but it tried to fight a larger monster and got thrown out of the game. Updated that code.
- It also tried to fight a newbie corpse. Had to fix that also...... It's not really learning at this point..... 
- I spent the day working on the pathing and mapping issue. It got very confused when it went into a dark area. It also got confused with finding the shortest path. The map feature was very helpful, especially when it started creating paths that made no sense. 
- I think there is a problem with fighting monsters now and will have to look at it later. 
- Pathing is working great now. I can find the bakery very quickly. It still gets a bit confused with some of the strange areas. Added a feature where it will show an arrow on where the character came from.
- I had claude review the presentation and make some basic recommendations. It added an overview tab. 
- The web monitoring solution is helping out alot. I could add more features but for now, it's doing the job and helping with flushing out the logic for the agent. I can have claude code review the sessions files and make recommendations where it gets stuck or has a loop.
- I think I have the overall logic to a point where I can start building more features. It can get to the right areas if I'm a bit more specfic at the prompt. It can fight and can obtain items and gold. It knows where the fountain and bakery are and can get there quickly. It knows now how to train. I've found that that I have to play the game myself if it gets stuck and then provide it with the necessary output so it can learn. I was hoping it will figure this out on it's own but that might be week 3. 
    - Example: I had to figure out how to open the doors in the newbie area and take that info and ask Claude to add it to the prompts. 
- It can still get confused if there is not a clear title or different description for the rooms. It still has issues with the chess board area and I had to manually get him out of there. It also had issues with darkness. I finally had to delete the character and recreate it. I added some logic to avoid darkness until we can figure out how to obtain a light source.
- So, I'm going to leave it as is for now. I'll make sure to update the folder name to week2_monitoring and then finish up this md file.

## Where the program stands now.

### High level architecture diagram
- Everything hangs off the MUD socket session - the same connection gets shared by the raw move/attack tools, navigate_to, explore, and combat_loop so they're not fighting each other for control.
- Room memory is split into a few pieces: RoomParser turns raw text into structured data, RoomMemory hashes and stores it per room, and WorldGraph is the actual map (a directed graph of rooms connected by exits).
- Added a whole exploration layer on top of that - BlockedExits remembers locked doors/dark rooms so it stops retrying them, and there's now dark-room detection so it doesn't wander in blind.
- Combat got its own safety layer too - it won't attack something that isn't actually in the room, and it won't attack something it's going to lose to, unless I force it.
- The dashboard is just a Flask app reading the same memory files everything else writes to - map, overview, live feed, goals, sessions, all pulling from the same source of truth.

### Data Flow
- User (me) gives it a goal -> agent loop decides which tool to call -> tool talks to the MUD -> result gets parsed and saved to memory before it ever goes back to the LLM.
- Most of the "thinking" now happens in code, not the LLM - process_room only sends back what's new, navigate_to/explore just run the pathfinding and walk it themselves.
- Every room it parses updates three things at once - room memory, the world graph, and now a "who's actually alive here" list the combat tools check against.
- If a planned route doesn't match reality (wrong room, blocked move) it stops immediately and fixes the map instead of blindly continuing - that was a big source of the "confused" behavior earlier.
- All of this gets logged to JSONL as it happens, which is what feeds the live tab, waterfall, and sessions viewer in the dashboard.

### Some ToDo's
- Still get a few duplicate rooms in the map from before the parsing fix - would be nice to write a one-time cleanup pass instead of leaving them.
- The "is this monster too dangerous" check is just a list of phrases I've seen so far - probably going to break on a different area of the game with different wording.
- Haven't solved the light source problem yet - it just avoids dark rooms entirely right now instead of actually getting a torch and going in.
- Want to get it self-diagnosing more of this instead of me reading session logs and telling Claude what broke.
- The chess board area is still a mess - some kind of non-standard room layout that confuses the pathing. Need to look at that specifically.
- Need to figure out how to interact with other NPC's to gather clues and start working on quests.ß

### Graphify findings
Had Claude trace through the knowledge graph it built of agent-exp (via `/graphify`) and it found a node-identity bug in graphify itself, not in my code - worth fixing at some point since it's actively skewing the graph's "God Nodes" ranking. (The findings are below to be fixed, maybe in week 3.)

- **Root cause**: graphify's AST extractor can't always resolve a bare type reference (`Context`, `Registry`, `Logger`) back to the module that actually defines it. When it fails, it falls back inconsistently - sometimes minting a new per-file id, sometimes reusing a bare unscoped one.
- **Over-fragmentation example**: `Registry` exists as 8 separate nodes in the graph - one real one (`src_boukensha_registry_registry`, degree 20) plus 7 near-empty degree-1 aliases, one per file that references it (`repl.py`, `knowledge.py`, and 5 test files). Same thing happened to `Logger` (3 nodes instead of 1). This hides how central these classes actually are.
- **Over-merging example (worse)**: `Context` has one canonical node in `context.py`, but also a second bare node - literal id `"context"`, empty `source_file` - that pulled in 37 edges from 11 unrelated files (`__init__.py`, `repl.py`, and 8 different test files) that all just happen to reference the `Context` type. This one fabricates false "these two files are connected" relationships between files that don't actually share anything.
- **Also caused 2 false self-loops** flagged by the health check: `bin/boukensha` importing the `boukensha` package (two different things sharing a name, collapsed onto one id) and `src/boukensha/__init__.py`'s `from . import backends, tasks, tools` (a normal relative import, not a real self-reference).
- **Checked whether this actually mattered**: the "Surprising Connections" section of the report came back clean - none of the 5 surprises it surfaced route through the fragmented/merged nodes. So this is a real data-quality bug, but so far it's only skewing the God Nodes ranking specifically, not the parts of the report I'd actually trust for insight.
- **To fix later**: either re-run `/graphify` with `--mode deep` (better inference budget) or patch graphify's own id-resolution so an unresolved type reference always gets a file-qualified fallback id instead of sometimes falling back to the bare name.



## Technical Conclusions
Adding the monitoring features was pretty easy with Claude. I kept moving between adding new features in the web page vs trying to update the logic of the agent so it wouldn't get stuck, lost or oveall confused. Everytime I would make a change it would break something else (pathing would break because it would become to literal). This is going to be a challenge going forward. 

## Key Takeaways
Monitoring add on was easy to build once I could come up with the requirements. It's in python so it's easy to add additional features (though I'm sure it's just as easy with RUBY). To figure out the logic is going to take hours to go through each potential scenario. I'm hoping we can build some kind of additonal loop that will utilize an LLM to figure this out instead and update the code without my help. This might require a complete redesign. This is getting hard.