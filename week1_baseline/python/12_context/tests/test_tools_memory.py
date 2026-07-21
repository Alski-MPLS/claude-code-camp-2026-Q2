from __future__ import annotations

from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player
from boukensha.tools.memory import Memory


def _make_registry() -> Registry:
    ctx = Context(task=Player, system="sys")
    return Registry(ctx)


def test_register_adds_expected_tools(tmp_path):
    registry = _make_registry()
    Memory.register(registry, memory_dir=str(tmp_path))
    assert registry.get("read_memory") is not None
    assert registry.get("write_memory") is not None


def test_register_creates_default_files(tmp_path):
    registry = _make_registry()
    Memory.register(registry, memory_dir=str(tmp_path))
    assert (tmp_path / "player.md").exists()
    assert (tmp_path / "world.md").exists()


def test_register_creates_missing_directory(tmp_path):
    memory_dir = tmp_path / "nested" / "memory"
    registry = _make_registry()
    Memory.register(registry, memory_dir=str(memory_dir))
    assert (memory_dir / "player.md").exists()
    assert (memory_dir / "world.md").exists()


def test_read_memory_returns_default_template(tmp_path):
    registry = _make_registry()
    Memory.register(registry, memory_dir=str(tmp_path))
    result = registry.dispatch("read_memory", {"file": "player"})
    assert "nothing recorded yet" in result


def test_write_memory_then_read_memory_round_trips(tmp_path):
    registry = _make_registry()
    Memory.register(registry, memory_dir=str(tmp_path))
    write_result = registry.dispatch(
        "write_memory", {"file": "world", "content": "# World Map\n\nRoom 1 -> north -> Room 2\n"}
    )
    assert write_result.startswith("ok:")
    read_result = registry.dispatch("read_memory", {"file": "world"})
    assert read_result == "# World Map\n\nRoom 1 -> north -> Room 2\n"


def test_write_memory_overwrites_existing_content(tmp_path):
    registry = _make_registry()
    Memory.register(registry, memory_dir=str(tmp_path))
    registry.dispatch("write_memory", {"file": "player", "content": "first"})
    registry.dispatch("write_memory", {"file": "player", "content": "second"})
    result = registry.dispatch("read_memory", {"file": "player"})
    assert result == "second"


def test_read_memory_rejects_unknown_file(tmp_path):
    registry = _make_registry()
    Memory.register(registry, memory_dir=str(tmp_path))
    result = registry.dispatch("read_memory", {"file": "monsters"})
    assert result.startswith("error:")


def test_write_memory_rejects_unknown_file(tmp_path):
    registry = _make_registry()
    Memory.register(registry, memory_dir=str(tmp_path))
    result = registry.dispatch("write_memory", {"file": "monsters", "content": "x"})
    assert result.startswith("error:")
    assert not (tmp_path / "monsters.md").exists()


def test_prompt_block_contains_both_files_and_content(tmp_path):
    (tmp_path).mkdir(exist_ok=True)
    from boukensha.tools.memory import Memory as M
    M.register(_make_registry(), memory_dir=str(tmp_path))
    (tmp_path / "player.md").write_text("# Player Notes\n\nLevel 3 warrior.\n")
    block = M.prompt_block(str(tmp_path))
    assert "player.md" in block
    assert "world.md" in block
    assert "Level 3 warrior." in block


def test_prompt_block_instructs_writing_on_every_new_room(tmp_path):
    block = Memory.prompt_block(str(tmp_path))
    assert "new room" in block
    assert "before" in block
    assert "write_memory" in block


def test_prompt_block_creates_files_if_missing(tmp_path):
    memory_dir = tmp_path / "fresh"
    block = Memory.prompt_block(str(memory_dir))
    assert (memory_dir / "player.md").exists()
    assert (memory_dir / "world.md").exists()
    assert "nothing recorded yet" in block


def test_tools_module_exports_memory():
    from boukensha import tools
    assert hasattr(tools, "Memory")


def test_read_memory_catches_io_exception_and_returns_error(tmp_path):
    from unittest.mock import patch
    from pathlib import Path

    registry = _make_registry()
    Memory.register(registry, memory_dir=str(tmp_path))

    # Monkeypatch Path.read_text to raise an OSError
    with patch.object(Path, "read_text", side_effect=OSError("permission denied")):
        result = registry.dispatch("read_memory", {"file": "player"})
        assert result.startswith("error:")
        assert "permission denied" in result


def test_write_memory_catches_io_exception_and_returns_error(tmp_path):
    from unittest.mock import patch
    from pathlib import Path

    registry = _make_registry()
    Memory.register(registry, memory_dir=str(tmp_path))

    # Monkeypatch Path.write_text to raise an OSError
    with patch.object(Path, "write_text", side_effect=OSError("disk full")):
        result = registry.dispatch("write_memory", {"file": "world", "content": "test"})
        assert result.startswith("error:")
        assert "disk full" in result
