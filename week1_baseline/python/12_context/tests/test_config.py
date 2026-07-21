from __future__ import annotations

from pathlib import Path

import yaml

from boukensha.config import Config


def _write_settings(tmp_path: Path, data: dict) -> None:
    (tmp_path / "settings.yaml").write_text(yaml.dump(data))


def test_memory_enabled_defaults_true(tmp_path, monkeypatch):
    monkeypatch.setenv("BOUKENSHA_DIR", str(tmp_path))
    cfg = Config()
    assert cfg.memory_enabled is True


def test_memory_enabled_respects_false(tmp_path, monkeypatch):
    monkeypatch.setenv("BOUKENSHA_DIR", str(tmp_path))
    _write_settings(tmp_path, {"memory": {"enabled": False}})
    cfg = Config()
    assert cfg.memory_enabled is False


def test_memory_dir_defaults_to_config_dir_subfolder(tmp_path, monkeypatch):
    monkeypatch.setenv("BOUKENSHA_DIR", str(tmp_path))
    cfg = Config()
    assert cfg.memory_dir == str(Path(cfg.dir) / "memory")


def test_memory_dir_respects_override(tmp_path, monkeypatch):
    monkeypatch.setenv("BOUKENSHA_DIR", str(tmp_path))
    custom = str(tmp_path / "custom_mem")
    _write_settings(tmp_path, {"memory": {"dir": custom}})
    cfg = Config()
    assert cfg.memory_dir == custom
