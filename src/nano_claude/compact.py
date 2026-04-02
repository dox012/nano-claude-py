"""Smart conversation compaction to manage context window."""

from __future__ import annotations

import json
from typing import Any

import anthropic
from rich.console import Console

from .types import Config

console = Console(stderr=True)


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """Rough heuristic: 1 token ~ 4 characters."""
    chars = 0
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, str):
            chars += len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    chars += len(str(block.get("text", "")))
                    chars += len(str(block.get("content", "")))
    return (chars + 3) // 4


def smart_compact(
    client: anthropic.Anthropic,
    config: Config,
    messages: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Compact conversation by summarizing older messages.

    Returns (compacted_messages, messages_saved).
    """
    before = len(messages)
    if before <= 4:
        return messages, 0

    to_summarize = messages[:-2]
    keep = messages[-2:]

    summary_messages = [
        {
            "role": "user",
            "content": (
                "Summarize this conversation concisely. Focus on:\n"
                "- Key decisions made\n"
                "- Files read or modified\n"
                "- Important facts learned\n"
                "- Current task state\n\n"
                f"Conversation to summarize:\n{_serialize_messages(to_summarize)}\n\n"
                "Respond with ONLY the summary, no preamble."
            ),
        }
    ]

    console.print("  [dim]Compacting conversation...[/dim]")

    response = client.messages.create(
        model=config.model,
        max_tokens=2048,
        messages=summary_messages,
        system="You are a conversation summarizer. Be concise but preserve all important technical details.",
    )

    summary = "Previous conversation was compacted."
    if response.content and response.content[0].type == "text":
        summary = response.content[0].text

    compacted = [
        {
            "role": "user",
            "content": f"[Conversation compacted — summary of {len(to_summarize)} previous messages]\n\n{summary}",
        },
        {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "I have the context from the compacted conversation. Ready to continue.",
                }
            ],
        },
        *keep,
    ]

    return compacted, before - len(compacted)


def should_auto_compact(messages: list[dict[str, Any]], max_context_tokens: int = 150_000) -> bool:
    """Trigger compaction at 75% of context limit."""
    return estimate_tokens(messages) > max_context_tokens * 0.75


def _serialize_messages(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for m in messages:
        role = m.get("role", "").upper()
        content = m.get("content", "")
        if isinstance(content, str):
            parts.append(f"[{role}]: {content}")
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")
                if btype == "text" and block.get("text"):
                    parts.append(f"[{role}]: {block['text']}")
                elif btype == "tool_use":
                    inp = json.dumps(block.get("input", {}))[:200]
                    parts.append(f"[{role} tool_use]: {block.get('name', '')}({inp})")
                elif btype == "tool_result":
                    c = str(block.get("content", ""))[:200]
                    parts.append(f"[{role} tool_result]: {c}")
    return "\n".join(parts)
