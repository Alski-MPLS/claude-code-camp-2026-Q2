"""Boukensha::Backends::Base port: shared backend contract for model
validation and model metadata.

Ruby defines both a class method ``model_info(model)`` (lookup by name) and
an instance method ``model_info`` (no args, returns the resolved instance's
metadata) — legal in Ruby because class methods and instance methods live in
separate method tables. Python has no such separation, so the two would
collide under one name. Resolution: ``model_info`` stays the public
classmethod; the instance's resolved metadata lives in the private
``self._model_info``, exposed only through the specific public properties
below (``context_window``, etc.) — which matches the Ruby README's
documented public instance API, which never lists ``model_info`` itself as
something instances expose.

Ruby's ``validate_model!`` interpolates ``self.name``, the fully-qualified
class name (``Boukensha::Backends::Anthropic``). Python's ``cls.__name__``
gives the bare class name (``Anthropic``) — there is no Python equivalent of
Ruby's namespaced ``Module::Class`` string; this is a language difference,
not a bug.
"""

from __future__ import annotations

from typing import Any

from ..errors import UnsupportedModelError


class Base:
    MODELS: dict[str, dict[str, Any]] | None = None

    @classmethod
    def models(cls) -> dict[str, dict[str, Any]]:
        if cls.MODELS is None:
            raise NotImplementedError(f"{cls.__name__} must define MODELS")
        return cls.MODELS

    @classmethod
    def model_info(cls, model: str) -> dict[str, Any] | None:
        return cls.models().get(str(model))

    @classmethod
    def validate_model(cls, model: str) -> str:
        model = str(model)
        if cls.model_info(model) is not None:
            return model

        supported = ", ".join(sorted(cls.models().keys()))
        raise UnsupportedModelError(
            f"{cls.__name__} does not support model {model!r}. Supported models: {supported}"
        )

    @property
    def context_window(self) -> int:
        return self._model_info["context_window"]

    @property
    def input_token_cost_per_million(self) -> float | None:
        return self._model_info["cost_per_million"]["input"]

    @property
    def output_token_cost_per_million(self) -> float | None:
        return self._model_info["cost_per_million"]["output"]

    @property
    def usage_unit(self) -> str:
        return self._model_info["usage_unit"]

    @property
    def usage_level(self) -> str | None:
        return self._model_info.get("usage_level")

    def estimate_cost(self, *, input_tokens: int, output_tokens: int) -> float | None:
        in_cost = self.input_token_cost_per_million
        out_cost = self.output_token_cost_per_million
        if in_cost is None or out_cost is None:
            return None

        return ((input_tokens * in_cost) + (output_tokens * out_cost)) / 1_000_000.0

    def _configure_model(self, model: str) -> None:
        self.model = type(self).validate_model(model)
        self._model_info = type(self).model_info(self.model)
