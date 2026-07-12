# Player State

- **Name:** dummy
- **Password:** helloworld
- **Sex:** Male
- **Class:** Warrior (selected class 'w' during creation)
- **Status:** Character created and logged in successfully.
- **Current location (last known):** The Pet Shop (north of Dark Alley, off Common Square)
- **HP/Mana/Move (last seen):** 7H 100M 62V

## Login flow (for reference)
1. Connect via `nc localhost 4000`
2. At "By what name do you wish to be known?" -> `dummy`
3. At "Did I get that right (Y/N)?" -> `yes`
4. At "Password:" -> `helloworld`
5. If new character: retype password, then select sex (m/f), then select class (c/t/w/m)
6. At "Make your choice:" main menu -> `1` to enter the game
7. Character spawns at **The Temple of Midgaard**

## Notes
- Quitting and re-entering the game resets location to "By The Temple Altar" unless you `rent` at an Inn reception to persist your location.
- Still need to `rent` at the Grunting Boar Inn reception to persist state between sessions.
