# Agent Experience build

## Goal

This is a copy of week1_baseline/python/12_context folder and renamed to agent-exp. This program should provide deeper visibility to the player so they can pull data on what exactly is happening behind the scenes. Besides the simple information that is being seen/completed, it should also give data on the time necessary, etc. The goal of this folder is to refactor the agent created to meet the following:

- I was able to find a list of the commands and what they do. These are located in the mud-commands.md file. 


- Create a Memory section in the .boukensha folder that will hold the details of the rooms visited. There was an attempt to build this out but the LLM seemed not to use it when asked to go to a specific area. It should the exits along with where they connect to, the description, any characters or items there and anything else that would destingush it from other areas. We would want to utilize some kind of hashing mechanism. I think that this should be a program/script instead of the LLM handling this. Understand that some rooms may be missing some of this information so it will have to handle that. The file should grow automatically and used to determine the proper path to a location. 
- There should be a goal section in the .bokensha folder that will help the agent understand the current ask of it. The agent should be able to update it based on the situation (i.e. if the hit points drops below 5, the agent should decide what to do). This should be automatically updated. This section should also have the basic instructions on how to use the MUD. the LLM should be pulling this informaiton into it's context and reviewing/updating it constantly. 
- Build out a way for the player to see exactly what is happening, how long each step takes, the current goal and the details observed. It should also have a tab that will show you the map built for that player that you can click on a specific room for details. It should also show in another tab a waterfall type graph that will show the steps taken and the time needed. This will help with identifying areas that are taking too long. The original sinatra app (log_viz) has been superseded by the Python dashboard (see DASHBOARD.md). i want this to be modular so that if I want to add more features/tabs, it should be easy to do.
- The agent should keep the amount of tokens to a minimum. Let's review the architecture and come up with ways to limit the number of tokens needed. In my mind, this could be as simple as limiting needing to use the LLM. So, do we build out tools that will be used for things like:
    - Program to review a room everytime a player enters in. Document all of the details if it's a new room and update the map area. It will log the information the same or lookup what needs to be reviewed for the LLM to make a decision.
    - Program that can help with fighting foes. Continue to fight or flee based on specific goals at that particular time.
    - Program for understanding the best path to get from one place to another. using some kind of shortest path with the details from the map data. So, if the LLM decides it needs to eat food, it uses a tool/program to show how to get there and moves the character there in the MUD.
    - [Place holder on anything else seen]

- Is there a way to skip the TUI and come up with a program that will have something similar but will also have the maps tab and details on what is being asked against the MUD And what is being sent back for better visibility? What are the options for this. So, you don't need to have the TUI running and a webpage with the details of the seesions. 

- Build this out in Python and create a program called boukensha in a bin directory that I can use to run the TUI. 


All of these changes should be in the /week2_capable/agent-exp folder or the /.boukensha folder at the root of the repo. 
