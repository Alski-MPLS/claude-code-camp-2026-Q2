from __future__ import annotations

from pathlib import Path

import pytest

import boukensha_loader


def _make_step_dir(tmp_path: Path, *, with_package: bool = True) -> Path:
    step_dir = tmp_path / "some_step"
    pkg_dir = step_dir / "src" / "boukensha"
    pkg_dir.mkdir(parents=True)
    if with_package:
        (pkg_dir / "__init__.py").write_text("MARKER = 'fake-step'\n")
    return step_dir


def test_resolve_defaults_to_bundled_src_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("BOUKENSHA_PATH", raising=False)
    monkeypatch.setattr(boukensha_loader.Path, "home", lambda: tmp_path)
    assert boukensha_loader.resolve() == boukensha_loader.BUNDLED_SRC_DIR


def test_resolve_uses_boukensha_path_env_var(monkeypatch, tmp_path):
    step_dir = _make_step_dir(tmp_path)
    monkeypatch.setenv("BOUKENSHA_PATH", str(step_dir))
    assert boukensha_loader.resolve() == str(step_dir / "src")


def test_resolve_boukensha_path_missing_package_aborts(monkeypatch, tmp_path):
    step_dir = _make_step_dir(tmp_path, with_package=False)
    monkeypatch.setenv("BOUKENSHA_PATH", str(step_dir))
    with pytest.raises(SystemExit, match="BOUKENSHA_PATH is set"):
        boukensha_loader.resolve()


def test_resolve_uses_boukensharc_file(monkeypatch, tmp_path):
    monkeypatch.delenv("BOUKENSHA_PATH", raising=False)
    step_dir = _make_step_dir(tmp_path)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".boukensharc").write_text(f"{step_dir}\n")
    monkeypatch.setattr(boukensha_loader.Path, "home", lambda: fake_home)
    assert boukensha_loader.resolve() == str(step_dir / "src")


def test_resolve_boukensharc_missing_package_aborts(monkeypatch, tmp_path):
    step_dir = _make_step_dir(tmp_path, with_package=False)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".boukensharc").write_text(f"{step_dir}\n")
    monkeypatch.delenv("BOUKENSHA_PATH", raising=False)
    monkeypatch.setattr(boukensha_loader.Path, "home", lambda: fake_home)
    with pytest.raises(SystemExit, match=r"\.boukensharc points to"):
        boukensha_loader.resolve()


def test_resolve_env_var_wins_over_boukensharc(monkeypatch, tmp_path):
    env_step = _make_step_dir(tmp_path)
    (env_step / "src" / "boukensha" / "__init__.py").write_text("MARKER = 'env'\n")

    rc_step_dir = tmp_path / "rc_step"
    rc_pkg = rc_step_dir / "src" / "boukensha"
    rc_pkg.mkdir(parents=True)
    (rc_pkg / "__init__.py").write_text("MARKER = 'rc'\n")

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".boukensharc").write_text(f"{rc_step_dir}\n")
    monkeypatch.setattr(boukensha_loader.Path, "home", lambda: fake_home)
    monkeypatch.setenv("BOUKENSHA_PATH", str(env_step))

    assert boukensha_loader.resolve() == str(env_step / "src")


def test_resolve_blank_boukensharc_falls_through_to_bundled(monkeypatch, tmp_path):
    monkeypatch.delenv("BOUKENSHA_PATH", raising=False)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".boukensharc").write_text("   \n")
    monkeypatch.setattr(boukensha_loader.Path, "home", lambda: fake_home)
    assert boukensha_loader.resolve() == boukensha_loader.BUNDLED_SRC_DIR
