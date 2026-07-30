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
