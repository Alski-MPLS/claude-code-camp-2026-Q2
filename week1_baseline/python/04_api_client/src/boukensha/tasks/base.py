"""Boukensha::Tasks::Base port: an abstract stateless task class.

All behaviour is expressed as classmethods/staticmethods that accept a
``settings`` dict — no instances are created.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class Base:
    TASK_NAME: str | None = None

    @classmethod
    def task_name(cls) -> str:
        if cls.TASK_NAME is None:
            raise NotImplementedError(f"{cls.__name__} must define TASK_NAME")
        return cls.TASK_NAME

    @classmethod
    def provider(cls, settings: dict[str, Any]) -> str:
        value = settings.get("provider")
        if not value:
            raise ValueError(f"tasks.{cls.task_name()}.provider is required in settings.yaml")
        return value

    @classmethod
    def model(cls, settings: dict[str, Any]) -> str:
        value = settings.get("model")
        if not value:
            raise ValueError(f"tasks.{cls.task_name()}.model is required in settings.yaml")
        return value

    @classmethod
    def prompt_override(cls, settings: dict[str, Any], prompt: str = "system") -> bool:
        node = settings.get("prompt_override")
        if not isinstance(node, dict):
            return False
        return node.get(prompt) is True

    @classmethod
    def prompt(
        cls,
        settings: dict[str, Any],
        name: str = "system",
        user_prompts_dir: str | None = None,
        default_prompts_dir: str | None = None,
    ) -> str | None:
        if cls.prompt_override(settings, name):
            text = cls._read_user_prompt(name, user_prompts_dir=user_prompts_dir)
            if text is not None:
                return text

        return cls._read_default_prompt(name, default_prompts_dir=default_prompts_dir)

    @classmethod
    def system_prompt(
        cls,
        settings: dict[str, Any],
        user_prompts_dir: str | None = None,
        default_prompts_dir: str | None = None,
    ) -> str | None:
        return cls.prompt(
            settings,
            "system",
            user_prompts_dir=user_prompts_dir,
            default_prompts_dir=default_prompts_dir,
        )

    # ---------- private -----------------------------------------------------

    @classmethod
    def _read_user_prompt(cls, prompt_name: str, user_prompts_dir: str | None = None) -> str | None:
        if not user_prompts_dir:
            return None
        return cls._read_file(Path(user_prompts_dir) / cls.task_name() / f"{prompt_name}.md")

    @classmethod
    def _read_default_prompt(cls, prompt_name: str, default_prompts_dir: str | None = None) -> str | None:
        if not default_prompts_dir:
            return None
        return cls._read_file(Path(default_prompts_dir) / f"{prompt_name}.md")

    @staticmethod
    def _read_file(path: Path) -> str | None:
        return path.read_text().strip() if path.exists() else None
