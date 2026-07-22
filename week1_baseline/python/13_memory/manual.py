import os, sys
from pathlib import Path
sys.path.insert(0, str(Path('src')))
os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path(__file__).parent.parent.parent.parent / ".boukensha"),
)
import boukensha
from boukensha.config import Config
cfg = Config()
print('BOUKENSHA_DIR:', cfg.dir)
print('mud.username:', cfg.mud_username)
print('maps path:', Path(cfg.dir) / 'maps' / f'{cfg.mud_username}.json')


# BOUKENSHA_DIR: /Users/alanw/.boukensha
# mud.username: None
# maps path: /Users/alanw/.boukensha/maps/None.json

# BOUKENSHA_DIR: /Users/alanw/code/github/ai/claude-code-camp-2026-Q2/week1_baseline/python/13_memory/tests/.boukensha
# mud.username: None
# mud.host: localhost
# maps path would be: /Users/alanw/code/github/ai/claude-code-camp-2026-Q2/week1_baseline/python/13_memory/tests/.boukensha/maps/None.json
