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
- This seems to be the best method to continue to build out and update the agent. I have Qwen3.30b running locally as the main LLM. I have claude code starting the app and watching the performance of the environment and providing me updates. I'm letting it run by giving Claude some instructions and I will occasionally provide input and allow certain tools to be used. I've made more progress this way then the last week. I just have to watch the tokens outside of the program.
    - Claude is just watching the program run and determines whether the code is acting according to my instructions or if it needs to be tweaked. As an example, It noticed that monsters would disappear. I mentioned that they can move and it recommended a fix while the underlying agent was running. 
- Downgraded to a smaller model due to thermal issues on my laptop. This is causing the agent to run slower and miss attacking wandering monsters. I guess I'll have to live with that for now or move to Claude API to test it out in small spurts. The model is using a more efficient attack program when it starts but it's not enough at this point. I had Claude run some comparisons.
    Comparing the two runs:
    - qwen3:30b: individual reasoning steps averaged ~33s/iteration, completed all its iterations cleanly, no timeouts.
    - qwen3:14b: most steps ran 40-55s, but iteration 23 exceeded 120s and killed the whole turn.
    - Going to change the timeout to 300 seconds and retry it. 
- Character made it to level 3. MAC is a bit warm <grin>. Going to add a "score" tab in the dashboard.
- Ran it with Haiku 4.5 using the API as a comparison. It not only found food to eat at the bakery, it then proceeded to kill 2 monsters and gain more gold and experience. It also used $1.70 due to input tokens. I'm asking claude to review and help come up with a fix. What Claude found.
    Why it was happening:
        - Every one of the 25+ tool-calling iterations per turn resent the entire system prompt, all 47 tool schemas, and the full growing conversation history — all at full input-token price
        - Prompt caching: Not enabled was confirmed right there in your Anthropic console screenshot
        - 98% of the $1.70 spent ($1.66) was input tokens (1.66M in vs. only 8K out) — almost pure re-transmission cost, not actual generation

    The fix (src/boukensha/backends/anthropic.py, committed as ab42fb1):
        - System prompt marked cacheable (static for the whole session)
        - Last tool definition marked cacheable (caches the entire 47-tool schema block, also static)
        - Last content block of the newest message marked cacheable each turn, so the growing history gets reused instead of rebilled
- Added some more funds to the API and gave claude more instructions around training, ATM funds, sleeping/resting, etc. By using Haiku and then watching it with Claude Code, the character was able to level up to 4, find a tourch and find where the minatour was located. It knew not to engage and to continue to level up. I also gave it instructions to start looking closer at rooms that had "unique" areas and to start reasoning through some of what is found. Seems to be working well now. Just need to help it along at times.
- Cost is good now also. 
- I needed to specify that a BANK is really an ATM. But, it did find a key and figured out how to use it (or where it can't use it). 



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