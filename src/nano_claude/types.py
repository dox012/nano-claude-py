"""Core type definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolDef:
    """Concrete tool implementation."""
    name: str
    description: str
    input_schema: dict[str, Any]
    _call: Callable[..., str] = field(repr=False)

    def call(self, **kwargs: Any) -> str:
        return self._call(**kwargs)


@dataclass
class Config:
    model: str
    max_tokens: int
    system_prompt: str
    api_key: str | None = None
    base_url: str | None = None


@dataclass
class ApiResponse:
    content: list[dict[str, Any]]
    stop_reason: str | None
    usage: dict[str, int]
