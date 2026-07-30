from __future__ import annotations

import pytest
from pathlib import Path


@pytest.fixture
def boukensha_dir_with_settings(tmp_path):
    """Create a BOUKENSHA_DIR with a minimal settings.yaml for testing."""
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text("""
tasks:
  player:
    provider: anthropic
    model: claude-haiku-4-5
""")
    return tmp_path
