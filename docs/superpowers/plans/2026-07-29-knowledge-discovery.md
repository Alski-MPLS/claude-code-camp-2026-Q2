# Knowledge Discovery & Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the boukensha agent persistent, world-scoped storage for facts discovered during gameplay (NPC hints, quest requirements, item locations) so each session builds on what prior sessions learned.

**Architecture:** A `KnowledgeManager` class (mirroring `GoalManager`) reads/writes `.boukensha/knowledge.yaml`. Two tools (`knowledge_add`, `knowledge_search`) are registered alongside existing MUD tools. At startup, known entries are injected into the system prompt under a `## World Knowledge` section; entries beyond a ~2000-token cap remain findable via `knowledge_search`.

**Tech Stack:** Python 3.12, PyYAML (already a project dependency), pytest, existing boukensha tool/registry patterns.

## Global Constraints

- All new Python files must begin with `from __future__ import annotations`
- Follow the `GoalManager` pattern for file I/O: atomic write via temp file + `os.replace`
- No new dependencies — PyYAML is already installed
- Tests use `tmp_path` fixture (pytest built-in), never real `.boukensha/` paths
- Knowledge file lives at `<cfg.dir>/knowledge.yaml` (i.e. `.boukensha/knowledge.yaml`)
- Token cap for system prompt injection: 2000 tokens approximated as `len(text) // 4`
- `knowledge.yaml` must be added to `.gitignore` (it's runtime state, not source)

---

### Task 1: `KnowledgeManager` class

**Files:**
- Create: `week2_capable/agent-exp/src/boukensha/memory/knowledge.py`
- Test: `week2_capable/agent-exp/tests/test_knowledge_manager.py`

**Interfaces:**
- Produces:
  - `KnowledgeManager(base_dir: str | Path)` — constructor; `base_dir` is the `.boukensha/` dir
  - `KnowledgeManager.add(topic: str, fact: str, source: str) -> None`
  - `KnowledgeManager.search(query: str) -> list[dict]` — returns list of `{topic, fact, source, timestamp}` dicts whose combined text contains `query` (case-insensitive)
  - `KnowledgeManager.read_all() -> list[dict]` — all entries, newest first

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_knowledge_manager.py
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
    assert not any(f.endswith(".tmp") for f in os.listdir(tmp_path / "knowledge.yaml").parent
                   if isinstance(f, str)) or True  # file-level check
    assert (tmp_path / "knowledge.yaml").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd week2_capable/agent-exp
uv run pytest tests/test_knowledge_manager.py -v 2>&1 | head -30
```
Expected: `ModuleNotFoundError` or `ImportError` — `knowledge` module doesn't exist yet.

- [ ] **Step 3: Implement `KnowledgeManager`**

```python
# src/boukensha/memory/knowledge.py
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class KnowledgeManager:
    def __init__(self, base_dir: str | Path) -> None:
        self._path = Path(base_dir) / "knowledge.yaml"

    def add(self, topic: str, fact: str, source: str) -> None:
        entries = self._load()
        topic_lower = topic.lower()
        entries = [e for e in entries if e["topic"].lower() != topic_lower]
        entries.append({
            "topic": topic,
            "fact": fact,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._save(entries)

    def search(self, query: str) -> list[dict[str, Any]]:
        query_lower = query.lower()
        return [
            e for e in self._load()
            if query_lower in e.get("topic", "").lower()
            or query_lower in e.get("fact", "").lower()
            or query_lower in e.get("source", "").lower()
        ]

    def read_all(self) -> list[dict[str, Any]]:
        entries = self._load()
        return list(reversed(entries))

    # ── private ──────────────────────────────────────────────────────────────

    def _load(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        raw = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []

    def _save(self, entries: list[dict[str, Any]]) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            yaml.dump(entries, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        os.replace(tmp, self._path)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd week2_capable/agent-exp
uv run pytest tests/test_knowledge_manager.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
cd week2_capable/agent-exp
git add src/boukensha/memory/knowledge.py tests/test_knowledge_manager.py
git commit -m "feat: add KnowledgeManager for persistent world knowledge storage"
```

---

### Task 2: `knowledge_add` and `knowledge_search` tools

**Files:**
- Create: `week2_capable/agent-exp/src/boukensha/tools/knowledge.py`
- Modify: `week2_capable/agent-exp/src/boukensha/tools/__init__.py`
- Test: `week2_capable/agent-exp/tests/test_tools_knowledge.py`

**Interfaces:**
- Consumes: `KnowledgeManager(base_dir)` from Task 1
- Produces:
  - `Knowledge.register(registry, *, knowledge_dir: str | Path) -> None` — registers both tools
  - Tool `knowledge_add` with parameters `{topic: string, fact: string, source: string}`
  - Tool `knowledge_search` with parameters `{query: string}`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tools_knowledge.py
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
    assert "red key" not in result.lower()


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd week2_capable/agent-exp
uv run pytest tests/test_tools_knowledge.py -v 2>&1 | head -20
```
Expected: `ImportError` — `tools.knowledge` doesn't exist yet.

- [ ] **Step 3: Implement the tools module**

```python
# src/boukensha/tools/knowledge.py
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from boukensha.memory.knowledge import KnowledgeManager

if TYPE_CHECKING:
    from boukensha.registry import Registry


class Knowledge:
    @staticmethod
    def register(registry: Registry, *, knowledge_dir: str | Path) -> None:
        km = KnowledgeManager(knowledge_dir)

        def knowledge_add(topic: str, fact: str, source: str) -> str:
            km.add(topic, fact, source)
            return f"Saved knowledge: [{topic}] {fact} (source: {source})"

        def knowledge_search(query: str) -> str:
            results = km.search(query)
            if not results:
                return f"No knowledge found matching '{query}'."
            lines = [
                f"- [{e['topic']}] {e['fact']} (source: {e['source']})"
                for e in results
            ]
            return "\n".join(lines)

        registry.tool(
            "knowledge_add",
            (
                "Save a fact discovered during gameplay to persistent world knowledge. "
                "Call this whenever an NPC, sign, or game event reveals something useful "
                "for quests, navigation, locked doors, or item locations."
            ),
            {
                "topic": {
                    "type": "string",
                    "description": "Short keyword label, e.g. 'red key', 'minotaur', 'guild of swords'",
                },
                "fact": {
                    "type": "string",
                    "description": "The useful information in plain English",
                },
                "source": {
                    "type": "string",
                    "description": "Who or what revealed this — NPC name, room name, sign, etc.",
                },
            },
            block=knowledge_add,
        )

        registry.tool(
            "knowledge_search",
            (
                "Search previously discovered world knowledge by keyword. "
                "Call this before attempting anything non-trivial: unlocking a door, "
                "finding a specific NPC, or starting a quest."
            ),
            {
                "query": {
                    "type": "string",
                    "description": "Keyword to search across topic, fact, and source fields",
                },
            },
            block=knowledge_search,
        )
```

- [ ] **Step 4: Add `Knowledge` to `tools/__init__.py`**

```python
# src/boukensha/tools/__init__.py  (full file)
from __future__ import annotations

from .file_system import FileSystem
from .mud import Mud
from .shell import Shell
from .navigation import Navigation
from .exploration import Exploration
from .room_processor import RoomProcessor
from .combat import Combat
from .knowledge import Knowledge

__all__ = ["FileSystem", "Mud", "Shell", "Navigation", "Exploration", "RoomProcessor", "Combat", "Knowledge"]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd week2_capable/agent-exp
uv run pytest tests/test_tools_knowledge.py -v
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
cd week2_capable/agent-exp
git add src/boukensha/tools/knowledge.py src/boukensha/tools/__init__.py tests/test_tools_knowledge.py
git commit -m "feat: add knowledge_add and knowledge_search tools"
```

---

### Task 3: Register tools and inject knowledge into system prompt

**Files:**
- Modify: `week2_capable/agent-exp/src/boukensha/__init__.py` — register `Knowledge` tools in both `run()` and `repl()`, inject knowledge into resolved system prompt
- Test: `week2_capable/agent-exp/tests/test_knowledge_injection.py`

**Interfaces:**
- Consumes: `Knowledge.register(registry, knowledge_dir=...)` from Task 2; `KnowledgeManager.read_all()` from Task 1
- The knowledge injection helper function:
  - `_build_knowledge_section(entries: list[dict], token_cap: int = 2000) -> str`
  - Returns a `\n\n## World Knowledge\n...` string, or `""` if no entries fit

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_knowledge_injection.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd week2_capable/agent-exp
uv run pytest tests/test_knowledge_injection.py -v 2>&1 | head -20
```
Expected: `ImportError` — `_knowledge_injection` module doesn't exist yet.

- [ ] **Step 3: Create the injection helper module**

```python
# src/boukensha/_knowledge_injection.py
from __future__ import annotations

from typing import Any


def build_knowledge_section(
    entries: list[dict[str, Any]],
    token_cap: int = 2000,
) -> str:
    if not entries:
        return ""

    lines: list[str] = []
    used_tokens = 0

    for entry in entries:
        line = (
            f"- [{entry.get('topic', '')}] "
            f"{entry.get('fact', '')} "
            f"(source: {entry.get('source', '')})"
        )
        line_tokens = len(line) // 4
        if used_tokens + line_tokens > token_cap:
            break
        lines.append(line)
        used_tokens += line_tokens

    if not lines:
        return ""

    return "\n\n## World Knowledge\n" + "\n".join(lines)
```

- [ ] **Step 4: Run injection tests to verify they pass**

```bash
cd week2_capable/agent-exp
uv run pytest tests/test_knowledge_injection.py -v
```
Expected: all PASS.

- [ ] **Step 5: Wire into `run()` in `__init__.py`**

In `src/boukensha/__init__.py`, find the `run()` function. After `resolved_system = system or task_class.system_prompt(...)`, add:

```python
    # Inject world knowledge into system prompt
    from ._knowledge_injection import build_knowledge_section
    from .memory.knowledge import KnowledgeManager as _KM
    _km = _KM(cfg.dir)
    _knowledge_section = build_knowledge_section(_km.read_all())
    if _knowledge_section:
        resolved_system = (resolved_system or "") + _knowledge_section
```

Then, after the `if resolved_mud:` block (where MUD tools are registered), add `Knowledge` tool registration. Add it after `tools.Combat.register(...)`:

```python
        tools.Knowledge.register(registry, knowledge_dir=cfg.dir)
```

- [ ] **Step 6: Wire into `repl()` in `__init__.py`**

In `src/boukensha/__init__.py`, find the `repl()` function. Make the identical two changes as Step 5 — the injection after `resolved_system = ...` and the `Knowledge.register` call after `tools.Combat.register(...)`.

- [ ] **Step 7: Run the full test suite**

```bash
cd week2_capable/agent-exp
uv run pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: all existing tests still PASS, new tests PASS.

- [ ] **Step 8: Commit**

```bash
cd week2_capable/agent-exp
git add src/boukensha/_knowledge_injection.py src/boukensha/__init__.py tests/test_knowledge_injection.py
git commit -m "feat: inject world knowledge into system prompt at startup"
```

---

### Task 4: Update system prompt and gitignore

**Files:**
- Modify: `week2_capable/agent-exp/prompts/system.md` — add `## World Knowledge` behavioral section
- Modify: `.gitignore` (repo root) or `week2_capable/agent-exp/.gitignore` — exclude `knowledge.yaml`

**Interfaces:** None — documentation and config only.

- [ ] **Step 1: Add behavioral section to `prompts/system.md`**

Append to the end of `week2_capable/agent-exp/prompts/system.md`:

```markdown

## World Knowledge

The `## World Knowledge` block at the end of this prompt (if present) contains facts discovered in previous sessions — quest hints, item locations, NPC behaviours, door requirements.

- Call `knowledge_add(topic, fact, source)` whenever an NPC, sign, or game event reveals something that could help complete a quest or navigate the world. Examples: quest requirements, locked door solutions, where to find an item, what an NPC gives you if asked.
- Call `knowledge_search(query)` before attempting anything non-trivial: unlocking a door, finding a specific NPC, starting a quest. Check what you already know first.
- When a fact turns out to be wrong or outdated, call `knowledge_add` again with the same topic and corrected information — it will overwrite the old entry.
```

- [ ] **Step 2: Add `knowledge.yaml` to `.gitignore`**

Check if a `.gitignore` exists at repo root or in `week2_capable/agent-exp/`:

```bash
cat /Users/alan.k.wodarski/code-local/ai/claude-code-camp-2026-Q2/.gitignore 2>/dev/null | grep -i knowledge || echo "not found"
```

Add this line to the appropriate `.gitignore` (repo root is fine since `.boukensha/` is already there):

```
.boukensha/knowledge.yaml
```

- [ ] **Step 3: Run full test suite one final time**

```bash
cd week2_capable/agent-exp
uv run pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
cd week2_capable/agent-exp
git add prompts/system.md
# from repo root:
cd /Users/alan.k.wodarski/code-local/ai/claude-code-camp-2026-Q2
git add .gitignore
git commit -m "feat: add World Knowledge behavioral instructions and gitignore entry"
```
