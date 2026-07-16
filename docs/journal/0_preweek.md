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
[todo]

## Technical Conclusions
The hypothesis mostly held up. Reference files were quick to start but broke down fast — lost state, no memory updates without reminders, and real trouble on Haiku at high effort. The Skill approach avoided some of that by asking the right questions early, but it wasn't a clean win — it still needed correction on where memory should live, and some lookups still needed hints. Tokens tell the clearest story: the Skill found things faster and cheaper, but repeated or already-done actions still burned through them either way. Bottom line: a Skill fixes some failure modes, mainly around setup and state, but memory discipline and exploration efficiency still come down to how clearly I spell things out.

## Key Takeaways
[todo]