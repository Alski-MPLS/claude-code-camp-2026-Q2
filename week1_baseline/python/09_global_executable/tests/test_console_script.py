from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

STEP_DIR = Path(__file__).parent.parent


def _run_console_script(*, env_overrides: dict[str, str], stdin_text: str = "/exit\n") -> subprocess.CompletedProcess:
    boukensha_bin = STEP_DIR / ".venv" / "bin" / "boukensha"
    env = {**os.environ, **env_overrides}
    return subprocess.run(
        [str(boukensha_bin)],
        input=stdin_text,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_console_script_boots_bundled_default(boukensha_dir_with_settings):
    result = _run_console_script(env_overrides={"BOUKENSHA_DIR": str(boukensha_dir_with_settings)})
    assert "BOUKENSHA MUD Assistant" in result.stdout
    assert "Goodbye." in result.stdout


def test_console_script_debug_flag_reports_bundled_path(boukensha_dir_with_settings):
    result = _run_console_script(
        env_overrides={"BOUKENSHA_DIR": str(boukensha_dir_with_settings), "BOUKENSHA_DEBUG": "1"},
    )
    assert "[boukensha] loading from:" in result.stdout
    assert str(STEP_DIR) in result.stdout


def test_console_script_boukensha_path_missing_package_errors(boukensha_dir_with_settings, tmp_path):
    missing_step = tmp_path / "not_a_step"
    result = _run_console_script(
        env_overrides={"BOUKENSHA_DIR": str(boukensha_dir_with_settings), "BOUKENSHA_PATH": str(missing_step)},
    )
    assert result.returncode != 0
    assert "BOUKENSHA_PATH is set" in result.stderr
