# Week 1 Technical Documentation

## Technical Goal
I think the technical goal is to understand the different stages of how this agent was built. Each stage builds off the previous one and helps with understanding the logical data flows. During the Week 1 Saturday video, we were shown the final application that I believe is what we're trying to build and understand. These are my first thoughts as I work through the videos and try to understand the deeper goals for this week. I'll probably add more to this section once I finish the videos.

## Technical Uncertainty
I am not a developer. I don't know how Ruby works and have a limited understanding of Python. So I'm not sure if what's being built is best practice for the overall goal of the course, or if we'll run into issues down the road. I plan on continuing to follow the videos and hope everything "clicks" at some point.

## Technical Hypothesis
I'm going to assume this is the best way to build out an agent that lets us keep adding new features in Week 2. I'm also hoping this is a good way to really understand how agents work in different scenarios. By pushing us through these details, I think we'll come away with a better understanding of agent builds instead of just "reading the manual."

I also hope this doesn't cost me too much as I convert these to Python and test the agent against the MUD. I've already used about 50% of my weekly token usage on Claude. I tried GitHub Copilot, but that was a disaster — probably needed a different model and effort level. It might also help to add some of the same skills to Copilot that I've added to Claude Code.

## Technical Observations
To help understand the code, besides watching the videos for each phase, I'm also converting these to Python. I have a bit more experience with Python and have used Claude Code to build applications with it before. It'll take more tokens, but I'm hoping it gives me the ability to look deeper and ask better questions to understand this week's goals.

### For this conversion
- Some areas required more work (tokens) for AI to convert Ruby to Python.
- I'm about halfway through the phases and haven't seen an issue with anything Claude Code produced.
- Having the right skills was key to coming up with specific plans and writing the code in stages using subagents. (I'm leaving the plan.md files for each phase in the repo for reference.)
- Was able to build a .env file (and not commit it) while using Ollama. This helps get the agent up and running faster without wasting tokens. I may still put some money into Anthropic's API to test speed — I don't have the hardware to run the larger Gemma models.
- During the port, when I got to 08_the_repl_loop, the example didn't work. I used the example.py file and had Claude explain why. It found the issue and fixed it on the first try.
- I started porting the 09 folder to Python before watching the videos. This might not have been needed, but I'll let it go and figure out how to test it since there's no example program for it.
- Once I got to the last step of the conversion, I was able to run it, but it had no tools to connect to the MUD — I could ask about local file information, just not the MUD itself. I used AI to find the gap and had it go back and fix phases 10, 11, and 12. It also hadn't documented how to connect to the MUD, so it's adding that to the .boukensha settings.yaml.example file.

### Ongoing testing of the 12_baseline code
- Finally got the program working. I asked it to find the bakery and it did so in 25 steps. I watched it play out in the Ruby log_viz program — it's using local Ollama as the model. I'm adding a few different features to help with the TUI.
- I asked it to find water to drink, and it found the fountain but didn't realize it could drink until I told it to. I wonder if that's worth adding.
- I also noticed I can't interject until it hits 25 iterations, so I just have to watch the agent run through instructions until it completes. It definitely needs constant babysitting. It does seem to understand looting for gold and items, though.
- It doesn't seem to know how to get out of resting. I might need to tweak the code — not sure if this was solved in Ruby and just didn't carry over correctly. I'll ask AI to review everything related to commands.

### Built a copy of the 12_baseline code to experiment
- Added memory/map functionality in a new folder called 13_memory. That seemed to help once running, though it was buggy at first and I had Claude Code work through it. It seems to be building the map feature under the .boukensha folder fairly well — I just need to double check it's actually using that map by telling it to go back and find rooms it already discovered. It's still missing some information, like what's actually in a room, and possibly what class the player is, which I think could help. The agent still needs a lot of hand-holding when it gets stuck, and it does get stuck often even with the memory map feature in place.
- I created it as a separate folder, 13_memory, so if I need the original in Week 2, I can just fall back to folder 12. Nothing should be impacted, and I can keep experimenting in 13.
- The map data is stored in the .boukensha folder, under a subfolder called maps. I'm going to let Git upload that to GitHub so I can reuse it if I'm testing on another computer — that way I don't have to rebuild the maps from scratch.
- Maps are created per user account, so if I'm running multiple users at the same time, they're not stepping on each other's toes.
- I went through the different Python folders and created an architecture.md file so I could understand what's going on a little better. I'm not an architect or developer, so it's a bit above me, but it helped, and I can reference it later, especially if I need to build things out in Claude Code.
- I also used Graphify to build out the links between the programs in the 13 folder. I didn't commit that to Git, but it's helped a lot — Claude Code uses it to understand the whole environment instead of pulling everything into context. It can find what it needs in the graphify-out folder, which has saved a ton on token usage.
- Finally tested the agent with all the changes. It was better, but there were still a couple of issues. It got fixated on one goal and wouldn't stop — once it ran through the 25 steps, even if I gave it a different goal (go eat food at the bakery), it would still fall back to the original goal, especially if it couldn't meet the new one. Not sure how to fix that yet, or whether it's a code issue or an LLM issue.
- I'm also wondering if my local Ollama model just isn't up to the challenge. I don't want to move to paid Anthropic usage yet (I'm using that mainly to help understand the code). This might be an ongoing challenge I'll have to live with.

## Technical Conclusions
I think this was an interesting Week 1. There was a ton of work to do — AI made it easier, but understanding the different parts was above my head at times. We're still building out the agent to act as an average player of the game, and I'm finding that combining an LLM with different coding tools is a challenge to get right. The LLM gets confused easily, and its logic can feel random — it looks good for a while, then goes off on strange tangents or just gets stuck. A human player would at least try to reason through the issue and come up with new strategies; the LLM doesn't really do that. Coding seems to be the answer, but where's the line between what the LLM should be responsible for and what should be handled in code? Too much on the LLM side and it gets random; too much on the code side and it gets rigid.

There's also the question of cost related to token usage. At what point does it make more sense to just have 2 or 3 players test something out, versus building and running an agent to do it? Where's the cost justification?

## Key Takeaways
I think we're still trying to build this agent to work like a simple player, not even an average one. It needs to understand the game, the goals, and when to change course. The ultimate goal we should be thinking about is how we add the logic for the agent to come back and explain where the pain points are for users — that's the real goal for the business. Which week will we start focusing on that?
