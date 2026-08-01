from __future__ import annotations
from boukensha.memory.knowledge import KnowledgeManager


def _build_knowledge_section(entries, token_cap=2000):
    # Import after Task 3 is implemented
    from boukensha._knowledge_injection import build_knowledge_section
    return build_knowledge_section(entries, token_cap)


def test_empty_entries_returns_empty_string(tmp_path):
    from boukensha._knowledge_injection import build_knowledge_section
    assert build_knowledge_section([]) == ""


def test_single_entry_appears_in_section(tmp_path):
    from boukensha._knowledge_injection import build_knowledge_section
    entries = [{"topic": "red key", "fact": "Ask the guard.", "source": "guard", "timestamp": "2026-01-01"}]
    result = build_knowledge_section(entries)
    assert "## World Knowledge" in result
    assert "[red key]" in result
    assert "Ask the guard." in result
    assert "(source: guard)" in result


def test_entries_beyond_cap_are_truncated():
    from boukensha._knowledge_injection import build_knowledge_section
    # Each entry is ~60 chars = ~15 tokens. Cap at 30 tokens = ~2 entries.
    entries = [
        {"topic": f"topic{i}", "fact": "x" * 40, "source": "src", "timestamp": "2026-01-01"}
        for i in range(20)
    ]
    result = build_knowledge_section(entries, token_cap=30)
    assert "## World Knowledge" in result
    # Should contain far fewer than 20 entries
    assert result.count("- [") < 10


def test_no_entries_no_section_header():
    from boukensha._knowledge_injection import build_knowledge_section
    assert "## World Knowledge" not in build_knowledge_section([])
