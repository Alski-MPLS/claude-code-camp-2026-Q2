from __future__ import annotations
import pytest
from boukensha.registry import Registry
from boukensha.context import Context
from boukensha.tasks.player import Player
from boukensha.tools.knowledge import Knowledge


@pytest.fixture
def registry_with_knowledge(tmp_path):
    ctx = Context(task=Player)
    reg = Registry(ctx)
    Knowledge.register(reg, knowledge_dir=tmp_path)
    return reg, tmp_path


def test_knowledge_add_returns_confirmation(registry_with_knowledge):
    reg, _ = registry_with_knowledge
    result = reg.dispatch("knowledge_add", {
        "topic": "red key",
        "fact": "Ask the east gate guard.",
        "source": "east gate guard",
    })
    assert "red key" in result.lower() or "saved" in result.lower() or "added" in result.lower()


def test_knowledge_add_persists_to_file(registry_with_knowledge):
    reg, tmp_path = registry_with_knowledge
    reg.dispatch("knowledge_add", {
        "topic": "minotaur",
        "fact": "Needs the red key.",
        "source": "innkeeper",
    })
    from boukensha.memory.knowledge import KnowledgeManager
    km = KnowledgeManager(tmp_path)
    entries = km.read_all()
    assert any(e["topic"] == "minotaur" for e in entries)


def test_knowledge_search_returns_matching_entries(registry_with_knowledge):
    reg, tmp_path = registry_with_knowledge
    reg.dispatch("knowledge_add", {"topic": "red key", "fact": "Ask the guard.", "source": "guard"})
    reg.dispatch("knowledge_add", {"topic": "minotaur", "fact": "Needs the red key.", "source": "innkeeper"})
    result = reg.dispatch("knowledge_search", {"query": "minotaur"})
    assert "minotaur" in result.lower()
    assert "- [red key]" not in result.lower()


def test_knowledge_search_no_results(registry_with_knowledge):
    reg, _ = registry_with_knowledge
    result = reg.dispatch("knowledge_search", {"query": "dragon"})
    assert "no" in result.lower() or result.strip() == "" or "0" in result


def test_knowledge_search_returns_multiple_matches(registry_with_knowledge):
    reg, _ = registry_with_knowledge
    reg.dispatch("knowledge_add", {"topic": "red key", "fact": "Ask the guard.", "source": "east gate guard"})
    reg.dispatch("knowledge_add", {"topic": "blue key", "fact": "Found on the inn table.", "source": "innkeeper"})
    result = reg.dispatch("knowledge_search", {"query": "key"})
    assert "red key" in result.lower()
    assert "blue key" in result.lower()
