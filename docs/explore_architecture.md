
## 1. Agent file with reference files eg. AGENT.md, @~/docs/*.MD

## Observations

- Starting claude in the explore_architecure and presenting what to accomplish was an easy start.
- It did have issues with login as the character was at a state that was already played.
- At one point, it tried to build a new character which didn't make sense.
- It finally started creating python files in the /tmp directory (saved the details in an ai-summary.md file)
- It was having a hard time with the Haiku model on high effort. 
- It did not save the details in the player.md or world.md files. I had to remind it when I changed models
- It started looking outside of the explore_architecture folder and found the /preview/data/world/wld file and was able to identify the bakery name, location and path.



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

