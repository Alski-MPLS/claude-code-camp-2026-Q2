from __future__ import annotations
from boukensha.memory.knowledge import KnowledgeManager


def test_add_and_read_all(tmp_path):
    km = KnowledgeManager(tmp_path)
    km.add("red key", "Ask the east gate guard.", "east gate guard")
    entries = km.read_all()
    assert len(entries) == 1
    assert entries[0]["topic"] == "red key"
    assert entries[0]["fact"] == "Ask the east gate guard."
    assert entries[0]["source"] == "east gate guard"
    assert "timestamp" in entries[0]


def test_add_deduplicates_by_topic_case_insensitive(tmp_path):
    km = KnowledgeManager(tmp_path)
    km.add("Red Key", "old fact", "old source")
    km.add("red key", "new fact", "new source")
    entries = km.read_all()
    assert len(entries) == 1
    assert entries[0]["fact"] == "new fact"


def test_read_all_returns_newest_first(tmp_path):
    km = KnowledgeManager(tmp_path)
    km.add("alpha", "first", "src")
    km.add("beta", "second", "src")
    entries = km.read_all()
    assert entries[0]["topic"] == "beta"
    assert entries[1]["topic"] == "alpha"


def test_search_matches_topic(tmp_path):
    km = KnowledgeManager(tmp_path)
    km.add("red key", "Ask the guard.", "east gate guard")
    km.add("minotaur", "Needs the red key.", "innkeeper")
    results = km.search("minotaur")
    assert len(results) == 1
    assert results[0]["topic"] == "minotaur"


def test_search_matches_fact(tmp_path):
    km = KnowledgeManager(tmp_path)
    km.add("red key", "Ask the east gate guard.", "east gate guard")
    results = km.search("east gate")
    assert len(results) == 1


def test_search_matches_source(tmp_path):
    km = KnowledgeManager(tmp_path)
    km.add("red key", "Ask the east gate guard.", "east gate guard")
    results = km.search("innkeeper")
    assert len(results) == 0
    km.add("minotaur", "Needs the red key.", "innkeeper")
    results = km.search("innkeeper")
    assert len(results) == 1


def test_search_is_case_insensitive(tmp_path):
    km = KnowledgeManager(tmp_path)
    km.add("Red Key", "Ask the Guard.", "Guard")
    results = km.search("red key")
    assert len(results) == 1


def test_read_all_empty_when_no_file(tmp_path):
    km = KnowledgeManager(tmp_path)
    assert km.read_all() == []


def test_atomic_write_no_partial_state(tmp_path):
    km = KnowledgeManager(tmp_path)
    km.add("alpha", "fact", "src")
    km.add("beta", "fact2", "src2")
    # Verify temp file is gone after write
    import os
    assert not any(f.endswith(".tmp") for f in os.listdir(tmp_path)
                   if isinstance(f, str))
    assert (tmp_path / "knowledge.yaml").exists()
