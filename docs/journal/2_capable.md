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

## Technical Conclusions
[todo]

## Key Takeaways
[todo]