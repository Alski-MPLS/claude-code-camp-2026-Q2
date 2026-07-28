# Game Findings

Running log of things learned about how this particular MUD behaves — quirks,
rules, and mechanics discovered during live play that aren't reflected in the
code yet. Add an entry whenever something surprising turns up; move it into
actual code/tests once it's implemented (leave the entry, just note where it
landed).

## Open

- **Dark rooms require a light source.** Some rooms are dark; entering one
  without a torch/lantern (or an equivalent light spell/item) should be
  avoided until the agent has a light source equipped. Need logic so
  exploration/navigation treats an unlit dark room as a no-go, not just
  another frontier to walk into blind.
