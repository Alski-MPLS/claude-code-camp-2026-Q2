# Week 3 Technical Documentation

## Technical Goal
At this point, the technical goal is to continue building out the agent to make it better. It's ultimately to make the agent more independent and to learn from the environment it experiences. As it runs into new new (or existing) scenario's, it will keep track of that and reason through next steps. It shouldn't constantly get into loops or get stuck and require human intervention. 
### Some higher expectations to solve for:
- If thirsty/hungary, it should understand what to do.
- How to gain experience and skills.
- How to gain health.
- How to gain gold.
- How to explore.

## Technical Uncertainty
Still dealing with strange behaviors that I keep trying to fix. I think it could be the model I'm using and will need to test that out. Just not sure yet how to do that. The agent can find the bakery and knows how to eat. I doesn't go back when it gets hungary. It's not able to learn except what it should care about. So, it sees everything in a room but it can't reason what it could use in the future. That could be more tokens to use but I'm not sure.

## Technical Hypothesis
Will continue to push for troubleshooting this program and watch the agent as it finds new environments and items. I will have to become more familiar with the game and how to play it. I know that we spent a week just going over the play style and the details but if this was for a company, I would think that much of that would be documented and could be ingested prior to diving deep into the agent build. It would have been great to have access to this 2 or 3 weeks prior to the launch of the boot camp so we would have just played it and build this knowledge prior to the start. 

## Technical Observations
- I copied the week 2 agent into week 3 and will continue to make changes there.
- Figured out how to get Claude Code to watch the player and give Claude instructions to help troublehshoot. The agent is using a local LLM through Ollama so it's interesting that I'm using two different models now to play and troubleshoot. 
- Had it finally fix the "sessions" tab in the browsers. 
- Claude Code is actively making changes to the program as it observes the play through while I give it additional instructions. 
- Claude found this -- "That's the small model hallucinating a generic name again ("newbie monster" isn't real content) rather than reading the room — correctly rejected since nothing's actually there. This is normal small-model judgment noise, not a bug in the fixes. The two structural issues you flagged (backtracking to town, and blocked combat) are holding up well through this whole run. I'll keep the monitor running passively and only interrupt if something concerning shows up.". I'm using Gemma4:e4b at this time and running on my MACBOOK AIR 5M. From Claude:
    - qwen3:30b (already in your settings.yaml as a commented option) — it's a MoE model (30B total, ~3B active per token), so it stays fast despite the size, and the larger total capacity should meaningfully cut down the "attacks a name it made up" behavior. Roughly 18-20GB at Ollama's default quant, leaving headroom for macOS/Docker/the dashboard.
    - qwen3:8b — smaller step up, safer on RAM/speed if 30b feels sluggish, still much better at tool use than gemma4:e4b.



## Where the program stands now.

### High level architecture diagram
- Everything hangs off the MUD socket session - the same connection gets shared by the raw move/attack tools, navigate_to, explore, and combat_loop so they're not fighting each other for control.
- Room memory is split into a few pieces: RoomParser turns raw text into structured data, RoomMemory hashes and stores it per room, and WorldGraph is the actual map (a directed graph of rooms connected by exits).
- Added a whole exploration layer on top of that - BlockedExits remembers locked doors/dark rooms so it stops retrying them, and there's now dark-room detection so it doesn't wander in blind.
- Combat got its own safety layer too - it won't attack something that isn't actually in the room, and it won't attack something it's going to lose to, unless I force it.
- The dashboard is just a Flask app reading the same memory files everything else writes to - map, overview, live feed, goals, sessions, all pulling from the same source of truth.
- Watched a live play session with Claude Code this week and found two real bugs in that combat/exploration layer, not just bad LLM judgment: RoomParser was filing any mob with a long custom description as an "item" instead of an "npc," which silently made it unattackable - and explore()'s frontier search is global across the whole map, so once the nearby area's fully mapped it'll happily walk you all the way back to town for some leftover unexplored exit there instead of pushing further into a dungeon. Fixed the parser's default and gave explore() an optional max_hops so it can be told to stay local.

### Data Flow
- User (me) gives it a goal -> agent loop decides which tool to call -> tool talks to the MUD -> result gets parsed and saved to memory before it ever goes back to the LLM.
- Most of the "thinking" now happens in code, not the LLM - process_room only sends back what's new, navigate_to/explore just run the pathfinding and walk it themselves.
- Every room it parses updates three things at once - room memory, the world graph, and now a "who's actually alive here" list the combat tools check against - and that npc/item split is exactly what the RoomParser bug above was corrupting.
- If a planned route doesn't match reality (wrong room, blocked move) it stops immediately and fixes the map instead of blindly continuing - that was a big source of the "confused" behavior earlier.
- All of this gets logged to JSONL as it happens, which is what feeds the live tab, waterfall, and sessions viewer in the dashboard - sessions viewer now shows the list and transcript side by side instead of stacked, so clicking a session doesn't mean scrolling past hundreds of rows to see it.
- Also caught a REPL bug where typing "continue" to resume a session was overwriting the actual goal text with the literal word "continue" - fixed so a resume phrase just reactivates the existing goal instead of replacing it.


## Technical Conclusions
[todo]

## Key Takeaways
[todo]