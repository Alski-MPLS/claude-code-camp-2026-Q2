# Preweek Technical Documentation

## Technical Goal
My Technical goal is to learn as much as I can about Claude Agents and to develop how to use this technology in my personal and work enviroments. I have a goal with leadership to be an AI leader and I've been able to build a couple of web sites within our company that was able to save up to $3.5 million over 3 years. Now, they want to understand how to take this knowledge and pull in others. I have other ideas that will allow the current engineers to avoid manual research tasks and just need help with what works and what doesn't around skills, agents, etc. It's easy to read but seeing these in action will really help. 

## Technical Uncertainty
Now that I've had a chance to review the preweek environment and have had a chance to play with the MUD, i will need to dive into the technical details.
- For the agent, what situations would that work well with.
- For the skill, same as agent. what situations would this work well.
- I'm also uncertain how many tokens will each situation use and will i need to spread this out across the week or purchase additional tokens to finish the pre-week. Some of the tasks could result in loops or inefficient logic.
- I have some experience with MCP and I'm wondering why we are using NC or Telnet. Is this going to be a challenge for the tools we build.
- I have experience with GIT, Claude and have sat the basic class at exampro but I haven't had a chance to use all of these in the real world. I'm uncertain if I will be able to grasp everything during these next 2+ weeks.

## Technical Hyphothesis
I think building this as a Skill, rather than just using reference files, will make the agent more reliable and cheaper to run. A Skill can front-load the right questions and enforce clear rules for reading and updating memory (player.md/world.md), which should cut down on dumb repeat mistakes and reduce how much re-exploring the agent has to do each time. It should also hold up better on weaker models, since the Skill narrows down what the agent needs to figure out on its own. If memory updates still fail, that likely points to unclear instructions on my part, not a flaw in the approach.

## Technical Observations
## 1. Agent file with reference files eg. AGENT.md, @~/docs/*.MD

## Observations

- Starting claude in the explore_architecure and presenting what to accomplish was an easy start.
- It did have issues with login as the character was at a state that was already played.
- At one point, it tried to build a new character which didn't make sense.
- It finally started creating python files in the /tmp directory (saved the details in an ai-summary.md file)
- It was having a hard time with the Haiku model on high effort. 
- It did not save the details in the player.md or world.md files. I had to remind it when I changed models
- It started looking outside of the explore_architecture folder and found the /preview/data/world/wld file and was able to identify the bakery name, location and path.
## Additional Observations with the Agent file
- Token usage on both tests seems to be random. At times, it would use less if the task was completed fast. For larger tasks, it will probably use much more but it will be hard to estimate.
- Any scripts created ad-hoc were saved in the /tmp folder instead of a structured location. 




## 2. Agent Skills drvien by main agent eg. ~/.skills

## Observations
- When I ran the request in claude, it asked me a number of questions before starting. I picked the recommended answers to start and play.
    - It asked if this was to what should it do once connected. I said this will be used to play the game
    - It should use a persistent backgroup connection
    - How should the login creds be stored -- Hard coded in the script
    - How do you want to test it. Just vibe-test it live 
- I forgot that i have Graphify installed so I will have to make sure this is not going to add too much junk to the repo.
- It want's to build the script in the ~/.claude/skills folder. I'll let it run but I'll ask to move it after it's completed. Had Claude move it. 
- I had it look for the bakery and it seemed to find it faster than the playing agent area. Less tokens needed. It did request many times to use python.
- Asked it to practice kick at the guild and changed the model to haiku. This will probably create an error as the character already practiced that skill. I stopped it at 67 attempts at about 10k in tokens. That seemed to be harder for the skill.
- Asked it to add the memory files. It is using the Test-Driven Development skill to help build this. Ran into an issue where the skills.md file was not picking the correct player.md and world.md files for memory. I needed to be clearer.
- I asked it to find where I can purchase a dagger and how much it costs using sonnet 5 and medium effort. It had an issue with how it transcribed the map and couldn't find it without hints.
- I asked it to find the minitaur and defeat it by using subtasks. It created a plan, purchase a dagger, locate the minotaur, assess the minotaur, engage the minotar if assessment allows -- or flee, update the memory with final outcome. It found a warning that if you are not level 7, then not to attempt it. It asked me if it should grind away and gain levels. I stopped the skill at that point to save on tokens. 

## Additional Observations with the Agent Skills
- It created the tbamud-explorer skill which packages all domain knowledge into a single reusable unit. Better than the flat prose in the CLAUDE.MD file. The skill has it's own helper script, defines it's own trigger phases and scopes it's memory paths.
- The skill creates is in a CLAUDE format (from what I understand) but it should work with some simple conversions.
- I would guess that as the world grows and the skill finds new areas, it will have a hard time using an MD file. I know that it had an issue with reviewing the town and it had to be reminded of some basics with the map. Plus, as the file grows, what does that do to the context size. I asked claude to review how it modifies the MD files and it said it has to read the entire file and any changes will have to re-write the entire contents, even for 1 entry. This seems inefficient and would need to change as more areas are discovered.
- This skill becomes very focused on a single task and can't think of what is required to fullfill that task. In an example, the minitaur recommends the player should be at level 7. The skill should have come up with a second plan on what is required without needing input.
- Having a structured queue would help could help with this in the player.md or another area. Maybe have an ID, priority, status (ready/blocked/in-progress) and a blocked field.
- 1 idea for improvement would be to update the queue whenever a level, HP or resource is changed. This could help with dealing on secondary tasks.
- Another idea for improvement would be to separate the player/world into 3 files that covers room topology, entity/NPC data and character state.
- Utilize a persona style in the definition file that can handle different play styles. This could help when a decision is needed and will minimize needing player input.
    - This could also help with building out sub-goals.
    - You could also provide feedback/transparency with the a step-by-step plan for reference and to help with future decisions.
- Utilize updating the plan and subplans during the session.
    - This should help when a new subgoal is required vs needing input from the user.
    - Should evolve as more areas and details are learned, based on the main and sub goals.
    - Theer should be checks after ever decision or observation, a plan validity check.
    - Act -> observe -> Check whether the plan still holds -> Adapt or Continue
- Different exploration styles could help. Right now, there is one exploration algorithm set. You could also create additional styles like
    - Cartographer -- explore as much as possible to build out the full map.
    - Speedrunner -- come up with direct pathing to the goal.
- Update the risk tolerance so it's not hardcoded -- flee below one-third HP. This should be associated to the persona.

## Conclusions
- The agent was easy to setup to setup and get up and running quickly but there were challenges with utilizing an existing character. It couldn't figure out what to do and tried to create a new character.
- The agent built ad-hoc scripts in a temporary folder.
- The agent decided to pull in data outside of what it was supposed to stay within. 
- The skill is strong for descrete/specific tasks that are simple and bounded. If nothing changes mid-session, this should be good "as-is"
- Multi-session goals are limited and does not work with with the current skill.
- Both approaches had issues with memory and sessions had to be stopped, hints had to be given or it got stuck and asked for help. 

## Approach Comparison

| | Plain Agent | Skill |
|---|---|---|
| Bakery found? | Yes (via `/preview/data/world/wld` outside project dir) | Yes (via telnet exploration) |
| Token cost | Higher, variable | Lower, more predictable |
| Memory persisted? | No — required manual prompting | Partially — dropped on model switch |
| Tooling | Ad-hoc Python in `/tmp` | `mud_client.py` at known path |
| Setup complexity | Low — just a CLAUDE.md with instructions | Higher — brainstorming questions before build |
| Cross-boundary access | Yes — read outside project dir | No — explicit absolute path scoping |
| Model sensitivity | Haiku struggled on high effort | Haiku struggled; Sonnet had map transcription issues |



## Technical Conclusions
The hypothesis mostly held up. Reference files were quick to start but broke down fast — lost state, no memory updates without reminders, and real trouble on Haiku at high effort. The Skill approach avoided some of that by asking the right questions early, but it wasn't a clean win — it still needed correction on where memory should live, and some lookups still needed hints. Tokens tell the clearest story: the Skill found things faster and cheaper, but repeated or already-done actions still burned through them either way. Bottom line: a Skill fixes some failure modes, mainly around setup and state, but memory discipline and exploration efficiency still come down to how clearly I spell things out.

## Key Takeaways
- Skills beat reference files for setup — asking the right questions up front avoids a lot of early confusion.
- Neither approach solves memory on its own — player.md/world.md updates still need explicit reminders regardless of architecture.
- Model choice matters more than architecture — Haiku struggled under both approaches, especially at high effort.
- Token cost tracks with repetition, not just approach — already-completed actions (guild kicks) burned tokens no matter which setup was used.
- Specificity is the real lever — most failures traced back to unclear instructions, not a flaw in Skill vs. reference-file design.