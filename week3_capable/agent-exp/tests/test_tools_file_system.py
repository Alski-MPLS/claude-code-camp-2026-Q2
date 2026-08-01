from __future__ import annotations

from pathlib import Path

from boukensha.context import Context
from boukensha.registry import Registry
from boukensha.tasks.player import Player
from boukensha.tools.file_system import FileSystem


def _make_registry() -> Registry:
    ctx = Context(task=Player, system="sys")
    return Registry(ctx)


def test_pwd_returns_root(tmp_path):
    registry = _make_registry()
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("pwd", {})
    assert result == str(tmp_path.resolve())


def test_list_directory_lists_files_and_dirs(tmp_path):
    (tmp_path / "hello.txt").write_text("hi")
    (tmp_path / "subdir").mkdir()
    registry = _make_registry()
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("list_directory", {"path": "."})
    assert "hello.txt" in result
    assert "subdir/" in result


def test_list_directory_default_path(tmp_path):
    (tmp_path / "file.txt").write_text("content")
    registry = _make_registry()
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("list_directory", {})
    assert "file.txt" in result


def test_list_directory_empty_dir(tmp_path):
    registry = _make_registry()
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("list_directory", {"path": "."})
    assert result == "(empty)"


def test_list_directory_not_a_directory(tmp_path):
    (tmp_path / "file.txt").write_text("content")
    registry = _make_registry()
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("list_directory", {"path": "file.txt"})
    assert result.startswith("error:")


def test_read_file_returns_contents(tmp_path):
    (tmp_path / "notes.txt").write_text("hello world")
    registry = _make_registry()
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("read_file", {"path": "notes.txt"})
    assert result == "hello world"


def test_read_file_not_a_file(tmp_path):
    (tmp_path / "subdir").mkdir()
    registry = _make_registry()
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("read_file", {"path": "subdir"})
    assert result.startswith("error:")


def test_write_file_creates_file(tmp_path):
    registry = _make_registry()
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("write_file", {"path": "new.txt", "content": "created"})
    assert result.startswith("ok:")
    assert (tmp_path / "new.txt").read_text() == "created"


def test_write_file_reports_byte_count(tmp_path):
    registry = _make_registry()
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("write_file", {"path": "bytes.txt", "content": "abc"})
    assert "3 bytes" in result


def test_write_file_creates_parent_directories(tmp_path):
    registry = _make_registry()
    FileSystem.register(registry, working_dir=str(tmp_path))
    registry.dispatch("write_file", {"path": "a/b/c.txt", "content": "nested"})
    assert (tmp_path / "a" / "b" / "c.txt").read_text() == "nested"


def test_delete_file_removes_file(tmp_path):
    (tmp_path / "target.txt").write_text("bye")
    registry = _make_registry()
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("delete_file", {"path": "target.txt"})
    assert result.startswith("ok:")
    assert not (tmp_path / "target.txt").exists()


def test_delete_file_rejects_directory(tmp_path):
    (tmp_path / "adir").mkdir()
    registry = _make_registry()
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("delete_file", {"path": "adir"})
    assert result.startswith("error:")


def test_path_traversal_rejected(tmp_path):
    registry = _make_registry()
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("read_file", {"path": "../../etc/passwd"})
    assert result.startswith("error:")
    assert "escapes" in result


def test_search_files_finds_pattern(tmp_path):
    (tmp_path / "a.txt").write_text("hello world\nfoo bar\n")
    (tmp_path / "b.txt").write_text("hello again\n")
    registry = _make_registry()
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("search_files", {"pattern": "hello"})
    assert "a.txt:1:hello world" in result
    assert "b.txt:1:hello again" in result


def test_search_files_no_matches(tmp_path):
    (tmp_path / "a.txt").write_text("nothing here\n")
    registry = _make_registry()
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("search_files", {"pattern": "ZZZMISSING"})
    assert result == "no matches"


def test_search_files_with_glob_filter(tmp_path):
    (tmp_path / "a.py").write_text("pattern_here\n")
    (tmp_path / "b.txt").write_text("pattern_here\n")
    registry = _make_registry()
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("search_files", {"pattern": "pattern_here", "glob": "*.py"})
    assert "a.py" in result
    assert "b.txt" not in result


def test_search_files_invalid_pattern(tmp_path):
    registry = _make_registry()
    FileSystem.register(registry, working_dir=str(tmp_path))
    result = registry.dispatch("search_files", {"pattern": "["})
    assert result.startswith("error: invalid pattern")
