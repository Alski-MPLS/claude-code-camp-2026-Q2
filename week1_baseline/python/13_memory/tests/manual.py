uv run python -c "
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path('src')))
os.environ.setdefault('BOUKENSHA_DIR', str(Path('examples').parent.parent.parent.parent.parent / '.boukensha'))

from boukensha.config import Config
cfg = Config()
print('BOUKENSHA_DIR:', cfg.dir)
print('mud.username:', cfg.mud_username)
print('mud.host:', cfg.mud_host)
print('maps path would be:', Path(cfg.dir) / 'maps' / f'{cfg.mud_username}.json')
"