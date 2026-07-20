import os
from pathlib import Path

# Override the config directory so the example works from the repo root.
# In real usage a user's ~/.boukensha is picked up automatically.
os.environ.setdefault(
    "BOUKENSHA_DIR", str((Path(__file__).parent.parent.parent.parent.parent / ".boukensha").resolve())
)

from boukensha import Config, Context, Tool
from boukensha.tasks import Player

config = Config()
player_settings = config.tasks("player")
system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
)

ctx = Context(task=Player, system=system_prompt)

ctx.register_tool(
    Tool(
        name="move",
        description="Move the player in a direction (north, south, east, west, up, down)",
        parameters={"direction": {"type": "string", "description": "The direction to move"}},
        block=lambda direction: f"You move {direction} into a torch-lit corridor.",
    )
)

ctx.add_message("user", "Explore north and tell me what you find.")
ctx.add_message("assistant", "Sure, let me head north and take a look.")

print("=== Boukensha Step 1: Struct Skeleton ===")
print()
print(f"Config:   {config}")
print(f"Context:  {ctx}")
print(f"Tool:     {ctx.tools['move']}")
print("Messages:")
for m in ctx.messages:
    print(f"  {m}")
