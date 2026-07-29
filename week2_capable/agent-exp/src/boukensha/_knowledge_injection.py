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
