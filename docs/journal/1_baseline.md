# Week1 Technical Documentation

## Technical Goal
I think the technical goal is to understand the different stages of how this agent was built. Each stage builds off the previous stage and helps with understanding the logical data flows. During the week1 Saturday video, we were shown the final application that I believe is what we are trying to build and understand. This is my first thoughts as I work through the different videos and try to understand the deeper goals with this week. I will probably add further content in this section, once I complete the videos.

## Technical Uncertainty
I am not a developer. I don't know how RUBY works and have a limited understanding on how python works. So, I'm not sure if what is being built is best-practice for the overall goal of the course or if we will run into potential issues in the near term. I plan on continuing to follow the video's and hope that everything "clicks" at some point.

## Technical Hypothesis
I'm going to assuming that this is the best way to build out an agent that will allow us to continue to add new features in week 2. I'm also hoping that this is a good example on how to really understand how agents work in different scenarios. By pushing us to go through these different details, we will have a better understanding on agent builds without just "reading the manual".
I also hope this is not going to cost me too much as I convert these to python and test out the agent against the MUD. I've already used about 50% of my weekly token usage on Claude. I tried to use github copilot but that was a disaster (probably needed to use a different model and level of effort. It might also help to add in additional skills like I have added to claude code.)

## Technical Observations
To help understandt the code, besides watching the videos for each phase, I'm also working on converting these to Python. I have a bit more understanding with Python and I've used claude code to build out some applications already with python. It will take up more tokens but I'm hoping this gives me the ability to look deeper and ask an AI better questions to understand the goals for this week.

For this conversion
- Some areas required more work (tokens) for AI to convert Ruby to Python.
- I'm half-way through the different phases and I have not seen an issue with what was created in Claude Code.
- Having the right skills was key to coming up with specific plans and write the code in stages using subagents. (I'm leaving the plan.md files for each phase in the repo for references).
- Was able to build out .env file (and not commit it) while using Ollama. This will help get the agent up and running faster without wasting tokens. I still may have to put some money in Anthropics API area to test it out for speed. I don't have the right hardware to utilize the large gemma4 models. 
- During the port, when i got to 08_the_repl_loop, it had an issue where the example didn't work. I was able to use the example.py file and explain why it wasn't working. Claude was able to find an issue in the code and was able to fix it on the first try.
- I started porting the 09 folder to python before I watched the video's. This might not be needed but I'll let it go and figure out how to test it since there is no example program.
- Once I got to the last step for the conversion over to python, I was able to run it but it did not have any tools to connect to the MUD. I could ask it about local file information but not with the MUD. I used AI to find the issues and it had to go back and add what was missed. I had it fix the 10, 11 and 12 phases. It also did not have the details on how to connect to MUD so it's adding them to the .boukensha settings.yaml.example file.
- Finally got the program working now. I asked it to find the bakery and it was able to do so in 25 steps. I watched it in the ruby log_viz program. It's using local Ollama as the AI. I'm adding some differnet features to help with the TUI. 
- I asked it to find water to drink and it found the fountain but didn't understand it could drink until I told it to. I wonder if I should add that.
- I also noticed that I can't interject until it hits 25 iterations. So, I just have to watch the agent run through the instructions until it completes. It definatly needs constant baby-sitting. I also noticed that it might understand how to loot for gold and items.
- It doesn't seem to understand how to get out of resting. I might have to tweak the code. Not sure if this was solved in RUBY and didn't come over correclty. I'll ask AI to review everything related to commands.
- Added the memory/map functionality in a new folder called 13_memory. That seemed to help when I ran the program though it was buggy in the beginning and i had to have cloud code try figuring it out. It seems to be building the map feature under the .bokensha folder fairly well I just need to double check and make sure it's actually utilizing that by telling it to go back and find rooms that it already had discovered. It's still missing some information around what is in there and also kind of around what the user is so class and that kind of thing which I think might be able to help. The agent still needs a lot of hand-holding when it gets stuck. And it does seem to get stuck often even with this memory map feature.
- I created it as a folder called 13_memory so if i need to use the original one in week 2, i can just fall back to folder 12 instead. Nothing should impact it and i can still keep experimenting in the 13 folder.
- The map data is stored within the .boukensha folder under a subfolder called maps I'm going to allow Git to upload that information to GitHub so that i can use it if i'm testing this out on another computer. That way I don't have to rebuild the maps from scratch.
- The maps Are created per user account. That way if I'm running multiple users at the same time they're not stepping on each other's toes.
- I had to go through the different Python folders and create an architectural.md file so that i can understand a little bit better what's going on. I'm not an architect or developer so it's a little above me but that did help out a little and I can also use that to reference later especially if I need to build things out in cloud code. 
- I also use Graphify to kind of build out all the links between the programs in the 13 folder. I did not commit that in Git but that has really helped out a lot because Claude Code does use that to understand the total environment instead of having to go back and pull it all into context. It can easily find it within the graphify-out folder. It has saved a ton on token usage.


## Technical Conclusions
[todo]

## Key Takeaways
[todo]