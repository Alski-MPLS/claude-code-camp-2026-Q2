# Knowledge Discovery & Storage — Design Spec

**Date:** 2026-07-29  
**Project:** boukensha (week2_capable/agent-exp)  
**Status:** Approved

---

## Problem

The agent discovers facts through gameplay — NPC dialogue, quest hints, environmental clues — that are essential for completing quests and navigating the world. Examples:

- "Ask the guard near the east gate for the red key"
- "The minotaur's chamber requires the red key to enter"
- "You can ask NPCs questions to get quest hints"

Currently, nothing captures or persists this knowledge. Each session starts blind.

---

## Design

### Storage

**File:** `.boukensha/knowledge.yaml`  
**Scope:** World-scoped (shared across all characters and playthroughs — the world rules don't change per character)  
**Format:** YAML list of entries

```yaml
- topic: red key
  fact: Ask the guard near the east gate — he will give it to you if you ask.
  source: east gate guard
  timestamp: 2026-07-29T00:00:00Z

- topic: minotaur
  fact: Requires the red key to enter its chamber.
  source: innkeeper
  timestamp: 2026-07-29T00:01:00Z
```

**Fields:**
- `topic` — short keyword label (e.g. "red key", "minotaur", "guild of swords")
- `fact` — the useful information in plain English
- `source` — who or what revealed it (NPC name, room name, sign, etc.)
- `timestamp` — ISO 8601 UTC, set on write

**`KnowledgeManager` class** (mirrors `GoalManager` pattern):
- `add(topic, fact, source)` — appends or replaces; case-insensitive match on `topic`
- `search(query)` — keyword match across all three text fields; returns matching entries
- `read_all()` — returns all entries, newest first
- Atomic writes via temp file + `os.replace`

---

### Deduplication

When `knowledge_add` is called with a topic that already exists (case-insensitive match), the existing entry is **replaced** — topic, fact, source, and timestamp all updated. Conflicting or refined facts overwrite old ones rather than accumulating duplicates.

---

### Tools

Two new tools registered in the MUD tool registry:

**`knowledge_add(topic, fact, source)`**
- Agent calls this whenever an NPC, sign, or event reveals something useful for quests or navigation
- Returns a confirmation string
- Replaces any existing entry with the same topic

**`knowledge_search(query)`**
- Keyword search across `topic`, `fact`, and `source` fields
- Returns formatted matching entries as a string
- Agent calls this before attempting anything non-trivial (unlocking a door, finding a specific NPC, starting a quest)

---

### System Prompt Injection

At startup, `KnowledgeManager.read_all()` is called and entries up to a **~2000-token cap** (most recent first) are appended to the system prompt under a `## World Knowledge` section:

```
## World Knowledge
- [red key] Ask the guard near the east gate — he will give it to you if you ask. (source: east gate guard)
- [minotaur] Requires the red key to enter its chamber. (source: innkeeper)
```

- If the file is empty or missing, the section is omitted entirely
- Injection happens where the system prompt string is assembled (before being set on `Context`)
- Entries beyond the cap remain searchable via `knowledge_search`

---

### Behavioral Instructions (additions to `prompts/system.md`)

A new `## World Knowledge` section is added to the standing system prompt:

```markdown
## World Knowledge

The section above (if present) contains facts discovered in previous sessions.

- Call `knowledge_add(topic, fact, source)` whenever an NPC, sign, or game event reveals something that could help complete a quest or navigate the world — quest requirements, locked door solutions, NPC behaviours, item locations.
- Call `knowledge_search(query)` before attempting anything non-trivial: unlocking a door, finding a specific NPC, starting a quest. Check what you already know first.
- When a fact turns out to be wrong or outdated, overwrite it with `knowledge_add` using the corrected information.
```

---

## File Changes

| File | Change |
|------|--------|
| `src/boukensha/memory/knowledge.py` | New — `KnowledgeManager` class |
| `src/boukensha/tools/knowledge.py` | New — `knowledge_add`, `knowledge_search` tools |
| `src/boukensha/run_dsl.py` | Register new tools |
| `src/boukensha/repl.py` | Register new tools; inject knowledge into system prompt at startup |
| `prompts/system.md` | Add `## World Knowledge` behavioral section |
| `.boukensha/knowledge.yaml` | Created on first `knowledge_add` call (not committed) |

---

## Out of Scope

- Knowledge expiry / TTL
- Per-topic confidence scores
- Semantic/embedding-based search (keyword matching is sufficient at this scale)
- UI for browsing the knowledge base
